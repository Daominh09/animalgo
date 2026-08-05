import { useEffect, useMemo, useRef, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { router, useLocalSearchParams } from "expo-router";

import { useCollection } from "@/api/collection";
import { CaptureCallout } from "@/map/CaptureCallout";
import {
  boundsFor,
  buildGeoJson,
  capturesToPins,
  CENTER,
  FIT_OPTIONS,
  MAPLIBRE_CSS,
  MAPLIBRE_JS,
  PIN_HIT_LAYER,
  PIN_LAYER,
  STYLE_URL,
  ZOOM,
} from "@/map/mapHtml";

// Owner: Person B — Rarity Engine & Collection
// Web Map screen. Metro resolves this over map.tsx for the web bundle, so
// react-native-webview (which has no web build) never enters it.
//
// MapLibre is mounted straight into the page rather than into an <iframe srcDoc>.
// A srcDoc iframe has an opaque origin, and MapLibre spawns a Web Worker from a blob
// URL, which browsers block there — the map silently fails and renders blank.
//
// Week 2: pass real captures as `pins`.

// maplibre-gl is loaded from a CDN at runtime rather than bundled, so it stays out of
// the native build. Minimal shape of the bits we use.
interface GeoJsonSource {
  setData(data: unknown): void;
}
interface MapMouseEvent {
  point: { x: number; y: number };
  features?: { properties: { id: string } }[];
}
interface MapLibreMap {
  addControl(control: unknown, position?: string): void;
  addSource(id: string, source: unknown): void;
  addLayer(layer: unknown): void;
  getSource(id: string): GeoJsonSource | undefined;
  getCanvas(): HTMLCanvasElement;
  queryRenderedFeatures(point: unknown, options?: unknown): unknown[];
  fitBounds(bounds: [[number, number], [number, number]], options?: unknown): void;
  on(event: string, layerOrHandler: string | ((e: MapMouseEvent) => void), handler?: (e: MapMouseEvent) => void): void;
  remove(): void;
}
interface MapLibreGl {
  Map: new (options: Record<string, unknown>) => MapLibreMap;
  NavigationControl: new (options?: Record<string, unknown>) => unknown;
}

declare global {
  interface Window {
    maplibregl?: MapLibreGl;
  }
}

/** Injects a <script>/<link> once, resolving when it has loaded. */
function loadOnce(tag: "script" | "link", url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const selector = tag === "script" ? `script[src="${url}"]` : `link[href="${url}"]`;
    const existing = document.querySelector(selector);
    if (existing) {
      if (existing.getAttribute("data-loaded") === "true") resolve();
      else {
        existing.addEventListener("load", () => resolve());
        existing.addEventListener("error", () => reject(new Error(`failed to load ${url}`)));
      }
      return;
    }
    const el = document.createElement(tag);
    if (tag === "script") {
      (el as HTMLScriptElement).src = url;
      (el as HTMLScriptElement).async = true;
    } else {
      (el as HTMLLinkElement).rel = "stylesheet";
      (el as HTMLLinkElement).href = url;
    }
    el.addEventListener("load", () => {
      el.setAttribute("data-loaded", "true");
      resolve();
    });
    el.addEventListener("error", () => reject(new Error(`failed to load ${url}`)));
    document.head.appendChild(el);
  });
}

export default function MapScreen() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const { data, isPending } = useCollection();
  const { focus } = useLocalSearchParams<{ focus?: string }>();

  // A capture id arriving from the Collection screen. Held in state and the param
  // cleared, so returning to this tab later doesn't re-frame the same capture, and so
  // asking for the same one twice works instead of being a no-op.
  useEffect(() => {
    if (!focus) return;
    setFocusId(focus);
    setSelectedId(focus);
    router.setParams({ focus: undefined });
  }, [focus]);

  const pins = useMemo(() => capturesToPins(data ?? []), [data]);
  // Looked up by id rather than stored as an object, so a refetch shows the new version
  // instead of a stale copy, and a capture that disappears closes the card.
  const selected = data?.find((c) => c.id === selectedId) ?? null;

  // Kept in a ref so the setup effect never re-runs when captures arrive. Re-running it
  // would destroy the map and reload every tile on each refetch.
  const pinsRef = useRef(pins);
  pinsRef.current = pins;
  const focusRef = useRef(focusId);
  focusRef.current = focusId;

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | undefined;

    (async () => {
      try {
        await Promise.all([loadOnce("link", MAPLIBRE_CSS), loadOnce("script", MAPLIBRE_JS)]);
        if (cancelled) return;

        const gl = window.maplibregl;
        if (!gl || !containerRef.current) throw new Error("maplibre-gl unavailable");

        map = new gl.Map({
          container: containerRef.current,
          style: STYLE_URL,
          center: CENTER,
          zoom: ZOOM,
        });
        map.addControl(new gl.NavigationControl({ showCompass: false }), "top-right");
        map.on("load", () => {
          if (cancelled) return;
          // pinsRef, not pins: captures may have arrived while the tiles were loading.
          map?.addSource("captures", { type: "geojson", data: buildGeoJson(pinsRef.current) });
          map?.addLayer(PIN_LAYER);
          map?.addLayer(PIN_HIT_LAYER);
          const bounds = boundsFor(pinsRef.current, focusRef.current);
          if (bounds) map?.fitBounds(bounds, FIT_OPTIONS);
          mapRef.current = map ?? null;
          setStatus("ready");
        });

        // Clicks are tested against the invisible hit layer, not the visible pin, so
        // the target is finger-sized without drawing a finger-sized dot.
        map.on("click", PIN_HIT_LAYER.id, (e) => {
          const id = e.features?.[0]?.properties.id;
          if (id) setSelectedId(id);
        });
        // A click on empty map dismisses the card. This also fires for pin clicks, but
        // MapLibre runs the layer handler first, so the selection survives.
        map.on("click", (e) => {
          const hits = mapRef.current?.queryRenderedFeatures(e.point, { layers: [PIN_HIT_LAYER.id] });
          if (!hits?.length) setSelectedId(null);
        });
        map.on("mouseenter", PIN_HIT_LAYER.id, () => {
          const canvas = mapRef.current?.getCanvas();
          if (canvas) canvas.style.cursor = "pointer";
        });
        map.on("mouseleave", PIN_HIT_LAYER.id, () => {
          const canvas = mapRef.current?.getCanvas();
          if (canvas) canvas.style.cursor = "";
        });
        map.on("error", () => {
          if (!cancelled) setStatus("error");
        });
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  // Push new captures into the existing source rather than rebuilding the map.
  // No-ops until the map is ready, which the effect above handles.
  useEffect(() => {
    if (status !== "ready") return;
    mapRef.current?.getSource("captures")?.setData(buildGeoJson(pins));
    const bounds = boundsFor(pins, focusId);
    if (bounds) mapRef.current?.fitBounds(bounds, FIT_OPTIONS);
  }, [pins, focusId, status]);

  return (
    <View className="flex-1 bg-slate-50">
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {status === "loading" && (
        <View className="absolute inset-0 items-center justify-center bg-slate-50">
          <ActivityIndicator />
          <Text className="mt-3 text-sm text-slate-500">Loading map…</Text>
        </View>
      )}

      {status === "error" && (
        <View className="absolute inset-0 items-center justify-center bg-slate-50 px-8">
          <Text className="text-center text-base text-slate-700">Couldn&apos;t load the map.</Text>
          <Text className="mt-2 text-center text-sm text-slate-400">
            Map tiles need an internet connection.
          </Text>
        </View>
      )}

      <View className="absolute left-0 right-0 top-0" pointerEvents="none">
        <View className="m-3 self-start rounded-full bg-black/70 px-3 py-1.5">
          <Text className="text-xs font-medium text-white">
            {isPending
              ? "Loading captures…"
              : pins.length === 0
                ? "No captures with a location yet"
                : `${pins.length} ${pins.length === 1 ? "capture" : "captures"} · approximate`}
          </Text>
        </View>
      </View>

      {selected && (
        <CaptureCallout
          capture={selected}
          onClose={() => setSelectedId(null)}
          onViewInCollection={() => {
            // Close first: coming back to the Map tab should show the map, not a card
            // left open over it from a previous visit.
            setSelectedId(null);
            router.push({ pathname: "/(tabs)/collection", params: { highlight: selected.id } });
          }}
        />
      )}
    </View>
  );
}

import { useEffect, useRef, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";

import {
  buildGeoJson,
  CENTER,
  MAPLIBRE_CSS,
  MAPLIBRE_JS,
  PIN_LAYER,
  STYLE_URL,
  ZOOM,
  type MapPin,
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
interface MapLibreMap {
  addControl(control: unknown, position?: string): void;
  addSource(id: string, source: unknown): void;
  addLayer(layer: unknown): void;
  on(event: string, handler: () => void): void;
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
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  // Week 1: no pins yet. Week 2 replaces this with real captures.
  const pins: MapPin[] = [];

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
          map?.addSource("captures", { type: "geojson", data: buildGeoJson(pins) });
          map?.addLayer(PIN_LAYER);
          setStatus("ready");
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
      map?.remove();
    };
    // Pins are static in Week 1; re-running on every render would tear down the map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          <Text className="text-xs font-medium text-white">Map · no pins yet (Week 1)</Text>
        </View>
      </View>
    </View>
  );
}

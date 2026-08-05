import { useEffect, useMemo, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import { router, useLocalSearchParams } from "expo-router";

import { useCollection } from "@/api/collection";
import { CaptureCallout } from "@/map/CaptureCallout";
import { buildMapHtml, capturesToPins } from "@/map/mapHtml";

// Owner: Person B — Rarity Engine & Collection
// Native (iOS/Android) Map screen. The web version lives in map.web.tsx, because
// react-native-webview has no web build; both render the same document from
// src/map/mapHtml.ts and read the same captures from GET /collection.
//
// Pins are baked into the HTML rather than pushed in later over the WebView bridge.
// That means a refetch reloads the document, which is fine here: a collection changes
// once per capture, not continuously, and it avoids a second messaging path to maintain.
//
// IMPORTANT: do not import @maplibre/maplibre-react-native here. It is a native module
// Expo Go cannot load, and Expo Router eagerly loads every route file — so that import
// crashes the whole app on startup, not just this tab.

export default function MapScreen() {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const { data, isPending, isMock } = useCollection();
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
  // Looked up by id rather than stored as an object, so a refetch that changes a
  // capture shows the new version instead of a stale copy — and a capture that
  // disappears closes the card instead of pinning a row that no longer exists.
  const selected = data?.find((c) => c.id === selectedId) ?? null;

  /** The map document talks to us over the WebView bridge; every message is JSON. */
  function handleMessage(raw: string) {
    let msg: { type?: string; id?: string };
    try {
      msg = JSON.parse(raw);
    } catch {
      setStatus("error");
      return;
    }
    if (msg.type === "ready") setStatus("ready");
    else if (msg.type === "select" && msg.id) setSelectedId(msg.id);
    else if (msg.type === "deselect") setSelectedId(null);
    else setStatus("error");
  }
  // Only rebuild the document when the pins or the framing actually change, so an
  // unrelated re-render doesn't tear the map down and reload the tiles.
  const html = useMemo(() => buildMapHtml(pins, focusId), [pins, focusId]);

  const label = isPending
    ? "Loading captures…"
    : pins.length === 0
      ? "No captures with a location yet"
      : `${pins.length} ${pins.length === 1 ? "capture" : "captures"} · approximate${isMock ? " · mock data" : ""}`;

  return (
    <View className="flex-1 bg-slate-50">
      <WebView
        // Reloads when the pins or the framing change, and only then. Keyed on the
        // actual inputs rather than html.length, which two different documents can
        // easily share — changing which pin is framed swaps coordinates of the same
        // width, so the length would not move and the map would never re-frame.
        key={`${pins.map((p) => p.id).join(",")}|${focusId ?? ""}`}
        originWhitelist={["*"]}
        source={{ html }}
        onMessage={(e) => handleMessage(e.nativeEvent.data)}
        onError={() => setStatus("error")}
        style={{ flex: 1 }}
      />

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

      <SafeAreaView className="absolute left-0 right-0 top-0" edges={["top"]} pointerEvents="none">
        <View className="m-3 self-start rounded-full bg-black/70 px-3 py-1.5">
          <Text className="text-xs font-medium text-white">{label}</Text>
        </View>
      </SafeAreaView>

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

import { useMemo, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";

import { useCollection } from "@/api/collection";
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
  const { data, isPending, signedOut } = useCollection();

  const pins = useMemo(() => capturesToPins(data ?? []), [data]);
  // Only rebuild the document when the pins actually change, so an unrelated re-render
  // doesn't tear the map down and reload the tiles.
  const html = useMemo(() => buildMapHtml(pins), [pins]);

  const label = signedOut
    ? "Sign in to see your captures"
    : isPending
      ? "Loading captures…"
      : pins.length === 0
        ? "No captures with a location yet"
        : `${pins.length} ${pins.length === 1 ? "capture" : "captures"} · approximate`;

  return (
    <View className="flex-1 bg-slate-50">
      <WebView
        // Reloads when the pins change; the key keeps that tied to the data, not to
        // every render.
        key={html.length}
        originWhitelist={["*"]}
        source={{ html }}
        onMessage={(e) => setStatus(e.nativeEvent.data === "ready" ? "ready" : "error")}
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
    </View>
  );
}

import { View, Text } from "react-native";

import { MAP_HTML } from "@/map/mapHtml";

// Owner: Person B — Rarity Engine & Collection
// Web Map screen. react-native-webview has no web build, so on web the same map
// document (src/map/mapHtml.ts) is hosted in an <iframe> instead. Metro picks this file
// over map.tsx for the web bundle via the .web extension, so react-native-webview is
// never pulled into the web bundle.

export default function MapScreen() {
  return (
    <View className="flex-1 bg-slate-50">
      <iframe
        title="Capture map"
        srcDoc={MAP_HTML}
        style={{ border: "none", width: "100%", height: "100%" }}
      />

      <View
        className="absolute left-0 right-0 top-0"
        pointerEvents="none"
      >
        <View className="m-3 self-start rounded-full bg-black/70 px-3 py-1.5">
          <Text className="text-xs font-medium text-white">Map · no pins yet (Week 1)</Text>
        </View>
      </View>
    </View>
  );
}

import { View, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MapView, Camera } from "@maplibre/maplibre-react-native";

// Owner: Person B — Rarity Engine & Collection
// Week 1: MapLibre shell — renders a real map, no capture pins yet.
// Week 2: drop pins for real captures; verify fuzzed coords render correctly for
//   IUCN Vulnerable/Endangered/Critically Endangered species (coords may be null).
//
// Note: MapLibre is a native module — it does NOT run in Expo Go. Use a dev build
//   (`npx expo run:android` / `run:ios` or an EAS dev client).

// Free demo tiles hosted by MapLibre; no API key or usage fees (per the tech-stack
// choice of MapLibre over Google Maps). Swap for a richer style later if needed.
const DEMO_STYLE_URL = "https://demotiles.maplibre.org/style.json";

// Default view: roughly centered on Vietnam until we center on the player's location.
const DEFAULT_CENTER: [number, number] = [105.8, 21.0]; // [lng, lat] — Hanoi
const DEFAULT_ZOOM = 4;

export default function MapScreen() {
  return (
    <View className="flex-1">
      <MapView style={{ flex: 1 }} mapStyle={DEMO_STYLE_URL}>
        <Camera zoomLevel={DEFAULT_ZOOM} centerCoordinate={DEFAULT_CENTER} />
      </MapView>

      {/* Week 1 marker so it's obvious pins aren't wired yet */}
      <SafeAreaView className="absolute left-0 right-0 top-0" edges={["top"]} pointerEvents="none">
        <View className="m-3 self-start rounded-full bg-black/70 px-3 py-1.5">
          <Text className="text-xs font-medium text-white">Map · no pins yet (Week 1)</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

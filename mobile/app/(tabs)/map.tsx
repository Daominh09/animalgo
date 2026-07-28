import { useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";

// Owner: Person B — Rarity Engine & Collection
// Week 1: MapLibre shell — a real, interactive map with no capture pins yet.
// Week 2: add capture pins; captures whose coordinates were fuzzed/withheld for
//   sensitive species (IUCN VU/EN/CR) must be excluded, not plotted at a wrong spot.
//
// IMPORTANT: do not import @maplibre/maplibre-react-native here. It is a native module
// that Expo Go cannot load, and Expo Router eagerly loads every route file — so that
// import crashes the whole app on startup, not just this tab. We render MapLibre GL JS
// in a WebView instead: same MapLibre (no Google Maps fees), but react-native-webview
// ships inside Expo Go, so it works without a dev build.

// Free demo tiles hosted by MapLibre — no API key, no usage fees.
const STYLE_URL = "https://demotiles.maplibre.org/style.json";
const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js";
const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";

// Default view: continental US, since the app targets US-based players.
const CENTER: [number, number] = [-98.5, 39.8]; // [lng, lat]
const ZOOM = 3;

const MAP_HTML = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<link href="${MAPLIBRE_CSS}" rel="stylesheet" />
<script src="${MAPLIBRE_JS}"></script>
<style>html,body,#map{margin:0;padding:0;height:100%;width:100%}body{background:#eef2f7}</style>
</head>
<body>
<div id="map"></div>
<script>
  function post(msg){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(msg); } }
  try {
    var map = new maplibregl.Map({
      container: 'map',
      style: '${STYLE_URL}',
      center: [${CENTER[0]}, ${CENTER[1]}],
      zoom: ${ZOOM}
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', function(){ post('ready'); });
    map.on('error', function(){ post('error'); });
  } catch (e) { post('error'); }
</script>
</body>
</html>`;

export default function MapScreen() {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  return (
    <View className="flex-1 bg-slate-50">
      <WebView
        originWhitelist={["*"]}
        source={{ html: MAP_HTML }}
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
          <Text className="text-xs font-medium text-white">Map · no pins yet (Week 1)</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

import { useState } from "react";
import { View, Text, Image, Pressable } from "react-native";

import type { Capture } from "../api/collection";
import { rarityMeta } from "../rarity";

// Owner: Person B — Rarity Engine & Collection
//
// Details for a tapped map pin. Deliberately a React component rather than a MapLibre
// popup: popups would mean writing the card twice, once as HTML inside the native
// WebView document and once for web, and they could not reuse the rarity badge styling
// the Collection screen already has.

export function CaptureCallout({
  capture,
  onClose,
  onViewInCollection,
}: {
  capture: Capture;
  onClose: () => void;
  onViewInCollection: () => void;
}) {
  const meta = rarityMeta(capture.rarity_tier);
  const [failed, setFailed] = useState(false);

  return (
    <View className="absolute inset-x-0 bottom-0 p-3">
      <View className={`flex-row rounded-2xl border-2 bg-white p-3 shadow-lg ${meta.ringClass}`}>
        {failed || !capture.image_url ? (
          <View className="h-20 w-20 items-center justify-center rounded-xl bg-slate-200">
            <Text className="text-xs text-slate-500">No photo</Text>
          </View>
        ) : (
          <Image
            source={{ uri: capture.image_url }}
            onError={() => setFailed(true)}
            resizeMode="cover"
            className="h-20 w-20 rounded-xl bg-slate-100"
          />
        )}

        <View className="ml-3 flex-1">
          <Text className="font-semibold italic text-slate-900" numberOfLines={1}>
            {capture.species_id ?? "Unidentified"}
          </Text>

          <View className={`mt-1 self-start rounded-full px-2 py-0.5 ${meta.badgeClass}`}>
            <Text className={`text-xs font-medium ${meta.badgeClass}`}>{meta.label}</Text>
          </View>

          <Text className="mt-1 text-xs text-slate-500">
            {new Date(capture.captured_at).toLocaleDateString()}
          </Text>

          {/* Says "approximate" rather than printing the numbers as if they were the
              real spot. Every capture is snapped to a ~11 km cell before it is stored,
              so this pin is the cell, not the animal. */}
          <Text className="mt-0.5 text-xs text-slate-400">
            Approximate area · {capture.lat?.toFixed(2)}, {capture.lng?.toFixed(2)}
          </Text>

          <Pressable
            onPress={onViewInCollection}
            hitSlop={8}
            className="mt-2 self-start rounded-full bg-slate-900 px-3 py-1.5"
          >
            <Text className="text-xs font-medium text-white">View in Collection →</Text>
          </Pressable>
        </View>

        <Pressable onPress={onClose} hitSlop={12} className="ml-2 self-start">
          <Text className="text-lg leading-none text-slate-400">×</Text>
        </Pressable>
      </View>
    </View>
  );
}

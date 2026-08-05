import { useState } from "react";
import { View, Text, Image, Pressable } from "react-native";

import type { Capture } from "../api/collection";
import { displayName } from "../captures";
import { rarityMeta } from "../rarity";

// Owner: Person B — Rarity Engine & Collection
//
// Details for a tapped map pin. Deliberately a React component rather than a MapLibre
// popup: a popup would mean writing the card twice, once as HTML inside the native
// WebView document and once for web, and could not reuse the rarity badge styling the
// Collection screen already has.
//
// The whole card is the target, with a chevron on the right rather than a labelled
// button. A small button asks the player to aim at it; a card-sized target with an
// arrow says "this leads somewhere" and is far easier to hit on a phone. The chevron
// occupies space that was empty anyway.

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
      <Pressable
        onPress={onViewInCollection}
        accessibilityRole="button"
        accessibilityLabel={`${displayName(capture)}, view in collection`}
        // Pressed state on the whole card, so it is obvious the card itself is the
        // control rather than something sitting inside it.
        style={({ pressed }) => (pressed ? { opacity: 0.7 } : undefined)}
        className={`flex-row items-center rounded-2xl border-2 bg-white p-3 shadow-lg ${meta.ringClass}`}
      >
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
          <Text className="font-semibold text-slate-900" numberOfLines={1}>
            {displayName(capture)}
          </Text>

          <View className={`mt-1 self-start rounded-full px-2 py-0.5 ${meta.badgeClass}`}>
            <Text className={`text-xs font-medium ${meta.badgeClass}`}>{meta.label}</Text>
          </View>

          <Text className="mt-1 text-xs text-slate-500">
            {new Date(capture.captured_at).toLocaleDateString()}
          </Text>

          {/* Says "approximate" rather than printing the numbers as though they were the
              real spot. Every capture is snapped to a ~11 km cell before storage, so the
              pin is the cell, not the animal. */}
          <Text className="mt-0.5 text-xs text-slate-400">
            Approximate area · {capture.lat?.toFixed(2)}, {capture.lng?.toFixed(2)}
          </Text>
        </View>

        {/* The affordance: fills the empty right-hand strip and reads as "tap through". */}
        <Text className="ml-2 mr-1 text-2xl font-light text-slate-300">›</Text>
      </Pressable>

      {/* Outside the card's Pressable, not nested in it — a dismiss control that also
          navigated would be the most annoying possible bug. Overlaps the top-right
          corner so it never competes with the chevron for the same tap. */}
      <Pressable
        onPress={onClose}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel="Close"
        className="absolute right-1 top-1 h-7 w-7 items-center justify-center rounded-full bg-slate-900/70"
      >
        <Text className="text-sm leading-none text-white">×</Text>
      </Pressable>
    </View>
  );
}

import { useState } from "react";
import { View, Text, Image, Pressable } from "react-native";

import type { BattleCapture } from "@/api/battles";
import { captureName, traitMeta } from "@/battles";
import { rarityMeta } from "@/rarity";

// Owner: Person C — Battle System
// The capture-as-a-fighter card, shared by the roster picker and the matchup views so a
// capture looks the same wherever it is fielded.

/** Placeholder used for a side that has not chosen a capture yet — the opponent's slot
 *  while a challenge is still pending. */
function EmptySlot({ size }: { size: string }) {
  return (
    <View className={`${size} items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50`}>
      <Text className="text-xs text-slate-400">?</Text>
    </View>
  );
}

function CaptureImage({ capture, size }: { capture: BattleCapture; size: string }) {
  const [failed, setFailed] = useState(false);

  // A broken R2 URL shows a labelled placeholder rather than an empty box, matching how
  // the Collection grid handles the same failure.
  if (failed || !capture.image_url) {
    return (
      <View className={`${size} items-center justify-center rounded-xl bg-slate-200`}>
        <Text className="text-xs text-slate-500">No photo</Text>
      </View>
    );
  }
  return (
    <Image
      source={{ uri: capture.image_url }}
      onError={() => setFailed(true)}
      resizeMode="cover"
      className={`${size} rounded-xl bg-slate-100`}
    />
  );
}

export function TraitBadge({ trait }: { trait: string | null }) {
  const meta = traitMeta(trait);
  return (
    <View className={`self-start rounded-full px-2 py-0.5 ${meta.badgeClass}`}>
      <Text className={`text-[10px] font-medium ${meta.badgeClass}`}>
        {meta.icon} {meta.label}
      </Text>
    </View>
  );
}

/**
 * One capture, as a fighter.
 *
 * `selected` rings it; `onPress` makes it choosable. Both are optional so the same card
 * serves the read-only matchup view on the result screen.
 */
export function BattleCard({
  capture,
  selected = false,
  onPress,
  compact = false,
}: {
  capture: BattleCapture | null;
  selected?: boolean;
  onPress?: () => void;
  compact?: boolean;
}) {
  const size = compact ? "h-24 w-24" : "aspect-square w-full";
  const rarity = rarityMeta(capture?.rarity_tier);

  const body = capture ? (
    <>
      <CaptureImage capture={capture} size={size} />
      <Text className="mt-2 text-center text-sm font-semibold text-slate-900" numberOfLines={1}>
        {captureName(capture)}
      </Text>
      <View className="mt-1 items-center gap-1">
        <View className={`rounded-full px-2 py-0.5 ${rarity.badgeClass}`}>
          <Text className={`text-[10px] font-medium ${rarity.badgeClass}`}>{rarity.label}</Text>
        </View>
        <TraitBadge trait={capture.trait} />
      </View>
    </>
  ) : (
    <>
      <EmptySlot size={size} />
      <Text className="mt-2 text-center text-sm text-slate-400">{captureName(null)}</Text>
    </>
  );

  const frame = `rounded-2xl border-2 bg-white p-2 ${
    selected ? "border-slate-900 bg-slate-50" : capture ? rarity.ringClass : "border-transparent"
  }`;

  // A plain View when there is nothing to tap: wrapping a read-only card in a Pressable
  // makes it look interactive on a screen where nothing is.
  if (!onPress) {
    return <View className={frame}>{body}</View>;
  }
  return (
    <Pressable onPress={onPress} className={frame}>
      {body}
    </Pressable>
  );
}

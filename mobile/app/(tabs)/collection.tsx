import { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, Image, FlatList, ActivityIndicator, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";

import { useCollection, type Capture } from "@/api/collection";
import { GRID_COLUMNS, rowIndexFor } from "@/captures";
import { rarityMeta } from "@/rarity";

// Owner: Person B — Rarity Engine & Collection
// Week 2: real captures from GET /collection, rarest first (the backend does the
// ordering, so the grid renders the list as given).
//
// Accepts a `highlight` param — the Map screen's "View in Collection" sends a capture id
// here, and the grid scrolls to that card and rings it.

/** How long the ring stays before fading out. Long enough to find the card after the
 *  scroll settles, short enough that it doesn't look like permanent selection state. */
const HIGHLIGHT_MS = 3000;

function CaptureCard({ capture, highlighted }: { capture: Capture; highlighted: boolean }) {
  const meta = rarityMeta(capture.rarity_tier);
  const [failed, setFailed] = useState(false);

  return (
    <View
      className={`flex-1 m-1.5 rounded-2xl border-2 bg-white p-3 ${
        highlighted ? "border-slate-900 bg-slate-50" : meta.ringClass
      }`}
    >
      {/* The photo the player took. Falls back to a neutral placeholder if the image
          can't load, so a broken R2 URL never shows an empty box. */}
      {failed || !capture.image_url ? (
        <View className="aspect-square w-full items-center justify-center rounded-xl bg-slate-200">
          <Text className="text-xs text-slate-500">No photo</Text>
        </View>
      ) : (
        <Image
          source={{ uri: capture.image_url }}
          onError={() => setFailed(true)}
          resizeMode="cover"
          className="aspect-square w-full rounded-xl bg-slate-100"
        />
      )}

      {/* Scientific name for now. Once the capture row carries a common name this
          becomes the headline and the scientific name moves underneath. */}
      <Text className="mt-2 font-semibold italic text-slate-900" numberOfLines={1}>
        {capture.species_id ?? "Unidentified"}
      </Text>
      <Text className="text-xs text-slate-500" numberOfLines={1}>
        {new Date(capture.captured_at).toLocaleDateString()}
      </Text>

      <View className={`mt-2 self-start rounded-full px-2 py-0.5 ${meta.badgeClass}`}>
        <Text className={`text-xs font-medium ${meta.badgeClass}`}>{meta.label}</Text>
      </View>
    </View>
  );
}

/** Full-screen message, used for every state that isn't a populated grid. */
function Centered({ title, detail, action }: { title: string; detail?: string; action?: React.ReactNode }) {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-center text-base text-slate-700">{title}</Text>
      {detail ? <Text className="mt-2 text-center text-sm text-slate-400">{detail}</Text> : null}
      {action}
    </View>
  );
}

export default function CollectionScreen() {
  const { data, isPending, isError, error, refetch, isRefetching, isMock } = useCollection();
  const { highlight } = useLocalSearchParams<{ highlight?: string }>();
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const listRef = useRef<FlatList<Capture>>(null);

  const captures = data ?? [];

  useEffect(() => {
    if (!highlight) return;
    const index = captures.findIndex((c) => c.id === highlight);
    // The capture may not be here — an id from a stale link, or a row that has since
    // been removed. Clear the param and leave the grid alone rather than scrolling
    // somewhere arbitrary.
    if (index === -1) {
      router.setParams({ highlight: undefined });
      return;
    }

    setHighlightedId(highlight);
    // Row index, not item index — see rowIndexFor. Passing the item index throws
    // "scrollToIndex out of range" for anything past the halfway point of the grid.
    listRef.current?.scrollToIndex({ index: rowIndexFor(index), animated: true, viewPosition: 0.5 });

    // Cleared immediately so tapping the same capture from the map a second time
    // re-triggers this effect. Leaving the param set would make the second tap a no-op.
    router.setParams({ highlight: undefined });

    const timer = setTimeout(() => setHighlightedId(null), HIGHLIGHT_MS);
    return () => clearTimeout(timer);
    // captures is intentionally not a dependency: it changes identity on every refetch,
    // which would re-scroll and re-ring the card while the player is reading it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight]);

  // Cards are variable height, so there's no getItemLayout and scrollToIndex can fire
  // before the target row has been measured. Jump to an estimate, then retry once the
  // list has rendered past it. `index` here is already a row index, and
  // averageItemLength is a row height, so they multiply directly.
  const handleScrollFailed = useCallback(
    ({ index, averageItemLength }: { index: number; averageItemLength: number }) => {
      listRef.current?.scrollToOffset({ offset: index * averageItemLength, animated: true });
      setTimeout(() => {
        listRef.current?.scrollToIndex({ index, animated: true, viewPosition: 0.5 });
      }, 250);
    },
    [],
  );
  const subtitle = isPending
    ? "Loading…"
    : `${captures.length} ${captures.length === 1 ? "capture" : "captures"}${isMock ? " · mock data" : ""}`;

  return (
    <SafeAreaView className="flex-1 bg-slate-50" edges={["top"]}>
      <View className="px-4 pb-2 pt-3">
        <Text className="text-2xl font-bold text-slate-900">Collection</Text>
        <Text className="text-sm text-slate-500">{subtitle}</Text>
      </View>

      {isPending ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator />
        </View>
      ) : isError ? (
        // Surfaced rather than swallowed: an empty grid and a failed request look
        // identical to a player, and only one of them is worth retrying.
        <Centered
          title="Couldn't load your collection."
          detail={error instanceof Error ? error.message : undefined}
          action={
            <Pressable
              onPress={() => refetch()}
              className="mt-4 rounded-full bg-slate-900 px-5 py-2"
            >
              <Text className="text-sm font-medium text-white">Try again</Text>
            </Pressable>
          }
        />
      ) : captures.length === 0 ? (
        <Centered
          title="No captures yet."
          detail="Photograph an animal on the Camera tab to start your collection."
        />
      ) : (
        <FlatList
          ref={listRef}
          data={captures}
          keyExtractor={(item) => item.id}
          // Same constant rowIndexFor uses. If these two ever disagree, scrollToIndex
          // starts throwing "out of range" — which is exactly how it broke before.
          numColumns={GRID_COLUMNS}
          onRefresh={refetch}
          refreshing={isRefetching}
          onScrollToIndexFailed={handleScrollFailed}
          contentContainerStyle={{ paddingHorizontal: 10, paddingBottom: 24 }}
          renderItem={({ item }) => (
            <CaptureCard capture={item} highlighted={item.id === highlightedId} />
          )}
          // Without this the rows already rendered keep their old `highlighted` prop,
          // because FlatList treats the renderItem closure as unchanged data.
          extraData={highlightedId}
        />
      )}
    </SafeAreaView>
  );
}

import { useState } from "react";
import { View, Text, Image, FlatList } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { MOCK_CAPTURES_BY_RARITY, RARITY_META, type MockCapture } from "@/mock/captures";

// Owner: Person B — Rarity Engine & Collection
// Week 1: grid of mock capture cards (sorted by rarity).
// Week 2: wire to real capture data from GET /collection, sorted by rarity.

function CaptureCard({ capture }: { capture: MockCapture }) {
  const meta = RARITY_META[capture.rarity];
  const [failed, setFailed] = useState(false);
  return (
    <View className={`flex-1 m-1.5 rounded-2xl border-2 bg-white p-3 ${meta.ringClass}`}>
      {/* The photo the player took (R2 image_url in Week 2). Falls back to a neutral
          placeholder if the image can't load, so a broken URL never shows an empty box. */}
      {failed ? (
        <View className="aspect-square w-full items-center justify-center rounded-xl bg-slate-200">
          <Text className="text-xs text-slate-500">No photo</Text>
        </View>
      ) : (
        <Image
          source={{ uri: capture.imageUrl }}
          onError={() => setFailed(true)}
          resizeMode="cover"
          className="aspect-square w-full rounded-xl bg-slate-100"
        />
      )}
      <Text className="mt-2 font-semibold text-slate-900" numberOfLines={1}>
        {capture.species}
      </Text>
      <Text className="text-xs italic text-slate-500" numberOfLines={1}>
        {capture.scientificName}
      </Text>
      <View className={`mt-2 self-start rounded-full px-2 py-0.5 ${meta.badgeClass}`}>
        <Text className={`text-xs font-medium ${meta.badgeClass}`}>{meta.label}</Text>
      </View>
    </View>
  );
}

export default function CollectionScreen() {
  return (
    <SafeAreaView className="flex-1 bg-slate-50" edges={["top"]}>
      <View className="px-4 pb-2 pt-3">
        <Text className="text-2xl font-bold text-slate-900">Collection</Text>
        <Text className="text-sm text-slate-500">
          {MOCK_CAPTURES_BY_RARITY.length} species · mock data (Week 1)
        </Text>
      </View>
      <FlatList
        data={MOCK_CAPTURES_BY_RARITY}
        keyExtractor={(item) => item.id}
        numColumns={2}
        contentContainerStyle={{ paddingHorizontal: 10, paddingBottom: 24 }}
        renderItem={({ item }) => <CaptureCard capture={item} />}
      />
    </SafeAreaView>
  );
}

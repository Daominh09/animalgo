import { useState } from "react";
import { View, Text, Pressable, FlatList, Image } from "react-native";
import { useRouter } from "expo-router";

import { MOCK_MY_ROSTER, MOCK_OPPONENT, type MockCapture } from "../../src/mocks/captures";

// Owner: Person C — Battle System
// Week 1: roster-select screen — pick one of your mock captures to challenge with
// Week 2: wire to real /collection data + real opponent lookup

export default function BattleScreen() {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const renderCapture = ({ item }: { item: MockCapture }) => {
    const isSelected = item.id === selectedId;
    return (
      <Pressable
        onPress={() => setSelectedId(item.id)}
        className={`flex-1 m-2 rounded-lg border p-3 items-center ${
          isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200"
        }`}
      >
        <Image source={{ uri: item.imageUrl }} className="w-20 h-20 rounded-md mb-2" />
        <Text className="font-semibold">{item.speciesName}</Text>
        <Text className="text-xs text-gray-500 capitalize">{item.rarityTier}</Text>
      </Pressable>
    );
  };

  return (
    <View className="flex-1 pt-4">
      <Text className="text-lg font-bold px-4 mb-2">Choose your capture</Text>
      <Text className="text-sm text-gray-500 px-4 mb-4">
        Challenging {MOCK_OPPONENT.displayName}
      </Text>
      <FlatList
        data={MOCK_MY_ROSTER}
        keyExtractor={(item) => item.id}
        renderItem={renderCapture}
        numColumns={2}
        contentContainerClassName="px-2 pb-4"
      />
      <Pressable
        disabled={!selectedId}
        onPress={() => router.push({ pathname: "/battle-challenge", params: { captureId: selectedId! } })}
        className={`m-4 rounded-lg p-4 items-center ${selectedId ? "bg-blue-600" : "bg-gray-300"}`}
      >
        <Text className="text-white font-semibold">Review Challenge</Text>
      </Pressable>
    </View>
  );
}

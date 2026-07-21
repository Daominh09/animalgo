import { useState } from "react";
import { View, Text, Pressable, Image } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { MOCK_MY_ROSTER, MOCK_OPPONENT } from "../src/mocks/captures";
import { apiFetch } from "../src/api/client";

// Owner: Person C — Battle System
// Week 1: challenge review screen — confirm the matchup, send the mock challenge
// Week 2: swap MOCK_OPPONENT for a real opponent lookup + real auth token

export default function BattleChallengeScreen() {
  const router = useRouter();
  const { captureId } = useLocalSearchParams<{ captureId: string }>();
  const [status, setStatus] = useState<string | null>(null);

  const myCapture = MOCK_MY_ROSTER.find((c) => c.id === captureId) ?? MOCK_MY_ROSTER[0];
  const opponentCapture = MOCK_OPPONENT.roster[0];

  const sendChallenge = async () => {
    setStatus("sending");
    // The /battles/challenge stub takes opponent_id + my_capture_id as query
    // params (no request body), matching the other Week 1 route stubs.
    const params = new URLSearchParams({ opponent_id: MOCK_OPPONENT.id, my_capture_id: myCapture.id });
    const result = await apiFetch(`/battles/challenge?${params.toString()}`, { method: "POST" });
    setStatus(result.status);
  };

  return (
    <View className="flex-1 items-center justify-center px-6">
      <Text className="text-lg font-bold mb-6">Confirm Challenge</Text>

      <View className="flex-row items-center justify-center mb-8">
        <View className="items-center mx-4">
          <Image source={{ uri: myCapture.imageUrl }} className="w-24 h-24 rounded-md mb-2" />
          <Text className="font-semibold">{myCapture.speciesName}</Text>
          <Text className="text-xs text-gray-500 capitalize">{myCapture.rarityTier}</Text>
        </View>
        <Text className="text-xl font-bold mx-2">VS</Text>
        <View className="items-center mx-4">
          <Image source={{ uri: opponentCapture.imageUrl }} className="w-24 h-24 rounded-md mb-2" />
          <Text className="font-semibold">{opponentCapture.speciesName}</Text>
          <Text className="text-xs text-gray-500 capitalize">{opponentCapture.rarityTier}</Text>
        </View>
      </View>

      {status ? (
        <Text className="mb-4 text-gray-700">Challenge status: {status}</Text>
      ) : null}

      <Pressable onPress={sendChallenge} className="bg-blue-600 rounded-lg px-6 py-4 items-center w-full">
        <Text className="text-white font-semibold">Send Challenge</Text>
      </Pressable>
      <Pressable onPress={() => router.back()} className="mt-3 px-6 py-3 items-center w-full">
        <Text className="text-gray-500">Back</Text>
      </Pressable>
    </View>
  );
}

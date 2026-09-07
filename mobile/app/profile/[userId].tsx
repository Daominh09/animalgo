import { ActivityIndicator, Image, Pressable, Share, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

// Owner: Person D — Economy, Shop & Shared Infra
// Week 2: GET /profile/{id}/public + this share screen. No auth needed to view --
// it's the public endpoint by design (see the backend route's own comment for what's
// deliberately excluded: wallet balance, raw coordinates).

type RarestCapture = {
  common_name: string | null;
  species_id: string | null;
  rarity_tier: string;
  image_url: string;
};

type PublicProfile = {
  user_id: string;
  display_name: string;
  capture_count: number;
  rarest_capture: RarestCapture | null;
  battle_wins: number;
};

export default function PublicProfileScreen() {
  const { userId } = useLocalSearchParams<{ userId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["profile", userId],
    queryFn: () => apiFetch(`/profile/${userId}/public`) as Promise<PublicProfile>,
    enabled: !!userId,
  });

  const share = async () => {
    if (!data) return;
    const rarest = data.rarest_capture
      ? ` Rarest catch: ${data.rarest_capture.common_name ?? data.rarest_capture.species_id} (${data.rarest_capture.rarity_tier}).`
      : "";
    await Share.share({
      message: `${data.display_name} has caught ${data.capture_count} animal${data.capture_count === 1 ? "" : "s"} on AnimalGO!${rarest}`,
    });
  };

  if (isLoading) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator />
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View className="flex-1 items-center justify-center px-6">
        <Text className="text-center text-base text-gray-700">Couldn&apos;t load this profile.</Text>
      </View>
    );
  }

  return (
    <View className="flex-1 items-center px-6 pt-10">
      <Text className="text-2xl font-bold">{data.display_name}</Text>

      <View className="mt-6 w-full flex-row justify-around">
        <View className="items-center">
          <Text className="text-xl font-bold">{data.capture_count}</Text>
          <Text className="text-xs text-gray-500">Captures</Text>
        </View>
        <View className="items-center">
          <Text className="text-xl font-bold">{data.battle_wins}</Text>
          <Text className="text-xs text-gray-500">Battle wins</Text>
        </View>
      </View>

      {data.rarest_capture && (
        <View className="mt-8 w-full items-center rounded-xl border border-gray-200 p-4">
          <Text className="mb-2 text-xs uppercase tracking-wide text-gray-400">Rarest catch</Text>
          <Image source={{ uri: data.rarest_capture.image_url }} className="mb-3 h-24 w-24 rounded-lg" />
          <Text className="font-semibold">
            {data.rarest_capture.common_name ?? data.rarest_capture.species_id}
          </Text>
          <Text className="text-sm capitalize text-gray-500">{data.rarest_capture.rarity_tier}</Text>
        </View>
      )}

      <Pressable onPress={share} className="mt-10 w-full items-center rounded-lg bg-black py-4">
        <Text className="font-semibold text-white">Share profile</Text>
      </Pressable>
    </View>
  );
}

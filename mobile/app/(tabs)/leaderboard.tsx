import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

// Owner: Person D — Economy, Shop & Shared Infra
// Week 2: GET /leaderboard, Redis-cached, rank criteria is user-selectable.

type RankBy = "coins" | "captures" | "rarity" | "wins";

const RANK_OPTIONS: { key: RankBy; label: string; unit: string }[] = [
  { key: "coins", label: "Coins", unit: "coins" },
  { key: "captures", label: "Captures", unit: "catches" },
  { key: "rarity", label: "Rarest", unit: "pts" },
  { key: "wins", label: "Wins", unit: "wins" },
];

type LeaderboardRow = {
  user_id: string;
  display_name: string;
  value: number;
};

export default function LeaderboardScreen() {
  const [rankBy, setRankBy] = useState<RankBy>("coins");
  const unit = RANK_OPTIONS.find((o) => o.key === rankBy)!.unit;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["leaderboard", rankBy],
    queryFn: () => apiFetch(`/leaderboard?rank_by=${rankBy}`) as Promise<LeaderboardRow[]>,
  });

  return (
    <View className="flex-1">
      <View className="px-4 pb-2 pt-3">
        <Text className="text-xl font-bold">Leaderboard</Text>
      </View>

      <View className="flex-row gap-2 px-4 pb-3">
        {RANK_OPTIONS.map((opt) => (
          <Pressable
            key={opt.key}
            onPress={() => setRankBy(opt.key)}
            className={`rounded-full px-3 py-1.5 ${rankBy === opt.key ? "bg-black" : "bg-gray-200"}`}
          >
            <Text className={`text-sm font-medium ${rankBy === opt.key ? "text-white" : "text-gray-700"}`}>
              {opt.label}
            </Text>
          </Pressable>
        ))}
      </View>

      <FlatList
        data={data ?? []}
        keyExtractor={(row) => row.user_id}
        renderItem={({ item, index }) => (
          <View className="flex-row items-center justify-between border-b border-gray-200 px-4 py-3">
            <View className="flex-row items-center gap-3">
              <Text className="w-6 text-sm font-semibold text-gray-400">{index + 1}</Text>
              <Text className="text-base">{item.display_name || "Anonymous"}</Text>
            </View>
            <Text className="text-base font-semibold">
              {item.value} {unit}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          isLoading ? (
            <ActivityIndicator className="mt-8" />
          ) : isError ? (
            <Text className="mt-8 text-center text-sm text-red-500">Couldn&apos;t load the leaderboard.</Text>
          ) : (
            <Text className="mt-8 text-center text-sm text-gray-400">No entries yet.</Text>
          )
        }
      />
    </View>
  );
}

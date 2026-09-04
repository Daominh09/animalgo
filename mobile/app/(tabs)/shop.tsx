import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAppStore } from "@/store/useAppStore";

// Owner: Person D — Economy, Shop & Shared Infra
// Week 1: mock catalog
// Week 2 (this file): real GET /shop/items + POST /shop/purchase. Purchases
// require a logged-in user (Authorization header) — there's no login screen
// yet, so purchase calls will 401 until auth is wired up. The catalog list
// itself needs no auth and works today.

type ShopItem = {
  id: string;
  name: string;
  type: string;
  cost: number;
  effect: string;
};

function ShopItemRow({ item, onBuy, buying }: { item: ShopItem; onBuy: () => void; buying: boolean }) {
  return (
    <View className="flex-row items-center justify-between border-b border-gray-200 px-4 py-3">
      <View className="flex-1">
        <Text className="text-base font-semibold">{item.name}</Text>
        <Text className="text-sm text-gray-500">{item.effect}</Text>
      </View>
      <Text className="mr-3 text-base font-semibold">{item.cost}</Text>
      <Pressable
        onPress={onBuy}
        disabled={buying}
        className="rounded-full bg-black px-4 py-2 disabled:opacity-40"
      >
        <Text className="text-sm font-medium text-white">{buying ? "…" : "Buy"}</Text>
      </Pressable>
    </View>
  );
}

export default function ShopScreen() {
  const accessToken = useAppStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [purchasingId, setPurchasingId] = useState<string | null>(null);

  const { data: items, isLoading, isError } = useQuery({
    queryKey: ["shop-items"],
    queryFn: () => apiFetch("/shop/items") as Promise<ShopItem[]>,
  });

  const purchase = useMutation({
    mutationFn: (itemId: string) =>
      apiFetch(`/shop/purchase?item_id=${itemId}`, { method: "POST" }, accessToken ?? undefined),
    onMutate: (itemId) => {
      setError(null);
      setPurchasingId(itemId);
    },
    onError: (err: Error) => setError(err.message),
    onSettled: () => setPurchasingId(null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["wallet"] }),
  });

  return (
    <View className="flex-1">
      <FlatList
        data={items ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ShopItemRow
            item={item}
            buying={purchasingId === item.id}
            onBuy={() => purchase.mutate(item.id)}
          />
        )}
        ListHeaderComponent={
          <View className="px-4 py-3">
            <Text className="text-xl font-bold">Shop</Text>
            {!accessToken && (
              <Text className="mt-1 text-xs text-gray-400">
                Not logged in — purchases will fail until sign-in exists.
              </Text>
            )}
            {error && <Text className="mt-1 text-xs text-red-500">{error}</Text>}
          </View>
        }
        ListEmptyComponent={
          isLoading ? (
            <ActivityIndicator className="mt-8" />
          ) : isError ? (
            <Text className="mt-8 text-center text-sm text-red-500">Couldn&apos;t load the shop.</Text>
          ) : (
            <Text className="mt-8 text-center text-sm text-gray-400">No items available.</Text>
          )
        }
      />
    </View>
  );
}

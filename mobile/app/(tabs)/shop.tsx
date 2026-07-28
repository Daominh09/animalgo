import { FlatList, Text, View } from "react-native";

// Owner: Person D — Economy, Shop & Shared Infra
// Week 1: mock catalog (this file)
// Week 2: replace MOCK_CATALOG with GET /shop, wire up real purchase flow
// (debit wallet via a server-side action, grant item — not a raw client
// credit call, see the security note on wallet.credit_wallet)

type ShopItem = {
  id: string;
  name: string;
  type: string;
  cost: number;
  effect: string;
};

// Shape matches backend/app/models.py's ShopItem table, so swapping this
// for a real GET /shop response later is a drop-in replacement.
const MOCK_CATALOG: ShopItem[] = [
  { id: "1", name: "Lure Scent", type: "consumable", cost: 50, effect: "+10% capture rate for 30 min" },
  { id: "2", name: "Rarity Scanner", type: "consumable", cost: 120, effect: "Reveals rarity tier before capture" },
  { id: "3", name: "Battle Shield", type: "consumable", cost: 80, effect: "Blocks one loss streak penalty" },
  { id: "4", name: "Golden Frame", type: "cosmetic", cost: 200, effect: "Profile-only cosmetic, no gameplay effect" },
];

function ShopItemRow({ item }: { item: ShopItem }) {
  return (
    <View className="flex-row items-center justify-between border-b border-gray-200 px-4 py-3">
      <View className="flex-1">
        <Text className="text-base font-semibold">{item.name}</Text>
        <Text className="text-sm text-gray-500">{item.effect}</Text>
      </View>
      <Text className="text-base font-semibold">{item.cost}</Text>
    </View>
  );
}

export default function ShopScreen() {
  return (
    <View className="flex-1">
      <FlatList
        data={MOCK_CATALOG}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <ShopItemRow item={item} />}
        ListHeaderComponent={
          <Text className="px-4 py-3 text-xl font-bold">Shop</Text>
        }
      />
    </View>
  );
}

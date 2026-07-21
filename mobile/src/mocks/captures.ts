// Owner: Person C — Battle System
// Week 1: fabricated captures so the roster-select + challenge screens have
// something to render before Person A/B's real capture data exists.
// Week 2: replace both arrays with real /captures + /collection data.

export type RarityTier = "common" | "uncommon" | "rare" | "legendary";

export interface MockCapture {
  id: string;
  speciesName: string;
  rarityTier: RarityTier;
  imageUrl: string;
}

export const MOCK_MY_ROSTER: MockCapture[] = [
  { id: "cap-1", speciesName: "Red Fox", rarityTier: "common", imageUrl: "https://placehold.co/200x200?text=Red+Fox" },
  { id: "cap-2", speciesName: "Snowy Owl", rarityTier: "rare", imageUrl: "https://placehold.co/200x200?text=Snowy+Owl" },
  { id: "cap-3", speciesName: "Monarch Butterfly", rarityTier: "uncommon", imageUrl: "https://placehold.co/200x200?text=Monarch" },
  { id: "cap-4", speciesName: "Amur Leopard", rarityTier: "legendary", imageUrl: "https://placehold.co/200x200?text=Amur+Leopard" },
];

export const MOCK_OPPONENT = {
  id: "user-opponent-1",
  displayName: "Jordan",
  roster: [
    { id: "cap-9", speciesName: "Gray Wolf", rarityTier: "rare" as RarityTier, imageUrl: "https://placehold.co/200x200?text=Gray+Wolf" },
  ],
};

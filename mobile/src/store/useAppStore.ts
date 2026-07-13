import { create } from "zustand";

interface AppState {
  userId: string | null;
  walletBalance: number;
  setUser: (id: string | null) => void;
  setWalletBalance: (amount: number) => void;
}

export const useAppStore = create<AppState>((set) => ({
  userId: null,
  walletBalance: 0,
  setUser: (id) => set({ userId: id }),
  setWalletBalance: (amount) => set({ walletBalance: amount }),
}));

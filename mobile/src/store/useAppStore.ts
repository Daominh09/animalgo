import { create } from "zustand";

interface AppState {
  userId: string | null;
  // Supabase access token — set once a login flow exists. Every
  // authenticated API call (wallet, purchase, ...) reads this.
  accessToken: string | null;
  walletBalance: number;
  setUser: (id: string | null) => void;
  setAccessToken: (token: string | null) => void;
  setWalletBalance: (amount: number) => void;
}

export const useAppStore = create<AppState>((set) => ({
  userId: null,
  accessToken: null,
  walletBalance: 0,
  setUser: (id) => set({ userId: id }),
  setAccessToken: (token) => set({ accessToken: token }),
  setWalletBalance: (amount) => set({ walletBalance: amount }),
}));

import { create } from "zustand";

interface AppState {
  userId: string | null;
  /** Supabase access token, sent as the bearer token on every authenticated request.
   *  Nothing sets this yet — Person D's sign-in flow owns that. Until it does, screens
   *  that need it show a signed-out state rather than failing with a 401. */
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

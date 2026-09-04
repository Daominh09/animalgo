import { create } from "zustand";

interface AppState {
  userId: string | null;
  /** Access token, sent as the bearer token on every authenticated request. Issued by
   *  Supabase but obtained through our own /auth endpoints, so the app never talks to
   *  Supabase directly. Written only by src/auth/useSession.ts, which also refreshes it
   *  before it expires. */
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

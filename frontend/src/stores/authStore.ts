import { create } from "zustand";
import type { User } from "../types";

interface AuthState { token: string | null; user: User | null; setAuth: (token: string, user: User) => void; logout: () => void }
const storedToken = localStorage.getItem("edurag_token");
const storedUser = localStorage.getItem("edurag_user");
export const useAuthStore = create<AuthState>((set) => ({
  token: storedToken, user: storedUser ? JSON.parse(storedUser) as User : null,
  setAuth: (token, user) => { localStorage.setItem("edurag_token", token); localStorage.setItem("edurag_user", JSON.stringify(user)); set({ token, user }); },
  logout: () => { localStorage.removeItem("edurag_token"); localStorage.removeItem("edurag_user"); set({ token: null, user: null }); },
}));

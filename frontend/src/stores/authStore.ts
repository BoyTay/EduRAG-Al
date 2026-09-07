import { create } from "zustand";
import type { User } from "../types";

interface AuthState { token: string | null; user: User | null; setAuth: (token: string, user: User, remember?: boolean) => void; updateUser: (user: User) => void; logout: () => void }
const storedToken = localStorage.getItem("edurag_token") || sessionStorage.getItem("edurag_token");
const storedUser = localStorage.getItem("edurag_user") || sessionStorage.getItem("edurag_user");
export const useAuthStore = create<AuthState>((set) => ({
  token: storedToken, user: storedUser ? JSON.parse(storedUser) as User : null,
  setAuth: (token, user, remember = false) => { const storage = remember ? localStorage : sessionStorage; localStorage.removeItem("edurag_token"); localStorage.removeItem("edurag_user"); sessionStorage.removeItem("edurag_token"); sessionStorage.removeItem("edurag_user"); storage.setItem("edurag_token", token); storage.setItem("edurag_user", JSON.stringify(user)); set({ token, user }); },
  updateUser: (user) => { const storage = localStorage.getItem("edurag_token") ? localStorage : sessionStorage; storage.setItem("edurag_user", JSON.stringify(user)); set({ user }); },
  logout: () => { localStorage.removeItem("edurag_token"); localStorage.removeItem("edurag_user"); sessionStorage.removeItem("edurag_token"); sessionStorage.removeItem("edurag_user"); set({ token: null, user: null }); },
}));

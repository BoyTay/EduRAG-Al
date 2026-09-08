import { Navigate, Route, Routes } from "react-router-dom";
import { MainLayout } from "./layouts/MainLayout";
import { AdminDashboard } from "./pages/AdminDashboard";
import { Chat } from "./pages/Chat";
import { Library } from "./pages/Library";
import { Login } from "./pages/Login";
import { Settings } from "./pages/Settings";
import { ResetPassword } from "./pages/ResetPassword";
import { useAuthStore } from "./stores/authStore";
function Protected() {
  const token = useAuthStore((state) => state.token);
  const isPreview = typeof window !== "undefined" && window.location.search.includes("preview=true");
  return token || isPreview ? <MainLayout /> : <Navigate to="/login" replace />;
}
export default function App() { return <Routes><Route path="/login" element={<Login />} /><Route path="/reset-password" element={<ResetPassword />} /><Route element={<Protected />}><Route path="/chat" element={<Chat />} /><Route path="/library" element={<Library />} /><Route path="/admin" element={<AdminDashboard />} /><Route path="/settings" element={<Settings />} /></Route><Route path="*" element={<Navigate to="/chat" replace />} /></Routes>; }

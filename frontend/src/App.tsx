import { Navigate, Route, Routes } from "react-router-dom";
import { MainLayout } from "./layouts/MainLayout";
import { AdminDashboard } from "./pages/AdminDashboard";
import { Chat } from "./pages/Chat";
import { Library } from "./pages/Library";
import { Login } from "./pages/Login";
import { useAuthStore } from "./stores/authStore";
function Protected() {
  const token = useAuthStore((state) => state.token);
  return token ? <MainLayout /> : <Navigate to="/login" replace />;
}
export default function App() { return <Routes><Route path="/login" element={<Login />} /><Route element={<Protected />}><Route path="/chat" element={<Chat />} /><Route path="/library" element={<Library />} /><Route path="/admin" element={<AdminDashboard />} /></Route><Route path="*" element={<Navigate to="/chat" replace />} /></Routes>; }

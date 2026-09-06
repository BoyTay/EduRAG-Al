import { Outlet } from "react-router-dom";
import { Header } from "../components/common/Header";
import { Sidebar } from "../components/sidebar/Sidebar";
export function MainLayout() { return <div className="flex h-[100dvh] overflow-hidden bg-canvas"><Sidebar /><main className="flex min-w-0 flex-1 flex-col"><Header /><div className="min-h-0 flex-1"><Outlet /></div></main></div>; }

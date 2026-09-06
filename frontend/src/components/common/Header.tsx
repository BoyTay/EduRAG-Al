import { CaretDown, UserCircle } from "@phosphor-icons/react";
import { NavLink } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-xs font-semibold transition ${isActive ? "bg-green-50 text-brand shadow-[inset_0_0_0_1px_rgba(46,125,50,.12)]" : "text-muted hover:bg-green-50 hover:text-brand"}`;

export function Header() {
  const user = useAuthStore((state) => state.user);
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line/80 bg-white/90 px-5 backdrop-blur-sm md:px-8">
      <button type="button" className="hidden items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-xs font-semibold text-brand transition hover:bg-green-100 lg:flex">
        <span className="size-1.5 rounded-full bg-brand" />Quy chế đào tạo tín chỉ 2023<CaretDown size={14} />
      </button>
      <nav aria-label="Điều hướng chính" className="mx-auto flex items-center gap-1 lg:absolute lg:left-1/2 lg:-translate-x-1/2">
        <NavLink to="/chat" className={navClass}>Trang chat</NavLink>
        <NavLink to="/library" className={navClass}>Tài liệu</NavLink>
        {user?.role === "admin" && <NavLink to="/admin" className={navClass}>Quản trị</NavLink>}
      </nav>
      <div className="flex items-center gap-2 text-right">
        <div className="hidden sm:block"><p className="text-xs font-semibold text-ink">{user?.display_name || "Sinh viên"}</p><p className="text-[10px] text-muted">Phiên làm việc đang hoạt động</p></div>
        <span className="grid size-9 place-items-center rounded-xl bg-green-100 text-brand"><UserCircle size={23} weight="fill" /></span>
      </div>
    </header>
  );
}

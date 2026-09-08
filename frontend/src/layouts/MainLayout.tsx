import { Outlet } from "react-router-dom";
import { Header } from "../components/common/Header";
import { Sidebar } from "../components/sidebar/Sidebar";

export function MainLayout() {
  return (
    <div className="flex h-[100dvh] overflow-hidden bg-[#f4faf7]">
      {/* Dark Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-gradient-to-br from-[#d9f2ec]/60 via-[#ebf7f0]/70 to-[#fff8ed]/60">
        {/* Ambient Fluid Waves Background (matching Reference Image 2) */}
        <div
          className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
          aria-hidden="true"
        >
          <svg
            className="absolute -bottom-10 -left-10 h-[110%] w-[120%] opacity-35"
            viewBox="0 0 1200 800"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="waveTeal" x1="0%" y1="50%" x2="100%" y2="50%">
                <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="waveOrange" x1="0%" y1="50%" x2="100%" y2="50%">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.1" />
                <stop offset="60%" stopColor="#f59e0b" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#fb923c" stopOpacity="0.8" />
              </linearGradient>
            </defs>

            {/* Cyan/Teal Ribbon Waves sweeping from bottom-left to top-right */}
            <path
              d="M-50 650 C 200 620, 300 480, 500 520 C 750 570, 900 350, 1250 200"
              stroke="url(#waveTeal)"
              strokeWidth="3.5"
              fill="none"
            />
            <path
              d="M-50 630 C 180 600, 320 460, 520 500 C 770 550, 920 330, 1250 180"
              stroke="url(#waveTeal)"
              strokeWidth="2"
              strokeDasharray="8 6"
              fill="none"
            />
            <path
              d="M-50 670 C 220 640, 280 500, 480 540 C 730 590, 880 370, 1250 220"
              stroke="url(#waveTeal)"
              strokeWidth="1.5"
              fill="none"
            />

            {/* Amber/Peach Ribbon Waves sweeping across towards bottom right */}
            <path
              d="M100 750 C 350 720, 500 590, 750 560 C 950 530, 1100 380, 1250 260"
              stroke="url(#waveOrange)"
              strokeWidth="3.5"
              fill="none"
            />
            <path
              d="M120 770 C 370 740, 520 610, 770 580 C 970 550, 1120 400, 1250 280"
              stroke="url(#waveOrange)"
              strokeWidth="2"
              fill="none"
            />
            <path
              d="M80 730 C 330 700, 480 570, 730 540 C 930 510, 1080 360, 1250 240"
              stroke="url(#waveOrange)"
              strokeWidth="1.5"
              fill="none"
            />
          </svg>

          {/* Glowing 4-point Sparkle Accent in Bottom Right */}
          <div className="absolute bottom-16 right-16 opacity-45">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <path
                d="M24 0 C24 13.25 34.75 24 48 24 C34.75 24 24 34.75 24 48 C24 34.75 13.25 24 0 24 C13.25 24 24 13.25 24 0 Z"
                fill="#fde68a"
              />
            </svg>
          </div>
        </div>

        {/* Header & Main Page View */}
        <Header />
        <div className="relative z-10 min-h-0 flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

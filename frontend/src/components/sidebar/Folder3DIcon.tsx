export function Folder3DIcon({ className = "size-9" }: { className?: string }) {
  return (
    <div className={`relative shrink-0 ${className}`}>
      <svg
        viewBox="0 0 44 44"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="size-full drop-shadow-[0_4px_10px_rgba(16,185,129,0.35)] transition-transform duration-200 group-hover:scale-105"
      >
        <defs>
          <linearGradient id="folderBgGrad" x1="0" y1="0" x2="0" y2="44" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#059669" />
          </linearGradient>
          <linearGradient id="folderFrontGrad" x1="0" y1="18" x2="0" y2="38" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e2e8f0" />
          </linearGradient>
          <linearGradient id="docGreenGrad" x1="0" y1="10" x2="0" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#34d399" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
          <filter id="folder3dShadow" x="-10%" y="-10%" width="130%" height="130%">
            <feDropShadow dx="0" dy="1.8" stdDeviation="1.2" floodColor="#064e3b" floodOpacity="0.32" />
          </filter>
        </defs>

        {/* Squircle Emerald Background Container */}
        <rect width="44" height="44" rx="13" fill="url(#folderBgGrad)" />
        {/* Subtle top inner light highlight */}
        <rect x="0.5" y="0.5" width="43" height="43" rx="12.5" stroke="white" strokeOpacity="0.3" />

        {/* Back blue folder/paper tab */}
        <rect
          x="22"
          y="15"
          width="13"
          height="17"
          rx="3"
          fill="#60a5fa"
          transform="rotate(10 28 23)"
          opacity="0.9"
        />

        {/* Middle Green Document with Lines */}
        <g filter="url(#folder3dShadow)">
          <rect x="14" y="10" width="15" height="19" rx="3" fill="url(#docGreenGrad)" />
          {/* Document Content Lines */}
          <rect x="17" y="14.5" width="9" height="1.8" rx="0.9" fill="#047857" />
          <rect x="17" y="18" width="9" height="1.8" rx="0.9" fill="#047857" />
          <rect x="17" y="21.5" width="6" height="1.8" rx="0.9" fill="#047857" />
        </g>

        {/* Front White Folder Body with 3D curve and tab */}
        <g filter="url(#folder3dShadow)">
          <path
            d="M 9 21.5 C 9 19.5 10.5 18 12.5 18 L 16.5 18 C 17.5 18 18.2 18.5 18.7 19.2 L 19.8 20.8 C 20.2 21.3 20.8 21.5 21.4 21.5 L 31.5 21.5 C 33.5 21.5 35 23 35 25 L 35 32 C 35 34.2 33.2 36 31 36 L 13 36 C 10.8 36 9 34.2 9 32 Z"
            fill="url(#folderFrontGrad)"
          />
          {/* Soft inner curve highlight */}
          <path
            d="M 10 22 C 10 20.5 11.2 19 12.5 19 L 16.5 19 C 17.2 19 17.8 19.4 18.2 20 L 19.3 21.6 C 19.8 22.2 20.6 22.5 21.4 22.5 L 31.5 22.5 C 33 22.5 34 23.5 34 25"
            stroke="white"
            strokeWidth="0.8"
            strokeLinecap="round"
            fill="none"
          />
        </g>
      </svg>
    </div>
  );
}

export function HeroAcademicGraphic({ className = "w-48 h-36" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 180"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        {/* Soft shadow */}
        <filter id="heroShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#0f766e" floodOpacity="0.12" />
        </filter>
        {/* Gradients */}
        <linearGradient id="bookCoverTeal" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2dd4bf" />
          <stop offset="100%" stopColor="#0d9488" />
        </linearGradient>
        <linearGradient id="bookCoverNavy" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
        <linearGradient id="bookCoverOrange" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fb923c" />
          <stop offset="100%" stopColor="#ea580c" />
        </linearGradient>
        <linearGradient id="nodeGlow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#5eead4" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#14b8a6" stopOpacity="0.2" />
        </linearGradient>
      </defs>

      {/* Background Knowledge Network Nodes */}
      <g opacity="0.85">
        {/* Connecting Lines */}
        <path d="M50 70 L95 45 L150 55 L200 40" stroke="#0d9488" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.4" />
        <path d="M95 45 L125 90 L185 85" stroke="#0d9488" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.4" />
        <path d="M150 55 L185 85 L200 40" stroke="#0d9488" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.4" />

        {/* Nodes */}
        <circle cx="50" cy="70" r="14" fill="#ccfbf1" />
        <circle cx="50" cy="70" r="7" fill="#14b8a6" />

        <circle cx="95" cy="45" r="12" fill="#ccfbf1" />
        <circle cx="95" cy="45" r="5" fill="#0d9488" />

        {/* Central Book Node */}
        <circle cx="150" cy="55" r="22" fill="#ccfbf1" filter="url(#heroShadow)" />
        <circle cx="150" cy="55" r="18" fill="#e6fffa" />
        {/* Mini Open Book Icon in Central Node */}
        <path d="M142 50 C146 48 149 48 150 51 C151 48 154 48 158 50 L158 59 C154 57 151 57 150 60 C149 57 146 57 142 59 Z" fill="#0d9488" />

        <circle cx="200" cy="40" r="10" fill="#ccfbf1" />
        <circle cx="200" cy="40" r="4" fill="#14b8a6" />

        <circle cx="125" cy="90" r="9" fill="#ccfbf1" />
        <circle cx="125" cy="90" r="4" fill="#0d9488" />

        <circle cx="185" cy="85" r="11" fill="#ccfbf1" />
        <circle cx="185" cy="85" r="5" fill="#14b8a6" />
      </g>

      {/* Books Stack at Bottom Right */}
      <g filter="url(#heroShadow)">
        {/* Bottom Blue Book (Horizontal) */}
        <path d="M85 140 L160 140 C165 140 168 143 168 147 L168 154 C168 157 165 160 160 160 L85 160 C80 160 76 156 76 150 C76 144 80 140 85 140 Z" fill="url(#bookCoverNavy)" />
        <path d="M88 143 L158 143 L158 157 L88 157 C85 157 82 154 82 150 C82 146 85 143 88 143 Z" fill="#f8fafc" />
        <rect x="88" y="145" width="67" height="10" fill="#e2e8f0" rx="1" />

        {/* Middle Orange Book (Horizontal) */}
        <path d="M92 124 L165 124 C170 124 173 127 173 131 L173 138 C173 141 170 144 165 144 L92 144 C87 144 83 140 83 134 C83 128 87 124 92 124 Z" fill="url(#bookCoverOrange)" />
        <path d="M95 127 L163 127 L163 141 L95 141 C92 141 89 138 89 134 C89 130 92 127 95 127 Z" fill="#fff7ed" />
        {/* Bookmark ribbon */}
        <path d="M125 124 L125 142 L130 137 L135 142 L135 124 Z" fill="#3b82f6" />

        {/* Vertical Books Standing Beside */}
        {/* Book 1 (Sage) */}
        <path d="M174 105 L186 105 L186 160 L174 160 Z" rx="2" fill="#7dd3fc" />
        <path d="M176 108 L184 108 L184 157 L176 157 Z" fill="#38bdf8" />

        {/* Book 2 (Rose/Peach) */}
        <path d="M188 100 L200 100 L200 160 L188 160 Z" rx="2" fill="#fda4af" />
        <path d="M190 103 L198 103 L198 157 L190 157 Z" fill="#f43f5e" />

        {/* Book 3 (Emerald leaning slightly) */}
        <g transform="rotate(-6 203 160)">
          <path d="M202 96 L214 96 L214 160 L202 160 Z" rx="2" fill="#6ee7b7" />
          <path d="M204 99 L212 99 L212 157 L204 157 Z" fill="#10b981" />
        </g>
      </g>
    </svg>
  );
}

export function GraduationCap3D({ className = "size-20" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <filter id="capShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#1e3a8a" floodOpacity="0.22" />
        </filter>
        <linearGradient id="capTopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="50%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
        <linearGradient id="capSkullGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#1e40af" />
          <stop offset="100%" stopColor="#172554" />
        </linearGradient>
        <linearGradient id="tasselGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fbbf24" />
          <stop offset="100%" stopColor="#d97706" />
        </linearGradient>
      </defs>

      <g filter="url(#capShadow)">
        {/* Cap skull base (underneath) */}
        <path
          d="M26 38 C26 54 36 65 50 65 C64 65 74 54 74 38 Z"
          fill="url(#capSkullGrad)"
        />
        {/* Bottom rim edge highlight */}
        <path
          d="M32 54 C37 61 44 64 50 64 C56 64 63 61 68 54 C63 59 56 62 50 62 C44 62 37 59 32 54 Z"
          fill="#60a5fa"
          opacity="0.4"
        />

        {/* Diamond Top Mortarboard (3D perspective) */}
        {/* Bottom thickness layer */}
        <polygon points="50,14 94,33 50,52 6,33" fill="#1e3a8a" />
        <polygon points="6,33 50,52 50,55 6,36" fill="#172554" />
        <polygon points="94,33 50,52 50,55 94,36" fill="#1e40af" />

        {/* Top diamond surface */}
        <polygon points="50,12 94,31 50,50 6,31" fill="url(#capTopGrad)" />

        {/* Highlight line on the top surface */}
        <path d="M50 13 L90 31" stroke="#93c5fd" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />

        {/* Center button */}
        <ellipse cx="50" cy="31" rx="4" ry="2.5" fill="#f59e0b" />
        <ellipse cx="50" cy="30" rx="3" ry="2" fill="#fbbf24" />

        {/* Tassel cord flowing over the left/bottom edge */}
        <path
          d="M50 31 C56 31 66 36 68 44 C69 50 66 56 65 62"
          stroke="url(#tasselGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
        {/* Tassel fringe */}
        <path
          d="M62 62 C64 61 67 61 68 63 L70 76 C67 78 63 78 60 76 Z"
          fill="url(#tasselGrad)"
        />
        {/* Tassel ring */}
        <circle cx="65" cy="63" r="2.5" fill="#fef08a" />
      </g>
    </svg>
  );
}

export function Trophy3D({ className = "size-20" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <filter id="trophyShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#b45309" floodOpacity="0.2" />
        </filter>
        <linearGradient id="goldLight" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="30%" stopColor="#facc15" />
          <stop offset="70%" stopColor="#eab308" />
          <stop offset="100%" stopColor="#ca8a04" />
        </linearGradient>
        <linearGradient id="goldDark" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#ca8a04" />
          <stop offset="100%" stopColor="#854d0e" />
        </linearGradient>
        <linearGradient id="pedestalGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#78350f" />
          <stop offset="100%" stopColor="#451a03" />
        </linearGradient>
      </defs>

      <g filter="url(#trophyShadow)">
        {/* Left handle */}
        <path
          d="M30 22 C18 22 16 38 28 44 C33 46 36 46 36 44 C26 40 26 28 34 26 Z"
          fill="url(#goldLight)"
        />

        {/* Right handle */}
        <path
          d="M70 22 C82 22 84 38 72 44 C67 46 64 46 64 44 C74 40 74 28 66 26 Z"
          fill="url(#goldLight)"
        />

        {/* Pedestal Base */}
        <rect x="36" y="73" width="28" height="9" rx="2" fill="url(#pedestalGrad)" />
        <rect x="34" y="78" width="32" height="4" rx="1.5" fill="#451a03" />
        <rect x="42" y="75" width="16" height="4" rx="1" fill="#fef08a" opacity="0.6" />

        {/* Stem connector */}
        <path d="M46 58 L54 58 L52 73 L48 73 Z" fill="url(#goldDark)" />
        <ellipse cx="50" cy="58" rx="7" ry="3" fill="url(#goldLight)" />

        {/* Main Cup Body */}
        <path
          d="M28 17 C28 42 40 56 50 56 C60 56 72 42 72 17 Z"
          fill="url(#goldLight)"
        />
        {/* Rim top */}
        <ellipse cx="50" cy="17" rx="22" ry="5" fill="url(#goldLight)" />
        <ellipse cx="50" cy="17" rx="20" ry="3.5" fill="#ca8a04" />
        <ellipse cx="50" cy="17" rx="18" ry="2.5" fill="#a16207" />

        {/* Shading & Sheen highlight on cup */}
        <path
          d="M34 21 C33 34 38 46 44 52 C41 46 38 35 38 21 Z"
          fill="#ffffff"
          opacity="0.45"
        />
        {/* Star badge on cup */}
        <path
          d="M50 28 L51.8 33.5 L57.5 33.5 L53 37 L54.7 42.5 L50 39 L45.3 42.5 L47 37 L42.5 33.5 L48.2 33.5 Z"
          fill="#fef08a"
          opacity="0.8"
        />
      </g>
    </svg>
  );
}

export function OpenBook3D({ className = "size-20" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <filter id="bookShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#c2410c" floodOpacity="0.2" />
        </filter>
        <linearGradient id="coverGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ea580c" />
          <stop offset="100%" stopColor="#9a3412" />
        </linearGradient>
        <linearGradient id="pageGradLeft" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ffedd5" />
          <stop offset="85%" stopColor="#fffaf5" />
          <stop offset="100%" stopColor="#fed7aa" />
        </linearGradient>
        <linearGradient id="pageGradRight" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#fed7aa" />
          <stop offset="15%" stopColor="#fffaf5" />
          <stop offset="100%" stopColor="#ffedd5" />
        </linearGradient>
      </defs>

      <g filter="url(#bookShadow)">
        {/* Book Cover Bottom Rim */}
        <path
          d="M12 62 C26 57 44 60 50 67 C56 60 74 57 88 62 L88 66 C74 61 56 64 50 71 C44 64 26 61 12 66 Z"
          fill="url(#coverGrad)"
        />

        {/* Thick page block base */}
        <path
          d="M14 60 C27 55 44 58 50 65 C56 58 73 55 86 60 L86 63 C73 58 56 61 50 68 C44 61 27 58 14 63 Z"
          fill="#fdba74"
        />

        {/* Left Page Surface */}
        <path
          d="M14 26 C28 21 44 24 50 31 L50 65 C44 58 28 55 14 60 Z"
          fill="url(#pageGradLeft)"
        />

        {/* Right Page Surface */}
        <path
          d="M50 31 C56 24 72 21 86 26 L86 60 C72 55 56 58 50 65 Z"
          fill="url(#pageGradRight)"
        />

        {/* Page text lines (Left page) */}
        <line x1="22" y1="33" x2="42" y2="35" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.65" />
        <line x1="20" y1="39" x2="44" y2="41" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <line x1="20" y1="45" x2="43" y2="47" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <line x1="21" y1="51" x2="38" y2="53" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />

        {/* Page text lines (Right page) */}
        <line x1="58" y1="35" x2="78" y2="33" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.65" />
        <line x1="56" y1="41" x2="80" y2="39" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <line x1="57" y1="47" x2="80" y2="45" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <line x1="62" y1="53" x2="79" y2="51" stroke="#f97316" strokeWidth="2" strokeLinecap="round" opacity="0.5" />

        {/* Spine Crease shadow */}
        <path d="M49 31 L49 66 L51 66 L51 31 Z" fill="#ea580c" opacity="0.3" />

        {/* Center Ribbon Bookmark */}
        <path
          d="M49 31 C49 38 52 46 54 54 L51 52 L48 54 C48 44 49 36 49 31 Z"
          fill="#dc2626"
        />
      </g>
    </svg>
  );
}

export function Calendar3D({ className = "size-20" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <filter id="calShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#0f766e" floodOpacity="0.2" />
        </filter>
        <linearGradient id="calHeaderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#14b8a6" />
          <stop offset="100%" stopColor="#0f766e" />
        </linearGradient>
        <linearGradient id="calBodyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#f0fdfa" />
          <stop offset="100%" stopColor="#ccfbf1" />
        </linearGradient>
      </defs>

      <g filter="url(#calShadow)">
        {/* Rear calendar page thickness for 3D look */}
        <rect x="23" y="24" width="58" height="52" rx="10" fill="#0d9488" opacity="0.4" />

        {/* Calendar Body Surface */}
        <rect x="20" y="22" width="60" height="52" rx="9" fill="url(#calBodyGrad)" />

        {/* Top Header Strip */}
        <path
          d="M20 31 C20 26 24 22 29 22 L71 22 C76 22 80 26 80 31 L80 37 L20 37 Z"
          fill="url(#calHeaderGrad)"
        />

        {/* Top Binder Rings */}
        <rect x="33" y="15" width="5" height="12" rx="2.5" fill="#334155" />
        <rect x="34" y="16" width="3" height="10" rx="1.5" fill="#94a3b8" />

        <rect x="62" y="15" width="5" height="12" rx="2.5" fill="#334155" />
        <rect x="63" y="16" width="3" height="10" rx="1.5" fill="#94a3b8" />

        {/* Calendar Day Grid (4 columns x 3 rows of rounded dots) */}
        {/* Row 1 */}
        <circle cx="33" cy="45" r="3.5" fill="#0d9488" />
        <circle cx="44" cy="45" r="3.5" fill="#0d9488" />
        <circle cx="55" cy="45" r="3.5" fill="#0d9488" />
        <circle cx="66" cy="45" r="3.5" fill="#0d9488" />

        {/* Row 2 */}
        <circle cx="33" cy="55" r="3.5" fill="#0d9488" />
        <circle cx="44" cy="55" r="3.5" fill="#0d9488" />
        <circle cx="55" cy="55" r="3.5" fill="#14b8a6" />
        {/* Highlighted Today circle with ring */}
        <circle cx="66" cy="55" r="5" fill="#2dd4bf" />
        <circle cx="66" cy="55" r="3" fill="#042f2e" />

        {/* Row 3 */}
        <circle cx="33" cy="65" r="3.5" fill="#0d9488" />
        <circle cx="44" cy="65" r="3.5" fill="#0d9488" />
        <circle cx="55" cy="65" r="3.5" fill="#0d9488" />
        <circle cx="66" cy="65" r="3.5" fill="#99f6e4" />
      </g>
    </svg>
  );
}

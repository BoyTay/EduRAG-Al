import {
  Calendar3D,
  GraduationCap3D,
  OpenBook3D,
  Trophy3D,
} from "./Illustrations3D";

interface QuestionCard {
  label: string;
  topic: string;
  badgeIcon: string;
  source: string;
  bgClass: string;
  borderClass: string;
  badgeClass: string;
  graphic: React.ReactNode;
}

const cards: QuestionCard[] = [
  {
    label: "Điều kiện xét tốt nghiệp",
    topic: "TỐT NGHIỆP",
    badgeIcon: "🎓",
    source: "Quy chế đào tạo tín chỉ",
    bgClass: "bg-[#eaf1fd] hover:bg-[#e2edfc]",
    borderClass: "border-blue-200/70",
    badgeClass: "text-blue-700",
    graphic: <GraduationCap3D className="h-16 w-20 shrink-0 drop-shadow-md" />,
  },
  {
    label: "Điều kiện nhận học bổng?",
    topic: "HỌC BỔNG",
    badgeIcon: "🏆",
    source: "Quy định công tác sinh viên",
    bgClass: "bg-[#fef8e7] hover:bg-[#fef4d8]",
    borderClass: "border-amber-200/70",
    badgeClass: "text-amber-700",
    graphic: <Trophy3D className="h-16 w-20 shrink-0 drop-shadow-md" />,
  },
  {
    label: "Quy định kỳ học phần?",
    topic: "HỌC LẠI",
    badgeIcon: "📖",
    source: "Hướng dẫn đăng ký học phần",
    bgClass: "bg-[#fef2e8] hover:bg-[#fee7d7]",
    borderClass: "border-orange-200/70",
    badgeClass: "text-orange-700",
    graphic: <OpenBook3D className="h-16 w-20 shrink-0 drop-shadow-md" />,
  },
  {
    label: "Lịch học và thi trong năm?",
    topic: "LỊCH HỌC",
    badgeIcon: "📅",
    source: "Kế hoạch năm học",
    bgClass: "bg-[#e6f7f5] hover:bg-[#d6f2ee]",
    borderClass: "border-teal-200/70",
    badgeClass: "text-teal-700",
    graphic: <Calendar3D className="h-16 w-20 shrink-0 drop-shadow-md" />,
  },
];

export function QuickQuestions({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {cards.map((card) => (
        <button
          key={card.label}
          onClick={() => onPick(card.label)}
          className={`group flex items-center justify-between rounded-2xl border ${card.borderClass} ${card.bgClass} p-4 text-left shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md active:translate-y-0 active:scale-[0.99] sm:p-4.5`}
        >
          {/* Text Content */}
          <div className="min-w-0 flex-1 pr-3">
            <span
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold tracking-wider ${card.badgeClass}`}
            >
              <span>{card.badgeIcon}</span>
              <span>{card.topic}</span>
            </span>

            <h3 className="mt-2 text-[15px] font-bold leading-snug text-slate-800">
              {card.label}
            </h3>

            <p className="mt-1 truncate text-xs text-slate-500">{card.source}</p>
          </div>

          {/* 3D Graphic */}
          <div className="shrink-0 transition-transform duration-300 group-hover:scale-105">
            {card.graphic}
          </div>
        </button>
      ))}
    </div>
  );
}

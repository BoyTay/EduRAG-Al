import { ArrowUp } from "@phosphor-icons/react";
import { useState } from "react";

export function ChatInput({
  onSend,
  loading,
}: {
  onSend: (question: string) => void;
  loading: boolean;
}) {
  const [value, setValue] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (value.trim() && !loading) {
      onSend(value.trim());
      setValue("");
    }
  };

  return (
    <form
      onSubmit={submit}
      className="relative z-10 px-4 pb-4 pt-1 sm:px-8"
    >
      <div className="mx-auto max-w-3xl rounded-2xl border border-slate-200/80 bg-white/90 p-2 shadow-[0_12px_32px_rgba(15,23,42,0.06)] backdrop-blur-md transition-all duration-200 focus-within:border-emerald-500/60 focus-within:ring-4 focus-within:ring-emerald-500/10">
        <div className="flex items-center gap-2 px-2 pt-1">
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Hỏi về quy chế, học vụ hoặc tài liệu..."
            className="h-10 min-w-0 flex-1 bg-transparent px-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={loading || !value.trim()}
            aria-label="Gửi câu hỏi"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white shadow-sm transition-all duration-200 hover:bg-emerald-500 hover:shadow-md active:scale-95 disabled:pointer-events-none disabled:opacity-40"
          >
            <ArrowUp size={18} weight="bold" />
          </button>
        </div>

        <div className="flex items-center justify-between px-3 pb-1 pt-1.5 text-[10px] text-slate-400">
          <span>EduRAG sẽ trích dẫn tài liệu khi có kết quả phù hợp.</span>
          <span className="hidden sm:block font-medium">Enter để gửi</span>
        </div>
      </div>
    </form>
  );
}

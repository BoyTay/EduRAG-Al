import { useEffect, useRef } from "react";
import { ChatInput } from "../components/chat/ChatInput";
import { ChatMessage } from "../components/chat/ChatMessage";
import { HeroAcademicGraphic } from "../components/chat/Illustrations3D";
import { QuickQuestions } from "../components/chat/QuickQuestions";
import { useChatStore } from "../stores/chatStore";

export function Chat() {
  const { messages, send, isLoading, setFeedback } = useChatStore();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages.length, isLoading]);

  return (
    <section className="flex h-full flex-col">
      {/* Scrollable Chat Area */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 pb-6 md:px-8">
        <div className="mx-auto max-w-4xl">
          {messages.length === 0 ? (
            <div className="space-y-3.5">
              {/* Hero Banner with Academic Graphic */}
              <div className="relative flex items-center justify-between overflow-hidden rounded-[2rem] border border-teal-100/90 bg-gradient-to-r from-[#e5f7f2]/95 via-[#effaf5]/90 to-[#f6fcf9]/95 p-5 shadow-sm backdrop-blur-md sm:p-6 md:p-7">
                <div className="min-w-0 max-w-xl">
                  <p className="mb-2 text-[10px] font-bold tracking-[0.18em] text-teal-700">
                    TRỢ LÝ HỌC VỤ
                  </p>
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl md:text-[32px] md:leading-tight">
                    Xin chào!
                    <br />
                    Tôi có thể giúp gì cho bạn?
                  </h1>
                  <p className="mt-2.5 text-xs leading-relaxed text-slate-600 sm:text-sm">
                    Tra cứu nhanh quy chế đào tạo, học phí, học bổng và những văn bản học vụ của Khoa.
                  </p>
                </div>

                {/* 3D Academic Graphic on Right */}
                <div className="hidden shrink-0 sm:block">
                  <HeroAcademicGraphic className="h-36 w-52 drop-shadow-sm md:h-40 md:w-60" />
                </div>
              </div>

              {/* 4 Quick Question Cards */}
              <QuickQuestions onPick={(question) => void send(question)} />

              {/* Disclaimer */}
              <p className="pt-2 text-center text-[11px] text-slate-400">
                Hãy kiểm tra lại các quy định quan trọng trước khi thực hiện thủ tục.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {messages.map((message, index) => (
                <ChatMessage
                  key={`${message.id ?? "local"}-${index}`}
                  message={message}
                  onFeedback={setFeedback}
                />
              ))}

              {isLoading && (
                <div className="flex items-center gap-3 rounded-2xl border border-teal-100 bg-white/80 px-4 py-3 text-sm text-slate-600 shadow-sm backdrop-blur-sm">
                  <span className="size-2 animate-ping rounded-full bg-emerald-500" />
                  <span>EduRAG đang tìm kiếm trong tài liệu...</span>
                </div>
              )}

              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      {/* Floating Chat Input Bar */}
      <ChatInput onSend={(question) => void send(question)} loading={isLoading} />
    </section>
  );
}

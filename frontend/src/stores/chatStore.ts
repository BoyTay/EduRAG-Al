import { create } from "zustand";
import { askStream, ChatStreamError, saveFeedback } from "../services/api";
import type { Message } from "../types";

interface ChatState {
  sessionId: string;
  messages: Message[];
  isLoading: boolean;
  setMessages: (messages: Message[]) => void;
  loadSession: (sessionId: string, messages: Message[]) => void;
  newChat: () => void;
  send: (question: string, documentFilename?: string) => Promise<void>;
  setFeedback: (messageId: number, feedback: "up" | "down") => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: crypto.randomUUID(),
  messages: [],
  isLoading: false,
  setMessages: (messages) => set({ messages }),
  loadSession: (sessionId, messages) => set({ sessionId, messages }),
  newChat: () => set({ sessionId: crypto.randomUUID(), messages: [] }),
  send: async (question, documentFilename) => {
    const current = get();
    set({ messages: [...current.messages, { role: "user", content: question }], isLoading: true });
    // Bong bóng trả lời chỉ xuất hiện khi có chữ đầu tiên, nên trong lúc truy hồi vẫn hiện
    // dòng "đang tìm kiếm". Chữ stream là bản nháp; kết quả "final" thay thế nó.
    let streaming = false;
    const withoutStreamingBubble = (messages: Message[]) => (streaming ? messages.slice(0, -1) : messages);
    try {
      const response = await askStream(question, current.sessionId, documentFilename, (text) => {
        set((state) => {
          if (!streaming) {
            streaming = true;
            return { messages: [...state.messages, { role: "assistant", content: text, streaming: true }] };
          }
          const messages = state.messages.slice();
          const last = messages[messages.length - 1];
          messages[messages.length - 1] = { ...last, content: last.content + text };
          return { messages };
        });
      });
      set((state) => ({
        sessionId: response.session_id,
        messages: [...withoutStreamingBubble(state.messages), {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          score: response.retrieval_score,
        }],
        isLoading: false,
      }));
    } catch (error) {
      const detail = error instanceof ChatStreamError ? error.detail : undefined;
      set((state) => ({
        messages: [...withoutStreamingBubble(state.messages), { role: "assistant", content: detail || "Không thể gửi câu hỏi lúc này. Vui lòng thử lại." }],
        isLoading: false,
      }));
    }
  },
  setFeedback: async (messageId, feedback) => {
    const previous = get().messages;
    set({ messages: previous.map((message) => message.id === messageId ? { ...message, feedback } : message) });
    try {
      await saveFeedback(messageId, feedback);
    } catch (error) {
      set({ messages: previous });
      throw error;
    }
  },
}));

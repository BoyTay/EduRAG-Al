import { create } from "zustand";
import { ask, saveFeedback } from "../services/api";
import type { Message } from "../types";

interface ChatState {
  sessionId: string;
  messages: Message[];
  isLoading: boolean;
  setMessages: (messages: Message[]) => void;
  loadSession: (sessionId: string, messages: Message[]) => void;
  newChat: () => void;
  send: (question: string) => Promise<void>;
  setFeedback: (messageId: number, feedback: "up" | "down") => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: crypto.randomUUID(),
  messages: [],
  isLoading: false,
  setMessages: (messages) => set({ messages }),
  loadSession: (sessionId, messages) => set({ sessionId, messages }),
  newChat: () => set({ sessionId: crypto.randomUUID(), messages: [] }),
  send: async (question) => {
    const current = get();
    set({ messages: [...current.messages, { role: "user", content: question }], isLoading: true });
    try {
      const response = await ask(question, current.sessionId);
      set((state) => ({
        sessionId: response.session_id,
        messages: [...state.messages, {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          score: response.retrieval_score,
        }],
        isLoading: false,
      }));
    } catch {
      set((state) => ({
        messages: [...state.messages, { role: "assistant", content: "Không thể gửi câu hỏi lúc này. Vui lòng thử lại." }],
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

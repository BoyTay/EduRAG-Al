"""
app.py - Streamlit Frontend chính (v2.0)
Giao diện chat cho sinh viên tra cứu tài liệu.
Nâng cấp: Glassmorphism UI, avatar, typing indicator, auto-scroll,
           admin login với username/password, feedback 👍/👎.
"""

import os
import uuid
import requests
import streamlit as st
from datetime import datetime

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EduRAG – Chatbot Hỗ Trợ Sinh Viên",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        min-height: 100vh;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.97);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* ─── Chat Bubbles ─── */
    .chat-row {
        display: flex;
        margin: 12px 0;
        animation: fadeInUp 0.35s ease-out;
    }
    .chat-row.user {
        justify-content: flex-end;
    }
    .chat-row.bot {
        justify-content: flex-start;
    }

    .chat-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1em;
        flex-shrink: 0;
        margin-top: 4px;
    }
    .chat-avatar.user-avatar {
        background: linear-gradient(135deg, #667eea, #764ba2);
        margin-left: 10px;
        order: 2;
    }
    .chat-avatar.bot-avatar {
        background: linear-gradient(135deg, #11998e, #38ef7d);
        margin-right: 10px;
    }

    .chat-bubble {
        padding: 14px 18px;
        line-height: 1.7;
        max-width: 75%;
        word-wrap: break-word;
    }
    .chat-bubble.user-bubble {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-radius: 18px 18px 4px 18px;
        box-shadow: 0 4px 18px rgba(102, 126, 234, 0.35);
    }
    .chat-bubble.bot-bubble {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #e8e8f0;
        border-radius: 18px 18px 18px 4px;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
    }

    .chat-meta {
        font-size: 0.72em;
        color: rgba(255,255,255,0.35);
        margin-top: 6px;
    }
    .chat-meta.user-meta {
        text-align: right;
    }

    /* ─── Source Badges ─── */
    .source-badge {
        display: inline-block;
        background: rgba(102, 126, 234, 0.15);
        border: 1px solid rgba(102, 126, 234, 0.35);
        color: #a5b4fc;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.78em;
        margin: 3px 4px 0 0;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .source-badge:hover {
        background: rgba(102, 126, 234, 0.3);
        transform: translateY(-1px);
    }

    /* ─── Score Indicator ─── */
    .score-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 600;
    }
    .score-good { background: rgba(74,222,128,0.15); color: #4ade80; }
    .score-medium { background: rgba(251,191,36,0.15); color: #fbbf24; }
    .score-low { background: rgba(248,113,113,0.15); color: #f87171; }

    /* ─── Header ─── */
    .main-header {
        text-align: center;
        padding: 24px 0 12px;
    }

    .main-title {
        font-size: 2.6em;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #f093fb, #38ef7d);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradientShift 4s ease infinite;
        margin-bottom: 4px;
    }

    .main-subtitle {
        color: rgba(255,255,255,0.5);
        font-size: 1em;
        font-weight: 300;
        letter-spacing: 0.5px;
    }

    @keyframes gradientShift {
        0%, 100% { background-position: 0% center; }
        50% { background-position: 100% center; }
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ─── Typing Indicator ─── */
    .typing-indicator {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 14px 20px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 18px 18px 18px 4px;
        backdrop-filter: blur(12px);
        max-width: 120px;
    }
    .typing-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: rgba(165, 180, 252, 0.7);
        animation: typingBounce 1.4s infinite ease-in-out;
    }
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typingBounce {
        0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
        40% { transform: scale(1); opacity: 1; }
    }

    /* ─── Input area ─── */
    .stChatInput > div {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 16px !important;
    }

    /* ─── Buttons ─── */
    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 0.95em !important;
        transition: all 0.3s ease !important;
        width: 100%;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(102,126,234,0.45) !important;
    }

    /* ─── Metrics ─── */
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 10px;
    }

    /* ─── Login Card ─── */
    .login-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 40px 36px;
        max-width: 420px;
        margin: 60px auto;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        animation: fadeInUp 0.5s ease-out;
    }
    .login-title {
        text-align: center;
        font-size: 1.6em;
        font-weight: 700;
        color: #e8e8f0;
        margin-bottom: 8px;
    }
    .login-subtitle {
        text-align: center;
        color: rgba(255,255,255,0.45);
        font-size: 0.9em;
        margin-bottom: 28px;
    }

    /* ─── Divider ─── */
    hr {
        border-color: rgba(255,255,255,0.08) !important;
    }

    /* ─── Spinner ─── */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }

    /* ─── Empty state ─── */
    .empty-chat {
        text-align: center;
        padding: 50px 20px;
        color: rgba(255,255,255,0.4);
        animation: fadeInUp 0.5s ease-out;
    }

    .empty-chat-icon {
        font-size: 3.5em;
        margin-bottom: 12px;
        filter: drop-shadow(0 4px 12px rgba(102,126,234,0.3));
    }

    /* ─── Suggestion chips ─── */
    .suggestion-chip {
        display: inline-block;
        background: rgba(102,126,234,0.12);
        border: 1px solid rgba(102,126,234,0.3);
        color: #a5b4fc;
        padding: 8px 14px;
        border-radius: 20px;
        margin: 4px;
        cursor: pointer;
        font-size: 0.88em;
        transition: all 0.2s;
    }

    .suggestion-chip:hover {
        background: rgba(102,126,234,0.3);
        border-color: rgba(102,126,234,0.6);
    }

    /* ─── Status dot ─── */
    .status-dot {
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }
    .status-online { background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,0.5); }
    .status-offline { background: #f87171; box-shadow: 0 0 8px rgba(248,113,113,0.5); }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* ─── Sidebar brand ─── */
    .sidebar-brand {
        text-align: center;
        padding: 12px 0 6px;
    }
    .sidebar-brand-icon {
        font-size: 2.2em;
        margin-bottom: 4px;
    }
    .sidebar-brand-name {
        font-size: 1.3em;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .sidebar-brand-tag {
        color: rgba(255,255,255,0.4);
        font-size: 0.78em;
        font-weight: 300;
    }

    /* ─── Feedback Widget ─── */
    div[data-testid="stFeedback"] {
        padding: 0 !important;
        margin-top: -8px !important;
        margin-left: 48px !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stFeedback"] button {
        background: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 2px 6px !important;
        width: auto !important;
        min-width: 32px !important;
        box-shadow: none !important;
        transform: none !important;
        color: rgba(255, 255, 255, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stFeedback"] button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #a5b4fc !important;
        transform: scale(1.15) !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Initialization ─────────────────────────────────────────────

def init_session():
    """Khởi tạo session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False
    if "admin_display_name" not in st.session_state:
        st.session_state.admin_display_name = ""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"
    if "session_created" not in st.session_state:
        st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")


# ─── API Helpers ──────────────────────────────────────────────────────────────

def check_backend_health() -> dict | None:
    """Kiểm tra kết nối backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def send_chat(question: str, session_id: str) -> dict | None:
    """Gửi câu hỏi đến backend, nhận câu trả lời."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat",
            json={"question": question, "session_id": session_id},
            timeout=120,  # Timeout 2 phút cho LLM
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"Lỗi API: {resp.status_code} - {resp.text}")
            return None
    except requests.exceptions.Timeout:
        st.error("⏱️ Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại.")
        return None
    except Exception as e:
        st.error(f"❌ Lỗi kết nối backend: {str(e)}")
        return None


def send_feedback(message_id: int, feedback: str) -> bool:
    """Gửi feedback cho một tin nhắn."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat/{message_id}/feedback",
            json={"feedback": feedback},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def admin_login(username: str, password: str) -> dict | None:
    """Đăng nhập admin qua backend API."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/admin/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def get_admin_stats() -> dict | None:
    """Lấy thống kê hệ thống."""
    try:
        resp = requests.get(f"{BACKEND_URL}/admin/stats", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def get_history(session_id: str) -> list:
    """Lấy lịch sử hội thoại từ backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/history/{session_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
        return []
    except Exception:
        return []


# ─── Auto-scroll JavaScript ──────────────────────────────────────────────────

def inject_auto_scroll():
    """Inject JavaScript để tự cuộn xuống tin nhắn mới nhất."""
    st.markdown("""
    <script>
        const chatContainer = window.parent.document.querySelector('[data-testid="stVerticalBlock"]');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        // Fallback: scroll toàn bộ main content
        const main = window.parent.document.querySelector('.main');
        if (main) {
            main.scrollTop = main.scrollHeight;
        }
    </script>
    """, unsafe_allow_html=True)


# ─── Chat Page ────────────────────────────────────────────────────────────────

def render_chat_page():
    """Hiển thị trang chat chính."""
    # Header
    st.markdown("""
    <div class="main-header">
        <div class="main-title">🎓 EduRAG</div>
        <div class="main-subtitle">Trợ lý AI tra cứu quy chế đào tạo & tài liệu Khoa</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 1. Kiểm tra xem có câu hỏi chờ xử lý từ click gợi ý (suggestion) không
    if "pending_question" in st.session_state and st.session_state.pending_question:
        question = st.session_state.pop("pending_question")
        # Thêm vào lịch sử
        st.session_state.messages.append({
            "role": "user",
            "content": question,
            "time": datetime.now().strftime("%H:%M"),
        })

        # Gọi API
        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result = send_chat(question, st.session_state.session_id)

        if result:
            bot_msg = {
                "role": "bot",
                "content": result["answer"],
                "sources": result.get("sources", []),
                "retrieval_score": result.get("retrieval_score", 0),
                "message_id": result.get("message_id"),
                "time": datetime.now().strftime("%H:%M"),
            }
            st.session_state.messages.append(bot_msg)
        st.rerun()

    # Hiển thị lịch sử chat
    if not st.session_state.messages:
        # Empty state với gợi ý câu hỏi
        st.markdown("""
        <div class="empty-chat">
            <div class="empty-chat-icon">💬</div>
            <h3 style="color: rgba(255,255,255,0.6);">Xin chào! Tôi có thể giúp gì cho bạn?</h3>
            <p>Hãy đặt câu hỏi về quy chế đào tạo, tín chỉ, học phí, và các quy định của Khoa.</p>
        </div>
        """, unsafe_allow_html=True)

        # Gợi ý câu hỏi
        st.markdown("**💡 Gợi ý câu hỏi:**")
        suggestions = [
            "Điều kiện xét học bổng là gì?",
            "Quy định về nghỉ học và bảo lưu?",
            "Số tín chỉ tối thiểu mỗi học kỳ?",
            "Quy chế thi và điều kiện dự thi?",
            "Điều kiện tốt nghiệp đại học?",
        ]
        cols = st.columns(3)
        for i, suggestion in enumerate(suggestions):
            with cols[i % 3]:
                if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.pending_question = suggestion
                    st.rerun()
    else:
        # Render messages với avatar
        for idx, msg in enumerate(st.session_state.messages):
            role = msg["role"]
            content = msg["content"]
            msg_time = msg.get("time", "")

            if role == "user":
                st.markdown(f"""
                <div class="chat-row user">
                    <div class="chat-bubble user-bubble">
                        {content}
                        <div class="chat-meta user-meta">{msg_time}</div>
                    </div>
                    <div class="chat-avatar user-avatar">🧑‍🎓</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Bot message
                sources = msg.get("sources", [])
                score = msg.get("retrieval_score", 0)
                message_id = msg.get("message_id")

                # Score indicator
                if score >= 0.7:
                    score_class = "score-good"
                    score_label = "Độ tin cậy cao"
                elif score >= 0.4:
                    score_class = "score-medium"
                    score_label = "Độ tin cậy trung bình"
                else:
                    score_class = "score-low"
                    score_label = "Độ tin cậy thấp"

                # Source badges HTML
                sources_html = ""
                if sources:
                    sources_html = '<div style="margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08);"><small><strong>📚 Nguồn tham khảo:</strong></small><br>'
                    for src in sources:
                        fname = src.get("filename", "N/A")
                        page = src.get("page")
                        page_info = f" (tr.{page})" if page else ""
                        sources_html += f'<span class="source-badge">📄 {fname}{page_info}</span>'
                    sources_html += '</div>'

                st.markdown(f"""
                <div class="chat-row bot">
                    <div class="chat-avatar bot-avatar">🤖</div>
                    <div class="chat-bubble bot-bubble">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <strong style="color:#a5b4fc;">EduRAG</strong>
                            <span class="score-pill {score_class}">● {score_label} ({score:.2f})</span>
                        </div>
                        {content}
                        {sources_html}
                        <div class="chat-meta">{msg_time}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Feedback widget
                if message_id:
                    fb_key = f"feedback_msg_{message_id}_{idx}"
                    fb_val = st.feedback(
                        "thumbs",
                        key=fb_key,
                    )
                    if fb_val is not None:
                        fb_str = "up" if fb_val == 1 else "down"
                        if msg.get("feedback") != fb_str:
                            if send_feedback(message_id, fb_str):
                                st.session_state.messages[idx]["feedback"] = fb_str
                                st.toast("Cảm ơn bạn đã phản hồi! 🙏", icon="✨")

        # Auto-scroll
        inject_auto_scroll()

    # Input area sử dụng st.chat_input chính thức của Streamlit
    prompt = st.chat_input("Nhập câu hỏi của bạn...")
    if prompt:
        # Thêm câu hỏi vào hội thoại
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "time": datetime.now().strftime("%H:%M"),
        })

        # Gọi API lấy câu trả lời
        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result = send_chat(prompt, st.session_state.session_id)

        if result:
            bot_msg = {
                "role": "bot",
                "content": result["answer"],
                "sources": result.get("sources", []),
                "retrieval_score": result.get("retrieval_score", 0),
                "message_id": result.get("message_id"),
                "time": datetime.now().strftime("%H:%M"),
            }
            st.session_state.messages.append(bot_msg)

        st.rerun()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    """Hiển thị sidebar với thông tin và điều hướng."""
    with st.sidebar:
        # Brand
        st.markdown("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">🎓</div>
            <div class="sidebar-brand-name">EduRAG</div>
            <div class="sidebar-brand-tag">Chatbot AI Hỗ Trợ Sinh Viên</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Backend status
        health = check_backend_health()
        if health:
            st.markdown(
                '<span class="status-dot status-online"></span> **Backend: Online**',
                unsafe_allow_html=True,
            )
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📊 Chunks", health.get("vector_store_docs", 0))
            with col2:
                st.metric("🤖 Model", "Qwen2.5")
        else:
            st.markdown(
                '<span class="status-dot status-offline"></span> **Backend: Offline**',
                unsafe_allow_html=True,
            )
            st.warning("Chạy backend: `docker compose up`")

        st.markdown("---")

        # Navigation
        st.markdown("### 📌 Điều hướng")
        if st.button("💬 Trang Chat", use_container_width=True):
            st.session_state.current_page = "chat"
            st.rerun()

        if st.button("⚙️ Quản Trị", use_container_width=True):
            st.session_state.current_page = "admin"
            st.rerun()

        st.markdown("---")

        # Session info
        st.markdown("### 📋 Phiên hiện tại")
        st.code(st.session_state.session_id[:8] + "...", language=None)
        st.caption(f"🕐 Tạo lúc: {st.session_state.get('session_created', 'N/A')}")
        st.caption(f"💬 Số tin nhắn: {len(st.session_state.messages)}")

        # Actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Xóa chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")
                st.rerun()
        with col2:
            if st.button("🔄 Phiên mới", use_container_width=True):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")
                st.rerun()

        # Export chat
        if st.session_state.messages:
            st.markdown("---")
            export_text = _build_chat_export()
            st.download_button(
                label="📥 Xuất hội thoại",
                data=export_text,
                file_name=f"edurag_chat_{st.session_state.session_id[:8]}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown("---")
        st.caption("📚 EduRAG v2.0 | Qwen2.5-7B")


def _build_chat_export() -> str:
    """Tạo nội dung text để xuất hội thoại."""
    lines = [
        "=" * 50,
        "  LỊCH SỬ HỘI THOẠI - EduRAG",
        f"  Phiên: {st.session_state.session_id[:8]}",
        f"  Thời gian: {st.session_state.get('session_created', 'N/A')}",
        "=" * 50,
        "",
    ]
    for msg in st.session_state.messages:
        time_str = msg.get("time", "")
        if msg["role"] == "user":
            lines.append(f"[{time_str}] 🧑‍🎓 Sinh viên:")
            lines.append(f"  {msg['content']}")
        else:
            lines.append(f"[{time_str}] 🤖 EduRAG:")
            lines.append(f"  {msg['content']}")
            sources = msg.get("sources", [])
            if sources:
                src_names = [s.get("filename", "") for s in sources]
                lines.append(f"  📚 Nguồn: {', '.join(src_names)}")
            score = msg.get("retrieval_score", 0)
            lines.append(f"  📊 Độ tin cậy: {score:.2f}")
        lines.append("")
    lines.append("─" * 50)
    lines.append("Xuất bởi EduRAG v2.0")
    return "\n".join(lines)


# ─── Admin Page ───────────────────────────────────────────────────────────────

def render_admin_page():
    """Hiển thị trang quản trị tài liệu."""
    from admin_page import render_admin

    # Kiểm tra đăng nhập
    if not st.session_state.admin_logged_in:
        _render_admin_login()
        return

    # Đã đăng nhập → hiển thị admin panel
    col1, col2, col3 = st.columns([4, 2, 1])
    with col1:
        st.markdown("## ⚙️ Quản Trị Tài Liệu")
    with col2:
        display_name = st.session_state.get("admin_display_name", "Admin")
        st.markdown(
            f'<div style="text-align:right; padding-top:12px; color:rgba(255,255,255,0.6);">'
            f'👤 <strong>{display_name}</strong></div>',
            unsafe_allow_html=True,
        )
    with col3:
        if st.button("🚪 Đăng xuất"):
            st.session_state.admin_logged_in = False
            st.session_state.admin_display_name = ""
            st.rerun()

    render_admin(BACKEND_URL)


def _render_admin_login():
    """Form đăng nhập admin với username + password."""
    st.markdown("""
    <div class="login-card">
        <div style="text-align:center; font-size:2.5em; margin-bottom:12px;">🔐</div>
        <div class="login-title">Đăng Nhập Quản Trị</div>
        <div class="login-subtitle">Vui lòng nhập tài khoản để tiếp tục</div>
    </div>
    """, unsafe_allow_html=True)

    # Form nằm giữa trang
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        with st.form("admin_login_form"):
            username = st.text_input(
                "👤 Tên đăng nhập",
                placeholder="Nhập tên đăng nhập...",
                key="admin_username",
            )
            password = st.text_input(
                "🔑 Mật khẩu",
                type="password",
                placeholder="Nhập mật khẩu...",
                key="admin_pwd",
            )
            submitted = st.form_submit_button("🔓 Đăng nhập", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("❌ Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu!")
                else:
                    result = admin_login(username, password)
                    if result and result.get("success"):
                        st.session_state.admin_logged_in = True
                        st.session_state.admin_display_name = result.get("display_name", username)
                        st.success(f"✅ Đăng nhập thành công! Xin chào {result.get('display_name', username)}.")
                        st.rerun()
                    else:
                        st.error("❌ Sai tên đăng nhập hoặc mật khẩu!")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_session()
    render_sidebar()

    if st.session_state.current_page == "chat":
        render_chat_page()
    elif st.session_state.current_page == "admin":
        render_admin_page()


if __name__ == "__main__":
    main()

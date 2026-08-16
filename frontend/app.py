"""
app.py - Streamlit Frontend chính
Giao diện chat cho sinh viên tra cứu tài liệu.
"""

import os
import uuid
import requests
import streamlit as st
from datetime import datetime

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_PASSWORD = "admin123"  # Thay đổi mật khẩu tại đây

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
        background: rgba(15, 12, 41, 0.95);
        border-right: 1px solid rgba(255,255,255,0.1);
    }

    /* Chat messages */
    .user-message {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 14px 18px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0;
        max-width: 80%;
        float: right;
        clear: both;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        line-height: 1.6;
    }

    .bot-message {
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #e8e8f0;
        padding: 14px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 85%;
        float: left;
        clear: both;
        backdrop-filter: blur(10px);
        line-height: 1.7;
    }

    .message-container {
        overflow: hidden;
        margin-bottom: 16px;
    }

    /* Source badges */
    .source-badge {
        display: inline-block;
        background: rgba(102, 126, 234, 0.2);
        border: 1px solid rgba(102, 126, 234, 0.4);
        color: #a5b4fc;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.78em;
        margin: 3px 3px 0 0;
        font-weight: 500;
    }

    /* Header */
    .main-header {
        text-align: center;
        padding: 20px 0 10px;
    }

    .main-title {
        font-size: 2.4em;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 4px;
    }

    .main-subtitle {
        color: rgba(255,255,255,0.55);
        font-size: 1em;
        font-weight: 300;
    }

    /* Input area */
    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 12px !important;
        color: white !important;
        padding: 12px 16px !important;
        font-size: 1em !important;
    }

    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102,126,234,0.3) !important;
    }

    /* Buttons */
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
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(102,126,234,0.5) !important;
    }

    /* Metrics */
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 10px;
    }

    /* Divider */
    hr {
        border-color: rgba(255,255,255,0.1) !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }

    /* Score indicator */
    .score-good { color: #4ade80; }
    .score-medium { color: #fbbf24; }
    .score-low { color: #f87171; }

    /* Empty state */
    .empty-chat {
        text-align: center;
        padding: 60px 20px;
        color: rgba(255,255,255,0.4);
    }

    .empty-chat-icon {
        font-size: 4em;
        margin-bottom: 16px;
    }

    /* Scrollable chat area */
    .chat-container {
        max-height: 60vh;
        overflow-y: auto;
        padding: 10px;
        scroll-behavior: smooth;
    }

    /* Suggestion chips */
    .suggestion-chip {
        display: inline-block;
        background: rgba(102,126,234,0.15);
        border: 1px solid rgba(102,126,234,0.35);
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
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"


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


def get_history(session_id: str) -> list:
    """Lấy lịch sử hội thoại từ backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/history/{session_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
        return []
    except Exception:
        return []


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
        st.session_state.messages.append({"role": "user", "content": question})

        # Gọi API
        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result = send_chat(question, st.session_state.session_id)

        if result:
            bot_msg = {
                "role": "bot",
                "content": result["answer"],
                "sources": result.get("sources", []),
                "retrieval_score": result.get("retrieval_score", 0),
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
        # Render messages
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                st.markdown(f"""
                <div class="message-container">
                    <div class="user-message">
                        <strong>🧑‍🎓 Bạn</strong><br>{content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Bot message
                sources = msg.get("sources", [])
                score = msg.get("retrieval_score", 0)

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
                    sources_html = "<br><br><small><strong>📚 Nguồn tham khảo:</strong></small><br>"
                    for src in sources:
                        fname = src.get("filename", "N/A")
                        page = src.get("page")
                        page_info = f" (tr.{page})" if page else ""
                        sources_html += f'<span class="source-badge">📄 {fname}{page_info}</span>'

                st.markdown(f"""
                <div class="message-container">
                    <div class="bot-message">
                        <strong>🤖 EduRAG</strong>
                        <span class="{score_class}" style="font-size:0.8em; float:right;">
                            ● {score_label} ({score:.2f})
                        </span>
                        <br><br>{content}
                        {sources_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Input area sử dụng st.chat_input chính thức của Streamlit
    prompt = st.chat_input("Nhập câu hỏi của bạn...")
    if prompt:
        # Thêm câu hỏi vào hội thoại
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Gọi API lấy câu trả lời
        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result = send_chat(prompt, st.session_state.session_id)

        if result:
            bot_msg = {
                "role": "bot",
                "content": result["answer"],
                "sources": result.get("sources", []),
                "retrieval_score": result.get("retrieval_score", 0),
            }
            st.session_state.messages.append(bot_msg)

        st.rerun()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    """Hiển thị sidebar với thông tin và điều hướng."""
    with st.sidebar:
        st.markdown("## 🎓 EduRAG")
        st.markdown("*Chatbot AI Hỗ Trợ Sinh Viên*")

        # Backend status
        health = check_backend_health()
        if health:
            st.success(f"🟢 Backend: Online")
            st.info(f"📊 Tài liệu: {health.get('vector_store_docs', 0)} chunks")
        else:
            st.error("🔴 Backend: Offline")
            st.warning("Chạy backend: `uvicorn main:app --port 8000`")

        st.markdown("---")

        # Navigation
        st.markdown("### 📌 Menu")
        if st.button("💬 Trang Chat", use_container_width=True):
            st.session_state.current_page = "chat"
            st.rerun()

        if st.button("⚙️ Trang Admin", use_container_width=True):
            st.session_state.current_page = "admin"
            st.rerun()

        st.markdown("---")

        # Session info
        st.markdown("### 📋 Phiên hiện tại")
        st.code(st.session_state.session_id[:8] + "...", language=None)
        st.caption(f"Số tin nhắn: {len(st.session_state.messages)}")

        # Clear chat
        if st.button("🗑️ Xóa hội thoại", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

        st.markdown("---")
        st.caption("📚 EduRAG v1.0 | Qwen2.5-7B")


# ─── Admin Page ───────────────────────────────────────────────────────────────

def render_admin_page():
    """Hiển thị trang quản trị tài liệu."""
    from admin_page import render_admin

    # Kiểm tra đăng nhập
    if not st.session_state.admin_logged_in:
        st.markdown("## 🔐 Đăng nhập Admin")
        password = st.text_input("Mật khẩu:", type="password", key="admin_pwd")
        if st.button("Đăng nhập"):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("✅ Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("❌ Sai mật khẩu!")
        return

    # Đã đăng nhập → hiển thị admin panel
    col1, col2 = st.columns([5, 1])
    with col1:
        st.markdown("## ⚙️ Quản Trị Tài Liệu")
    with col2:
        if st.button("🚪 Đăng xuất"):
            st.session_state.admin_logged_in = False
            st.rerun()

    render_admin(BACKEND_URL)


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

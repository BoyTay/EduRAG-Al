"""
admin_page.py - Streamlit trang quản trị tài liệu (v3.0 – University Style)
Redesigned to match Stitch "EduRAG Admin Dashboard (University Style)".
Top bar with green shield, stat cards, two-column layout with knowledge base
and analytics sections.
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime


def _get_admin_colors():
    """Trả về bộ màu theo theme hiện tại."""
    is_dark = st.session_state.get("theme") == "dark"
    if is_dark:
        return {
            "card_bg": "#1e2035",
            "card_border": "#2d2f48",
            "text_primary": "#e8e8f0",
            "text_secondary": "#9a9ab0",
            "text_heading": "#f0f0f8",
            "accent": "#86bc42",
            "accent_dark": "#86bc42",
            "badge_bg": "#2a3d15",
            "badge_color": "#baf472",
            "progress_bg": "#2a2c45",
            "hover_bg": "#242640",
            "drop_bg": "#1a1b2e",
            "drop_text": "#e8e8f0",
            "drop_sub": "#9a9ab0",
            "divider": "#2d2f48",
            "shadow": "rgba(0,0,0,0.2)",
            "icon_bg": "#2a3d15",
            "icon_color": "#86bc42",
            "fb_good": "#86bc42",
            "fb_bad": "#ef4444",
        }
    return {
        "card_bg": "#ffffff",
        "card_border": "#c3c9b4",
        "text_primary": "#151c27",
        "text_secondary": "#434939",
        "text_heading": "#151c27",
        "accent": "#406900",
        "accent_dark": "#406900",
        "badge_bg": "#baf472",
        "badge_color": "#2f4f00",
        "progress_bg": "#dce2f3",
        "hover_bg": "#f0f3ff",
        "drop_bg": "#f9f9ff",
        "drop_text": "#151c27",
        "drop_sub": "#434939",
        "divider": "#dce2f3",
        "shadow": "rgba(0,0,0,0.06)",
        "icon_bg": "#baf472",
        "icon_color": "#406900",
        "fb_good": "#406900",
        "fb_bad": "#ba1a1a",
    }


def render_admin(backend_url: str):
    """Render toàn bộ giao diện admin (University Style)."""

    # ─── Top Bar ──────────────────────────────────────────────────────────────
    _render_admin_topbar()

    # ─── Stat Cards Row ───────────────────────────────────────────────────────
    stats = _fetch_stats(backend_url)
    health = _fetch_health(backend_url)
    _render_stat_cards(stats, health)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ─── Two Column Layout ────────────────────────────────────────────────────
    col_left, col_right = st.columns([7, 5])

    with col_left:
        _render_knowledge_base(backend_url)

    with col_right:
        _render_feedback_stats(stats)
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        _render_recent_history(backend_url)


# ─── Admin Top Bar ────────────────────────────────────────────────────────────

def _render_admin_topbar():
    """Top navigation bar for admin dashboard."""
    admin_name = st.session_state.get("admin_display_name", "Admin")
    c = _get_admin_colors()

    st.markdown(f"""
    <div style="
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0 16px 0;
        border-bottom: 1px solid {c['card_border']};
        margin-bottom: 18px;
    ">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 22px; color: {c['accent']};">🛡️</span>
            <span style="font-size: 20px; font-weight: 700; color: {c['accent']};">Bảng quản trị EduRAG</span>
            <span style="
                background: {c['badge_bg']};
                color: {c['badge_color']};
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.04em;
            ">Admin</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: {c['badge_bg']};
                color: {c['badge_color']};
                padding: 4px 12px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 600;
            ">
                <span style="width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 6px #22c55e;"></span>
                Hệ thống trực tuyến
            </span>
            <span style="font-size: 13px; font-weight: 600; color: {c['text_primary']};">👤 {admin_name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Stat Cards ───────────────────────────────────────────────────────────────

def _render_stat_cards(stats: dict | None, health: dict | None):
    """Render 4 stat cards in a row."""
    c = _get_admin_colors()
    total_docs = stats.get("total_documents", 0) if stats else 0
    total_chunks = health.get("vector_store_docs", 0) if health else (stats.get("total_chunks", 0) if stats else 0)
    total_messages = stats.get("total_messages", 0) if stats else 0

    fb_up = stats.get("total_feedback_up", 0) if stats else 0
    fb_down = stats.get("total_feedback_down", 0) if stats else 0
    total_fb = fb_up + fb_down
    satisfaction = int(fb_up / total_fb * 100) if total_fb > 0 else 0

    card_style = f"""
        background: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        position: relative;
        overflow: hidden;
        transition: box-shadow 0.2s;
        box-shadow: 0 1px 3px {c['shadow']};
    """
    label_style = f"font-size:13px; color:{c['text_secondary']}; font-weight:400;"
    value_style = f"font-size:28px; font-weight:700; color:{c['accent']}; line-height:1.2;"
    icon_style = f"""
        width:32px; height:32px; border-radius:50%;
        background:{c['icon_bg']}; display:flex; align-items:center;
        justify-content:center; font-size:16px; color:{c['icon_color']};
    """

    st.markdown(f"""
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
        <!-- Card 1: Tài liệu đã nạp -->
        <div style="{card_style}">
            <span style="{label_style}">Tài liệu đã nạp</span>
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <span style="{value_style}">{total_docs}</span>
                <div style="{icon_style}">📄</div>
            </div>
        </div>
        <!-- Card 2: Chunks vector -->
        <div style="{card_style}">
            <span style="{label_style}">Chunks vector</span>
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <span style="{value_style}">{total_chunks}</span>
                <div style="{icon_style}">📊</div>
            </div>
        </div>
        <!-- Card 3: Lượt chat -->
        <div style="{card_style}">
            <span style="{label_style}">Lượt chat</span>
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <span style="{value_style}">{total_messages}</span>
            </div>
        </div>
        <!-- Card 4: Đánh giá tốt -->
        <div style="{card_style}">
            <span style="{label_style}">Đánh giá tốt</span>
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <span style="{value_style}">{satisfaction}%</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Knowledge Base Section ───────────────────────────────────────────────────

def _render_knowledge_base(backend_url: str):
    """Left column: Knowledge Base with upload zone and document list."""
    c = _get_admin_colors()

    # Section card
    st.markdown(f"""
    <div style="
        background: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px {c['shadow']};
    ">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span style="font-size:20px; font-weight:600; color:{c['text_primary']};">Knowledge Base</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Rebuild index button
    col_spacer, col_rebuild = st.columns([3, 1])
    with col_rebuild:
        rebuild_clicked = st.button("🔄 Rebuild index", key="rebuild_idx_btn", use_container_width=True)

    if rebuild_clicked:
        with st.spinner("⏳ Đang rebuild... (có thể mất vài phút)"):
            try:
                rebuild_resp = requests.post(
                    f"{backend_url}/admin/rebuild-index",
                    timeout=600,
                )
                if rebuild_resp.status_code == 200:
                    result = rebuild_resp.json()
                    st.success(f"✅ {result['message']}")
                else:
                    st.error(f"❌ Lỗi rebuild: {rebuild_resp.text}")
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

    # Upload dropzone
    st.markdown(f"""
    <div style="
        border: 2px dashed #86bc42;
        border-radius: 12px;
        padding: 28px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: {c['drop_bg']};
        cursor: pointer;
        margin: 12px 0 16px;
        text-align: center;
        transition: background 0.2s;
    ">
        <span style="font-size:36px; color:{c['accent']}; margin-bottom:8px;">☁️</span>
        <p style="font-size:15px; font-weight:600; color:{c['drop_text']}; margin:0;">Kéo thả tài liệu vào đây hoặc click để tải lên</p>
        <p style="font-size:13px; color:{c['drop_sub']}; margin-top:4px;">Hỗ trợ PDF, TXT, DOCX (Max 50MB)</p>
    </div>
    """, unsafe_allow_html=True)

    # Actual Streamlit uploader (functional)
    uploaded_files = st.file_uploader(
        "Chọn file tài liệu:",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Chấp nhận file PDF, DOCX, TXT. Có thể chọn nhiều file.",
        key="doc_uploader",
        label_visibility="collapsed",
    )

    if uploaded_files:
        if st.button("⬆️ Upload & Nạp vào Hệ Thống", key="upload_btn", use_container_width=True):
            for file in uploaded_files:
                with st.spinner(f"⏳ Đang xử lý '{file.name}'..."):
                    try:
                        files = {"file": (file.name, file.getvalue(), file.type)}
                        resp = requests.post(
                            f"{backend_url}/admin/upload",
                            files=files,
                            timeout=300,
                        )
                        if resp.status_code == 200:
                            result = resp.json()
                            st.success(f"✅ {result['message']}")
                        else:
                            st.error(f"❌ Lỗi upload {file.name}: {resp.text}")
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")

    # Document list
    c = _get_admin_colors()
    st.markdown(f"""
    <div style="margin-top:12px; margin-bottom:8px;">
        <span style="font-size:11px; font-weight:600; letter-spacing:0.05em; text-transform:uppercase; color:{c['text_secondary']};">
            Tài liệu đã nạp
        </span>
    </div>
    """, unsafe_allow_html=True)

    _render_document_list(backend_url)


def _render_document_list(backend_url: str):
    """Render the document file list in university style."""
    c = _get_admin_colors()
    try:
        resp = requests.get(f"{backend_url}/admin/documents", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            documents = data.get("documents", [])

            if not documents:
                st.markdown(f"""
                <div style="text-align:center; padding:24px; color:{c['text_secondary']};">
                    <p>📭 Chưa có tài liệu nào</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                for doc in documents:
                    fname = doc.get("filename", "Unknown")
                    fsize = doc.get("file_size_kb", 0)
                    chunks = doc.get("chunk_count", 0)
                    uploaded_at = doc.get("uploaded_at", "")
                    try:
                        dt = datetime.fromisoformat(uploaded_at)
                        time_str = dt.strftime("Đã nạp %d/%m/%Y %H:%M")
                    except Exception:
                        time_str = f"Đã nạp {uploaded_at}" if uploaded_at else ""

                    # PDF icon in red
                    icon = "📕" if fname.lower().endswith(".pdf") else "📄"

                    st.markdown(f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        padding: 10px 12px;
                        border-radius: 10px;
                        transition: background 0.2s;
                        cursor: pointer;
                        margin-bottom: 4px;
                    " onmouseover="this.style.background='{c['hover_bg']}'" onmouseout="this.style.background='transparent'">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:28px;">{icon}</span>
                            <div>
                                <div style="font-size:13px; font-weight:600; color:{c['text_primary']};">{fname}</div>
                                <div style="font-size:11px; color:{c['text_secondary']};">{fsize:.1f} KB • {chunks} chunks • {time_str}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Delete section
                st.markdown("---")
                file_names = [doc["filename"] for doc in documents]
                selected_file = st.selectbox(
                    "Chọn file cần xóa:",
                    file_names,
                    key="delete_selector",
                )
                if selected_file:
                    if st.button(f"🗑️ Xóa '{selected_file}'", key="delete_btn", use_container_width=True):
                        with st.spinner("Đang xóa..."):
                            try:
                                del_resp = requests.delete(
                                    f"{backend_url}/admin/delete/{selected_file}",
                                    timeout=30,
                                )
                                if del_resp.status_code == 200:
                                    st.success(f"✅ Đã xóa {selected_file}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Lỗi xóa: {del_resp.text}")
                            except Exception as e:
                                st.error(f"❌ Lỗi: {str(e)}")
        else:
            st.error(f"Không thể lấy danh sách tài liệu: {resp.status_code}")
    except Exception as e:
        st.caption(f"⚠️ Không thể kết nối backend: {str(e)}")


# ─── Feedback Stats ───────────────────────────────────────────────────────────

def _render_feedback_stats(stats: dict | None):
    """Right column top: Feedback statistics with progress bars."""
    c = _get_admin_colors()
    fb_up = stats.get("total_feedback_up", 0) if stats else 0
    fb_down = stats.get("total_feedback_down", 0) if stats else 0
    total_fb = fb_up + fb_down
    pct_up = int(fb_up / total_fb * 100) if total_fb > 0 else 0
    pct_down = int(fb_down / total_fb * 100) if total_fb > 0 else 0
    empty_message = (
        f'<p style="font-size:13px;color:{c["text_secondary"]};margin:0;">Chưa có phản hồi nào để thống kê.</p>'
        if total_fb == 0 else ""
    )

    html_content = (
        f'<div style="background:{c["card_bg"]};border:1px solid {c["card_border"]};border-radius:12px;padding:20px;box-shadow:0 1px 3px {c["shadow"]};">' 
        f'<h3 style="font-size:18px;font-weight:600;color:{c["text_primary"]};margin:0 0 14px 0;">Thống kê feedback</h3>'
        f'{empty_message}'
        f'<div style="display:flex;justify-content:space-between;font-size:13px;font-weight:600;margin-bottom:4px;">'
        f'<span style="color:{c["text_primary"]};display:flex;align-items:center;gap:4px;">👍 Hài lòng</span>'
        f'<span style="color:{c["fb_good"]};">{pct_up}%</span>'
        f'</div>'
        f'<div style="width:100%;height:8px;background:{c["progress_bg"]};border-radius:999px;overflow:hidden;margin-bottom:14px;">'
        f'<div style="height:100%;background:{c["fb_good"]};width:{pct_up}%;border-radius:999px;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:13px;font-weight:600;margin-bottom:4px;">'
        f'<span style="color:{c["text_primary"]};display:flex;align-items:center;gap:4px;">👎 Không hài lòng</span>'
        f'<span style="color:{c["fb_bad"]};">{pct_down}%</span>'
        f'</div>'
        f'<div style="width:100%;height:8px;background:{c["progress_bg"]};border-radius:999px;overflow:hidden;">'
        f'<div style="height:100%;background:{c["fb_bad"]};width:{pct_down}%;border-radius:999px;"></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html_content, unsafe_allow_html=True)


# ─── Recent Chat History ─────────────────────────────────────────────────────

def _render_recent_history(backend_url: str):
    """Right column bottom: Recent conversation history."""
    c = _get_admin_colors()
    token = st.session_state.get("auth_token", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # Try to fetch recent sessions from backend
    history_items = []
    try:
        sessions_resp = requests.get(f"{backend_url}/sessions", headers=headers, timeout=10)
        if sessions_resp.status_code == 200:
            sessions_data = sessions_resp.json()
            sessions = sessions_data.get("sessions", [])

            for session_id in sessions[:4]:
                try:
                    hist_resp = requests.get(
                        f"{backend_url}/history/{session_id}",
                        headers=headers,
                        timeout=5,
                    )
                    if hist_resp.status_code == 200:
                        messages = hist_resp.json().get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            question = last_msg.get("user_message", "")[:60]
                            timestamp = last_msg.get("timestamp", "")
                            feedback = last_msg.get("feedback", "")
                            user_id = session_id[:4]
                            if question:
                                history_items.append({
                                    "question": question,
                                    "time": timestamp,
                                    "user_id": user_id,
                                    "feedback": feedback,
                                })
                except Exception:
                    pass
    except Exception:
        pass

    # Không hiển thị dữ liệu mẫu: dashboard chỉ phản ánh dữ liệu thật.
    if not history_items:
        items_html = f'<p style="font-size:13px;color:{c["text_secondary"]};margin:0;">Chưa có hội thoại nào.</p>'
    else:
        items_html = ""

    for item in history_items:
        q = item["question"]
        t = item["time"]
        uid = item["user_id"]
        fb = item["feedback"]

        if fb == "up":
            fb_icon = "😊"
            fb_color = c["fb_good"]
        elif fb == "down":
            fb_icon = "😞"
            fb_color = c["fb_bad"]
        else:
            fb_icon = "😐"
            fb_color = c["text_secondary"]

        items_html += f"""<div style="border-bottom:1px solid {c['divider']};padding-bottom:10px;margin-bottom:10px;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:3px;">
<span style="font-size:13px;font-weight:600;color:{c['text_primary']};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80%;">{q}</span>
<span style="font-size:14px;color:{fb_color};">{fb_icon}</span>
</div>
<span style="font-size:11px;color:{c['text_secondary']};">{t} • User ID: {uid}</span>
</div>"""

    full_history_html = f"""<div style="background:{c['card_bg']};border:1px solid {c['card_border']};border-radius:12px;padding:20px;box-shadow:0 1px 3px {c['shadow']};">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
<h3 style="font-size:18px;font-weight:600;color:{c['text_primary']};margin:0;">Lịch sử hội thoại gần đây</h3>
<span style="font-size:13px;font-weight:600;color:{c['accent']};cursor:pointer;">Xem tất cả</span>
</div>
{items_html}
</div>"""

    st.markdown(full_history_html, unsafe_allow_html=True)


# ─── API Helpers ──────────────────────────────────────────────────────────────

def _fetch_stats(backend_url: str) -> dict | None:
    """Fetch admin stats from backend."""
    try:
        resp = requests.get(f"{backend_url}/admin/stats", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _fetch_health(backend_url: str) -> dict | None:
    """Fetch health check from backend."""
    try:
        resp = requests.get(f"{backend_url}/health", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None

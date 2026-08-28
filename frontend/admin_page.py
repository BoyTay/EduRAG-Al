"""
admin_page.py - Streamlit trang quản trị tài liệu (v2.0)
Cho phép upload nhiều file, xem bảng tài liệu, xóa, rebuild index,
và hiển thị dashboard thống kê hệ thống.
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime


def render_admin(backend_url: str):
    """Render toàn bộ giao diện admin."""

    # ─── Tabs ─────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload Tài Liệu",
        "📋 Danh Sách Tài Liệu",
        "📊 Thống Kê",
        "🔧 Công Cụ",
    ])

    # ─── Tab 1: Upload ─────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### 📤 Upload Tài Liệu Mới")
        st.info(
            "Hỗ trợ file **PDF** và **DOCX**. "
            "Có thể chọn **nhiều file** cùng lúc. "
            "File sẽ được tự động phân đoạn và đưa vào hệ thống."
        )

        uploaded_files = st.file_uploader(
            "Chọn file tài liệu (kéo thả hoặc nhấn để chọn):",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            help="Chấp nhận file PDF hoặc DOCX. Có thể chọn nhiều file.",
            key="doc_uploader",
        )

        if uploaded_files:
            # Preview thông tin các file đã chọn
            st.markdown(f"**📁 Đã chọn {len(uploaded_files)} file:**")

            preview_data = []
            for f in uploaded_files:
                preview_data.append({
                    "📄 Tên file": f.name,
                    "💾 Kích thước": f"{f.size / 1024:.1f} KB",
                    "📁 Định dạng": f.type.split("/")[-1].upper() if f.type else "N/A",
                })
            st.dataframe(
                pd.DataFrame(preview_data),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")

            description = st.text_area(
                "Mô tả tài liệu (áp dụng cho upload đơn lẻ):",
                placeholder="Ví dụ: Quy chế đào tạo đại học hệ chính quy năm 2024",
                height=68,
                key="doc_description",
            )

            if st.button("⬆️ Upload & Nạp vào Hệ Thống", key="upload_btn", use_container_width=True):
                if len(uploaded_files) == 1:
                    # Upload đơn (có description)
                    _upload_single(backend_url, uploaded_files[0], description)
                else:
                    # Upload nhiều file
                    _upload_multiple(backend_url, uploaded_files)

    # ─── Tab 2: Danh sách tài liệu ─────────────────────────────────────────────
    with tab2:
        st.markdown("### 📋 Danh Sách Tài Liệu Đã Nạp")
        _render_document_list(backend_url)

    # ─── Tab 3: Thống kê ────────────────────────────────────────────────────────
    with tab3:
        st.markdown("### 📊 Dashboard Thống Kê")
        _render_stats_dashboard(backend_url)

    # ─── Tab 4: Công cụ ────────────────────────────────────────────────────────
    with tab4:
        st.markdown("### 🔧 Công Cụ Quản Trị")
        _render_tools(backend_url)


# ─── Upload Helpers ───────────────────────────────────────────────────────────

def _upload_single(backend_url: str, file, description: str):
    """Upload một file duy nhất."""
    with st.spinner(f"⏳ Đang xử lý '{file.name}'... (có thể mất vài phút)"):
        try:
            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {}
            if description.strip():
                data["description"] = description.strip()

            resp = requests.post(
                f"{backend_url}/admin/upload",
                files=files,
                data=data,
                timeout=300,
            )

            if resp.status_code == 200:
                result = resp.json()
                st.success(f"✅ {result['message']}")
                st.info(
                    f"📊 Đã tạo **{result['chunk_count']}** chunks | "
                    f"💾 {result['file_size_kb']:.1f} KB"
                )
                st.balloons()
            else:
                error_detail = resp.json().get("detail", resp.text)
                st.error(f"❌ Lỗi upload: {error_detail}")

        except requests.exceptions.Timeout:
            st.error("⏱️ Timeout! File quá lớn hoặc server bận. Thử lại sau.")
        except Exception as e:
            st.error(f"❌ Lỗi kết nối: {str(e)}")


def _upload_multiple(backend_url: str, uploaded_files: list):
    """Upload nhiều file cùng lúc với progress bar."""
    progress_bar = st.progress(0, text="Đang chuẩn bị upload...")
    status_container = st.container()

    total = len(uploaded_files)
    success_count = 0
    fail_count = 0
    results_display = []

    for i, file in enumerate(uploaded_files):
        progress = (i + 1) / total
        progress_bar.progress(progress, text=f"⏳ Đang xử lý {file.name}... ({i+1}/{total})")

        try:
            files = {"file": (file.name, file.getvalue(), file.type)}
            resp = requests.post(
                f"{backend_url}/admin/upload",
                files=files,
                timeout=300,
            )

            if resp.status_code == 200:
                result = resp.json()
                results_display.append({
                    "📄 File": file.name,
                    "Trạng thái": "✅ Thành công",
                    "Chunks": result.get("chunk_count", 0),
                    "Kích thước": f"{result.get('file_size_kb', 0):.1f} KB",
                })
                success_count += 1
            else:
                error = resp.json().get("detail", "Lỗi không xác định")
                results_display.append({
                    "📄 File": file.name,
                    "Trạng thái": f"❌ {error[:50]}",
                    "Chunks": 0,
                    "Kích thước": f"{file.size/1024:.1f} KB",
                })
                fail_count += 1

        except Exception as e:
            results_display.append({
                "📄 File": file.name,
                "Trạng thái": f"❌ {str(e)[:50]}",
                "Chunks": 0,
                "Kích thước": f"{file.size/1024:.1f} KB",
            })
            fail_count += 1

    progress_bar.progress(1.0, text="✅ Hoàn tất!")

    # Hiển thị kết quả
    with status_container:
        if fail_count == 0:
            st.success(f"✅ Tất cả {total} file đã upload thành công!")
            st.balloons()
        else:
            st.warning(f"⚠️ {success_count}/{total} thành công, {fail_count} thất bại")

        st.dataframe(
            pd.DataFrame(results_display),
            use_container_width=True,
            hide_index=True,
        )


# ─── Document List ────────────────────────────────────────────────────────────

def _render_document_list(backend_url: str):
    """Hiển thị danh sách tài liệu dạng bảng."""

    col_refresh, col_search = st.columns([1, 3])
    with col_refresh:
        st.button("🔄 Làm mới", key="refresh_docs", use_container_width=True)
    with col_search:
        search_query = st.text_input(
            "🔍 Tìm kiếm",
            placeholder="Nhập tên file để lọc...",
            key="doc_search",
            label_visibility="collapsed",
        )

    try:
        resp = requests.get(f"{backend_url}/admin/documents", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            documents = data.get("documents", [])
            total = data.get("total", 0)

            # Lọc theo search query
            if search_query:
                documents = [
                    d for d in documents
                    if search_query.lower() in d["filename"].lower()
                ]

            st.info(f"📚 Tổng cộng: **{total}** tài liệu" + (
                f" (hiển thị {len(documents)} kết quả)" if search_query else ""
            ))

            if not documents:
                st.markdown("""
                <div style="text-align:center; padding:40px; color:rgba(255,255,255,0.5);">
                    <h3>📭 Chưa có tài liệu nào</h3>
                    <p>Upload tài liệu ở tab <strong>Upload Tài Liệu</strong></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Hiển thị bảng dataframe
                df_data = []
                for doc in documents:
                    uploaded_at = doc["uploaded_at"]
                    try:
                        dt = datetime.fromisoformat(uploaded_at)
                        uploaded_at = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass

                    df_data.append({
                        "📄 Tên file": doc["filename"],
                        "📁 Loại": doc["file_type"].upper(),
                        "📊 Chunks": doc["chunk_count"],
                        "💾 Kích thước": f"{doc['file_size_kb']:.1f} KB",
                        "📅 Ngày upload": uploaded_at,
                        "📝 Mô tả": doc.get("description") or "—",
                    })

                st.dataframe(
                    pd.DataFrame(df_data),
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 40 + len(df_data) * 35),
                )

                # Xóa tài liệu
                st.markdown("---")
                st.markdown("#### 🗑️ Xóa tài liệu")
                file_names = [doc["filename"] for doc in documents]
                selected_file = st.selectbox(
                    "Chọn file cần xóa:",
                    file_names,
                    key="delete_selector",
                )

                if selected_file:
                    col_del, col_cancel = st.columns(2)
                    with col_del:
                        if st.button(
                            f"🗑️ Xóa '{selected_file}'",
                            key="delete_btn",
                            use_container_width=True,
                        ):
                            st.session_state["confirm_delete"] = selected_file

                    # Xác nhận xóa
                    if st.session_state.get("confirm_delete") == selected_file:
                        st.warning(f"⚠️ Bạn chắc chắn muốn xóa **{selected_file}**? Không thể hoàn tác!")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Xác nhận xóa", key="confirm_del_yes", use_container_width=True):
                                with st.spinner("Đang xóa..."):
                                    try:
                                        del_resp = requests.delete(
                                            f"{backend_url}/admin/delete/{selected_file}",
                                            timeout=30,
                                        )
                                        if del_resp.status_code == 200:
                                            result = del_resp.json()
                                            st.success(f"✅ {result['message']}")
                                            st.session_state.pop("confirm_delete", None)
                                            st.rerun()
                                        else:
                                            error_detail = del_resp.json().get("detail", del_resp.text)
                                            st.error(f"❌ {error_detail}")
                                    except Exception as e:
                                        st.error(f"❌ Lỗi: {str(e)}")
                        with c2:
                            if st.button("❌ Hủy", key="confirm_del_no", use_container_width=True):
                                st.session_state.pop("confirm_delete", None)
                                st.rerun()
        else:
            st.error(f"Không thể lấy danh sách tài liệu: {resp.status_code}")

    except Exception as e:
        st.error(f"❌ Không thể kết nối backend: {str(e)}")


# ─── Stats Dashboard ─────────────────────────────────────────────────────────

def _render_stats_dashboard(backend_url: str):
    """Hiển thị dashboard thống kê hệ thống."""

    # System health
    try:
        health_resp = requests.get(f"{backend_url}/health", timeout=5)
        stats_resp = requests.get(f"{backend_url}/admin/stats", timeout=5)

        if health_resp.status_code == 200 and stats_resp.status_code == 200:
            health = health_resp.json()
            stats = stats_resp.json()

            # Row 1: Hệ thống
            st.markdown("#### 🖥️ Trạng Thái Hệ Thống")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("🟢 Backend", "Online")
            with c2:
                st.metric("🤖 LLM", health.get("llm_model", "N/A"))
            with c3:
                st.metric("⏱️ Uptime", stats.get("uptime", "N/A"))
            with c4:
                st.metric("📦 Embedding", "Vietnamese")

            st.markdown("---")

            # Row 2: Tài liệu
            st.markdown("#### 📚 Tài Liệu")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("📄 Số tài liệu", stats.get("total_documents", 0))
            with c2:
                st.metric("📊 Tổng chunks", stats.get("total_chunks", 0))
            with c3:
                last_upload = stats.get("last_upload")
                if last_upload:
                    try:
                        dt = datetime.fromisoformat(last_upload)
                        last_upload = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass
                st.metric("📅 Cập nhật cuối", last_upload or "Chưa có")

            st.markdown("---")

            # Row 3: Hội thoại
            st.markdown("#### 💬 Hoạt Động")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("🗣️ Phiên chat", stats.get("total_sessions", 0))
            with c2:
                st.metric("💬 Tổng tin nhắn", stats.get("total_messages", 0))
            with c3:
                st.metric("👍 Phản hồi tốt", stats.get("total_feedback_up", 0))
            with c4:
                st.metric("👎 Phản hồi xấu", stats.get("total_feedback_down", 0))

            # Tỷ lệ hài lòng
            fb_up = stats.get("total_feedback_up", 0)
            fb_down = stats.get("total_feedback_down", 0)
            total_fb = fb_up + fb_down
            if total_fb > 0:
                satisfaction = fb_up / total_fb * 100
                st.progress(
                    satisfaction / 100,
                    text=f"📈 Tỷ lệ hài lòng: {satisfaction:.1f}% ({fb_up}/{total_fb} phản hồi tích cực)",
                )
        else:
            st.error("Không thể lấy thống kê hệ thống")
    except Exception as e:
        st.error(f"❌ Không thể kết nối backend: {str(e)}")


# ─── Tools ────────────────────────────────────────────────────────────────────

def _render_tools(backend_url: str):
    """Hiển thị các công cụ quản trị."""

    # Rebuild index
    st.markdown("#### 🔄 Rebuild Vector Store")
    st.warning(
        "⚠️ **Cảnh báo:** Thao tác này sẽ xóa và tạo lại toàn bộ vector store "
        "từ thư mục `data/`. Có thể mất nhiều thời gian."
    )

    if st.button("🔨 Rebuild Index", key="rebuild_btn", use_container_width=True):
        with st.spinner("⏳ Đang rebuild... (có thể mất vài phút)"):
            try:
                rebuild_resp = requests.post(
                    f"{backend_url}/admin/rebuild-index",
                    timeout=600,
                )
                if rebuild_resp.status_code == 200:
                    result = rebuild_resp.json()
                    st.success(f"✅ {result['message']}")
                    st.info(
                        f"📁 Files: {len(result.get('processed_files', []))} | "
                        f"📊 Chunks: {result.get('total_chunks', 0)}"
                    )
                    if result.get("processed_files"):
                        st.write("**Files đã xử lý:**")
                        for fname in result["processed_files"]:
                            st.write(f"  ✅ {fname}")
                else:
                    error_detail = rebuild_resp.json().get("detail", rebuild_resp.text)
                    st.error(f"❌ Lỗi rebuild: {error_detail}")
            except requests.exceptions.Timeout:
                st.error("⏱️ Timeout! Thử lại hoặc chạy script build_index.py trực tiếp.")
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

    st.markdown("---")

    # Xem sessions
    st.markdown("#### 💬 Lịch Sử Hội Thoại")
    try:
        sessions_resp = requests.get(f"{backend_url}/sessions", timeout=10)
        if sessions_resp.status_code == 200:
            sessions_data = sessions_resp.json()
            sessions = sessions_data.get("sessions", [])
            st.info(f"Tổng cộng **{len(sessions)}** phiên hội thoại")

            if sessions:
                selected_session = st.selectbox(
                    "Chọn session để xem:",
                    sessions,
                    format_func=lambda x: x[:16] + "...",
                    key="session_selector",
                )

                if selected_session and st.button("📖 Xem lịch sử", key="view_history_btn"):
                    hist_resp = requests.get(
                        f"{backend_url}/history/{selected_session}",
                        timeout=10
                    )
                    if hist_resp.status_code == 200:
                        history = hist_resp.json().get("messages", [])
                        st.markdown(f"**Session:** `{selected_session}`")
                        st.markdown(f"**Số tin nhắn:** {len(history)}")

                        for msg in history:
                            with st.expander(
                                f"🧑 {msg['user_message'][:60]}...",
                                expanded=False
                            ):
                                st.markdown(f"**Câu hỏi:** {msg['user_message']}")
                                st.markdown(f"**Trả lời:** {msg['bot_response']}")
                                feedback_str = ""
                                if msg.get("feedback"):
                                    fb = msg["feedback"]
                                    feedback_str = f" | Phản hồi: {'👍' if fb == 'up' else '👎'}"
                                if msg.get("retrieval_score"):
                                    st.caption(
                                        f"Score: {msg['retrieval_score']:.3f} | "
                                        f"{msg['timestamp']}{feedback_str}"
                                    )
    except Exception as e:
        st.error(f"❌ Lỗi: {str(e)}")

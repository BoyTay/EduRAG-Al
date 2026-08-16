"""
admin_page.py - Streamlit trang quản trị tài liệu
Cho phép upload, xem và xóa tài liệu, rebuild index.
"""

import requests
import streamlit as st
from datetime import datetime


def render_admin(backend_url: str):
    """Render toàn bộ giao diện admin."""

    # ─── Tabs ─────────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📤 Upload Tài Liệu", "📋 Danh Sách Tài Liệu", "🔧 Công Cụ"])

    # ─── Tab 1: Upload ─────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### 📤 Upload Tài Liệu Mới")
        st.info("Hỗ trợ file **PDF** và **DOCX**. File sẽ được tự động phân đoạn và đưa vào hệ thống.")

        uploaded_file = st.file_uploader(
            "Chọn file tài liệu:",
            type=["pdf", "docx"],
            help="Chỉ chấp nhận file PDF hoặc DOCX",
            key="doc_uploader",
        )

        description = st.text_area(
            "Mô tả tài liệu (tùy chọn):",
            placeholder="Ví dụ: Quy chế đào tạo đại học hệ chính quy năm 2024",
            height=80,
            key="doc_description",
        )

        if uploaded_file is not None:
            # Preview thông tin file
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📄 Tên file", uploaded_file.name)
            with col2:
                size_kb = uploaded_file.size / 1024
                st.metric("💾 Kích thước", f"{size_kb:.1f} KB")
            with col3:
                st.metric("📁 Định dạng", uploaded_file.type.split("/")[-1].upper())

            st.markdown("---")

            if st.button("⬆️ Upload & Nạp vào Hệ Thống", key="upload_btn", use_container_width=True):
                with st.spinner("⏳ Đang xử lý tài liệu... (có thể mất vài phút)"):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {}
                        if description.strip():
                            data["description"] = description.strip()

                        resp = requests.post(
                            f"{backend_url}/admin/upload",
                            files=files,
                            data=data,
                            timeout=300,  # 5 phút cho file lớn
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

    # ─── Tab 2: Danh sách tài liệu ─────────────────────────────────────────────
    with tab2:
        st.markdown("### 📋 Danh Sách Tài Liệu Đã Nạp")

        col_refresh, col_count = st.columns([1, 3])
        with col_refresh:
            refresh_btn = st.button("🔄 Làm mới", key="refresh_docs")

        # Lấy danh sách tài liệu
        try:
            resp = requests.get(f"{backend_url}/admin/documents", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                documents = data.get("documents", [])
                total = data.get("total", 0)

                with col_count:
                    st.info(f"Tổng cộng: **{total}** tài liệu")

                if not documents:
                    st.markdown("""
                    <div style="text-align:center; padding:40px; color:rgba(255,255,255,0.5);">
                        <h3>📭 Chưa có tài liệu nào</h3>
                        <p>Upload tài liệu ở tab <strong>Upload Tài Liệu</strong> hoặc chạy script build_index.py</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Hiển thị từng tài liệu
                    for doc in documents:
                        with st.expander(
                            f"📄 {doc['filename']} — {doc['chunk_count']} chunks — {doc['file_size_kb']:.1f} KB",
                            expanded=False
                        ):
                            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                            with col1:
                                st.write(f"**Mô tả:** {doc.get('description') or 'Không có mô tả'}")
                            with col2:
                                st.metric("Loại", doc['file_type'].upper())
                            with col3:
                                uploaded_at = doc['uploaded_at']
                                try:
                                    dt = datetime.fromisoformat(uploaded_at)
                                    uploaded_at = dt.strftime("%d/%m/%Y %H:%M")
                                except Exception:
                                    pass
                                st.write(f"**Upload:** {uploaded_at}")
                            with col4:
                                if st.button(
                                    f"🗑️ Xóa",
                                    key=f"delete_{doc['id']}",
                                    help=f"Xóa {doc['filename']}",
                                    use_container_width=True,
                                ):
                                    st.session_state[f"confirm_delete_{doc['id']}"] = True

                            # Xác nhận xóa
                            if st.session_state.get(f"confirm_delete_{doc['id']}", False):
                                st.warning(f"⚠️ Bạn chắc chắn muốn xóa **{doc['filename']}**?")
                                confirm_col1, confirm_col2 = st.columns(2)
                                with confirm_col1:
                                    if st.button("✅ Xác nhận xóa", key=f"confirm_yes_{doc['id']}", use_container_width=True):
                                        with st.spinner("Đang xóa..."):
                                            try:
                                                del_resp = requests.delete(
                                                    f"{backend_url}/admin/delete/{doc['filename']}",
                                                    timeout=30,
                                                )
                                                if del_resp.status_code == 200:
                                                    result = del_resp.json()
                                                    st.success(f"✅ {result['message']}")
                                                    st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                                                    st.rerun()
                                                else:
                                                    error_detail = del_resp.json().get("detail", del_resp.text)
                                                    st.error(f"❌ {error_detail}")
                                            except Exception as e:
                                                st.error(f"❌ Lỗi: {str(e)}")
                                with confirm_col2:
                                    if st.button("❌ Hủy", key=f"confirm_no_{doc['id']}", use_container_width=True):
                                        st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                                        st.rerun()
            else:
                st.error(f"Không thể lấy danh sách tài liệu: {resp.status_code}")

        except Exception as e:
            st.error(f"❌ Không thể kết nối backend: {str(e)}")

    # ─── Tab 3: Công cụ ────────────────────────────────────────────────────────
    with tab3:
        st.markdown("### 🔧 Công Cụ Quản Trị")

        # Health check
        st.markdown("#### 📡 Trạng Thái Hệ Thống")
        try:
            health_resp = requests.get(f"{backend_url}/health", timeout=5)
            if health_resp.status_code == 200:
                health = health_resp.json()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🟢 Backend", "Online")
                with col2:
                    st.metric("📊 Vector Chunks", health.get("vector_store_docs", 0))
                with col3:
                    st.metric("🤖 LLM", health.get("llm_model", "N/A"))

                st.success(f"**Embedding Model:** {health.get('embedding_model', 'N/A')}")
            else:
                st.error("Backend không khả dụng")
        except Exception:
            st.error("❌ Không thể kết nối backend. Đảm bảo backend đang chạy.")

        st.markdown("---")

        # Rebuild index
        st.markdown("#### 🔄 Rebuild Vector Store")
        st.warning("⚠️ **Cảnh báo:** Thao tác này sẽ xóa và tạo lại toàn bộ vector store từ thư mục `data/`. Có thể mất nhiều thời gian.")

        if st.button("🔨 Rebuild Index", key="rebuild_btn", use_container_width=True):
            with st.spinner("⏳ Đang rebuild... (có thể mất vài phút)"):
                try:
                    rebuild_resp = requests.post(
                        f"{backend_url}/admin/rebuild-index",
                        timeout=600,  # 10 phút
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
                                    if msg.get("retrieval_score"):
                                        st.caption(f"Score: {msg['retrieval_score']:.3f} | {msg['timestamp']}")
        except Exception as e:
            st.error(f"❌ Lỗi: {str(e)}")

"""
app.py - Streamlit Frontend chính (v3.0 – University Style)
Giao diện chat cho sinh viên tra cứu tài liệu.
Redesigned: Light university theme with green accent, matching Stitch "EduRAG Student Chat (University Style)".
"""

import os
import uuid
import requests
import streamlit as st
from datetime import datetime

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ─── Page config ──────────────────────────────────────────────────────────────
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

st.set_page_config(
    page_title="EduRAG – Chatbot Hỗ Trợ Sinh Viên",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS (University Style – Dynamic Theme) ─────────────────────────────

def inject_theme_css():
    """Inject CSS dựa trên theme hiện tại (light/dark)."""
    theme = st.session_state.get("theme", "light")
    is_dark = theme == "dark"

    # ─── Theme-dependent color variables ───
    if is_dark:
        app_bg = "#1a1b2e"
        sidebar_bg = "#161828"
        sidebar_border = "#2d2f48"
        text_primary = "#e8e8f0"
        text_secondary = "#9a9ab0"
        text_heading = "#f0f0f8"
        border_color = "#2d2f48"
        card_bg = "#1e2035"
        bot_bubble_bg = "#242640"
        bot_bubble_border = "rgba(100,105,140,0.3)"
        input_bg = "#1e2035"
        input_border = "#3a3c58"
        date_pill_bg = "#2a2c45"
        date_pill_color = "#9a9ab0"
        source_badge_bg = "#2a3d15"
        source_badge_color = "#baf472"
        match_badge_bg = "#1a2e1a"
        match_badge_color = "#6fcf6f"
        match_badge_border = "#2a4a2a"
        empty_chat_color = "#9a9ab0"
        header_bg = "rgba(26,27,46,0.85)"
        metric_bg = "#1e2035"
        metric_label = "#9a9ab0"
        metric_value = "#86bc42"
        nav_active_color = "#e8e8f0"
        nav_inactive_color = "#9a9ab0"
        nav_hover_color = "#c0c0d0"
        login_card_bg = "#1e2035"
        login_card_border = "rgba(100,105,140,0.3)"
        login_input_bg = "#242640"
        login_input_border = "#3a3c58"
        login_input_text = "#e8e8f0"
        login_label_color = "#9a9ab0"
        login_text_color = "#e8e8f0"
        google_btn_bg = "#242640"
        google_btn_border = "#3a3c58"
        google_btn_color = "#c0c0d0"
        google_btn_hover_bg = "#2a2c45"
        divider_color = "#2d2f48"
        conv_item_color = "#9a9ab0"
        conv_item_hover_bg = "rgba(134,188,66,0.10)"
        conv_item_active_border = "#86bc42"
        conv_item_active_bg = "rgba(134,188,66,0.15)"
        sidebar_btn_bg = "#86bc42"
        sidebar_btn_text = "#ffffff"
        doc_name_color = "#e8e8f0"
        doc_meta_color = "#9a9ab0"
        doc_hover_bg = "rgba(134,188,66,0.08)"
        typing_bubble_bg = "#242640"
        typing_dot_color = "#86bc42"
    else:
        app_bg = "#fafaf7"
        sidebar_bg = "#f5f3ee"
        sidebar_border = "#e5e2da"
        text_primary = "#2d3a2e"
        text_secondary = "#6b7c6b"
        text_heading = "#151c27"
        border_color = "#c3c9b4"
        card_bg = "#ffffff"
        bot_bubble_bg = "#f0f3ff"
        bot_bubble_border = "rgba(195,201,180,0.5)"
        input_bg = "#ffffff"
        input_border = "#c3c9b4"
        date_pill_bg = "#f0f3ff"
        date_pill_color = "#434939"
        source_badge_bg = "#baf472"
        source_badge_color = "#2f4f00"
        match_badge_bg = "#e6f4ea"
        match_badge_color = "#137333"
        match_badge_border = "#ceead6"
        empty_chat_color = "#6b7c6b"
        header_bg = "rgba(249,249,255,0.8)"
        metric_bg = "#ffffff"
        metric_label = "#434939"
        metric_value = "#536600"
        nav_active_color = "#2d3a2e"
        nav_inactive_color = "#6b7c6b"
        nav_hover_color = "#2d3a2e"
        login_card_bg = "#ffffff"
        login_card_border = "rgba(195, 201, 180, 0.5)"
        login_input_bg = "#ffffff"
        login_input_border = "#c3c9b4"
        login_input_text = "#151c27"
        login_label_color = "#434939"
        login_text_color = "#151c27"
        google_btn_bg = "#ffffff"
        google_btn_border = "#c3c9b4"
        google_btn_color = "#45617a"
        google_btn_hover_bg = "#f8faf5"
        divider_color = "#c3c9b4"
        conv_item_color = "#4f5f4f"
        conv_item_hover_bg = "rgba(74,103,65,0.10)"
        conv_item_active_border = "#406900"
        conv_item_active_bg = "rgba(74,103,65,0.14)"
        sidebar_btn_bg = "#4a6741"
        sidebar_btn_text = "#ffffff"
        doc_name_color = "#2d3a2e"
        doc_meta_color = "#8a8a7a"
        doc_hover_bg = "rgba(74,103,65,0.06)"
        typing_bubble_bg = "#f0f3ff"
        typing_dot_color = "#406900"

    link_color = "#86bc42" if is_dark else "#406900"
    feedback_idle_bg = "#242640" if is_dark else "#f5f7fb"
    feedback_idle_border = "#3a3c58" if is_dark else "#d8dfeb"
    feedback_idle_text = "#c0c0d0" if is_dark else "#60718a"
    feedback_hover_bg = "#2a2c45" if is_dark else "#eaf0f9"

    st.markdown(f"""
    <style>
        /* ─── Import Fonts ─── */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}

        /* ─── Hide Streamlit Default Menu & Keep Controls Ready ─── */
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}

        header[data-testid="stHeader"] {{
            background: transparent !important;
            height: 0px !important;
            min-height: 0px !important;
            padding: 0 !important;
            pointer-events: none !important;
            z-index: 99 !important;
        }}
        header[data-testid="stHeader"] [data-testid="stToolbar"],
        header[data-testid="stHeader"] [data-testid="stDecoration"],
        header[data-testid="stHeader"] [data-testid="stStatusWidget"] {{
            display: none !important;
        }}
        header[data-testid="stHeader"] [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {{
            opacity: 0 !important;
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 32px !important;
            height: 32px !important;
            pointer-events: auto !important;
        }}
        [data-testid="stSidebarCollapseButton"],
        button[aria-label="Close sidebar"],
        button[aria-label="Collapse sidebar"] {{
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}

        /* ─── Main Background ─── */
        .stApp {{
            background: {app_bg};
            min-height: 100vh;
            transition: background 0.3s ease;
        }}

        /* ─── Sidebar Native Sizing & Styling ─── */
        [data-testid="stSidebar"],
        section[data-testid="stSidebar"] {{
            width: 260px !important;
            min-width: 260px !important;
            max-width: 260px !important;
            background: {sidebar_bg} !important;
            border-right: 1px solid {sidebar_border} !important;
            transition: background 0.3s ease !important;
        }}

        /* ─── Main Content Container (Centered & Balanced) ─── */
        .main .block-container {{
            max-width: 860px !important;
            margin: 0 auto !important;
            padding: 1.2rem 1.5rem 6rem 1.5rem !important;
        }}

        /* ─── Hide Sidebar on Login Page ─── */
        .stApp:has(.stitch-login-anchor) [data-testid="stSidebar"],
        .stApp:has(.stitch-login-anchor) section[data-testid="stSidebar"] {{
            display: none !important;
        }}
        [data-testid="stSidebar"] > div:first-child,
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarUserContent"] {{
            padding-top: 0.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}
        [data-testid="stSidebarHeader"] {{
            padding: 0.25rem 0.5rem 0 0.5rem !important;
            min-height: 2rem !important;
            height: auto !important;
            margin-bottom: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
            color: {text_primary};
        }}

        /* ─── Sidebar Expander Override (Library & Settings) ─── */
        [data-testid="stSidebar"] [data-testid="stExpander"] {{
            border: 1px solid {border_color} !important;
            border-radius: 10px !important;
            background: {'#1e2035' if is_dark else '#ffffff'} !important;
            margin-bottom: 8px !important;
            overflow: hidden !important;
            box-shadow: 0 1px 4px rgba(0,0,0,{'0.15' if is_dark else '0.04'}) !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"]:hover {{
            border-color: #86bc42 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:focus,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:active {{
            background-color: {'#1e2035' if is_dark else '#f8f7f2'} !important;
            background: {'#1e2035' if is_dark else '#f8f7f2'} !important;
            color: {text_primary} !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
            padding: 10px 14px !important;
            border-radius: 9px !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            outline: none !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
            background-color: {'#242640' if is_dark else '#edf3e7'} !important;
            background: {'#242640' if is_dark else '#edf3e7'} !important;
            color: {'#86bc42' if is_dark else '#406900'} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary p,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary span {{
            color: {text_primary} !important;
            font-weight: 600 !important;
            transition: color 0.2s ease !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover p,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover span {{
            color: {'#86bc42' if is_dark else '#406900'} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary svg,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stExpanderIcon"] {{
            color: {text_secondary} !important;
            fill: currentColor !important;
            transition: color 0.2s ease, transform 0.2s ease !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover svg,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover [data-testid="stExpanderIcon"] {{
            color: {'#86bc42' if is_dark else '#406900'} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{
            background: {'#1e2035' if is_dark else '#ffffff'} !important;
            border-top: 1px solid {border_color} !important;
            padding: 10px 12px !important;
        }}

        /* ─── Top header bar ─── */
        .top-header-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 24px;
            border-bottom: 1px solid {border_color};
            background: {header_bg};
            backdrop-filter: blur(8px);
            margin: -1rem -1rem 0 -1rem;
            margin-bottom: 16px;
        }}
        .top-header-left {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .top-header-title {{
            font-size: 20px;
            font-weight: 600;
            color: {text_heading};
            line-height: 28px;
        }}
        .online-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #22c55e;
            display: inline-block;
            box-shadow: 0 0 6px rgba(34,197,94,0.6);
            animation: dotPulse 2s infinite;
        }}
        @keyframes dotPulse {{
            0%, 100% {{ opacity: 1; box-shadow: 0 0 6px rgba(34,197,94,0.6); }}
            50% {{ opacity: 0.6; box-shadow: 0 0 12px rgba(34,197,94,0.3); }}
        }}
        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(16px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes floatBounce {{
            0%, 100% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-8px); }}
        }}
        .export-btn {{
            background: none;
            border: none;
            color: {text_secondary};
            font-size: 20px;
            cursor: pointer;
            padding: 6px;
            border-radius: 50%;
            transition: background 0.2s;
        }}
        .export-btn:hover {{ background: {bot_bubble_bg}; }}

        /* ─── Date Separator ─── */
        .date-separator {{
            display: flex;
            justify-content: center;
            margin: 16px 0;
        }}
        .date-pill {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: {date_pill_color};
            background: {date_pill_bg};
            padding: 4px 14px;
            border-radius: 999px;
        }}

        /* ─── Chat Rows ─── */
        .chat-row {{
            display: flex;
            margin: 10px 0;
            max-width: 800px;
            width: 100%;
            animation: fadeInUp 0.3s ease-out;
        }}
        .chat-row.user {{
            justify-content: flex-end;
            margin-left: auto;
        }}
        .chat-row.bot {{
            justify-content: flex-start;
        }}

        /* ─── Avatars ─── */
        .chat-avatar {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
            flex-shrink: 0;
            margin-top: 4px;
        }}
        .chat-avatar.user-avatar {{
            background: #d3ee74;
            border: 1px solid {border_color};
            margin-left: 10px;
            order: 2;
            font-size: 16px;
        }}
        .chat-avatar.bot-avatar {{
            background: {bot_bubble_bg};
            border: 1px solid {border_color};
            color: {'#86bc42' if is_dark else '#406900'};
            margin-right: 10px;
            font-weight: 700;
        }}

        /* ─── Chat Bubbles ─── */
        .chat-bubble {{
            padding: 14px 20px;
            line-height: 1.65;
            max-width: 75%;
            word-wrap: break-word;
        }}
        .chat-bubble.user-bubble {{
            background: linear-gradient(135deg, #86bc42 0%, #6fa832 100%);
            color: #ffffff;
            border-radius: 18px 18px 4px 18px;
            box-shadow: 0 4px 20px rgba(64,105,0,0.15);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .chat-bubble.user-bubble:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 24px rgba(64,105,0,0.22);
        }}
        .chat-bubble.bot-bubble {{
            background: {bot_bubble_bg};
            border: 1px solid {bot_bubble_border};
            border-left: 3px solid #86bc42;
            color: {text_heading};
            border-radius: 18px 18px 18px 4px;
            box-shadow: 0 4px 20px rgba(0,0,0,{'0.15' if is_dark else '0.05'});
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .chat-bubble.bot-bubble:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 24px rgba(0,0,0,{'0.2' if is_dark else '0.08'});
        }}
        .chat-bubble.bot-bubble ul {{
            list-style-type: disc;
            padding-left: 1.5em;
            margin: 6px 0;
        }}
        .chat-bubble.bot-bubble li {{
            margin-bottom: 4px;
        }}
        .chat-bubble.bot-bubble strong {{
            font-weight: 600;
        }}

        .chat-meta {{
            font-size: 11px;
            color: {text_secondary};
            margin-top: 6px;
        }}
        .chat-meta.user-meta {{
            text-align: right;
            color: rgba(255,255,255,0.7);
        }}

        /* ─── Source Badge (green pill) ─── */
        .source-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: {source_badge_bg};
            color: {source_badge_color};
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            margin: 3px 4px 0 0;
            transition: background 0.2s;
            cursor: pointer;
        }}
        .source-badge:hover {{
            background: {'#3a5020' if is_dark else '#9fd75a'};
        }}

        /* ─── Match Score Badge ─── */
        .match-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: {match_badge_bg};
            color: {match_badge_color};
            border: 1px solid {match_badge_border};
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
        }}

        /* ─── Bot Tools Row ─── */
        .bot-tools-row {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            margin-top: 8px;
        }}
        .bot-tools-spacer {{ flex: 1; }}
        /* Các thao tác phản hồi chỉ lộ ra khi người dùng tập trung vào câu trả lời. */
        [class*="st-key-answer_"] [class*="st-key-feedback_controls_"] {{
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            pointer-events: none;
            transform: translateY(-5px);
            transition: max-height 160ms ease, opacity 160ms ease, transform 160ms ease;
        }}
        [class*="st-key-answer_"]:hover [class*="st-key-feedback_controls_"],
        [class*="st-key-answer_"]:focus-within [class*="st-key-feedback_controls_"] {{
            max-height: 52px;
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0);
        }}
        [class*="st-key-feedback_controls_"] [data-testid="stButton"] > button {{
            min-height: 30px !important;
            padding: 4px 10px !important;
            border: 1px solid {feedback_idle_border} !important;
            border-radius: 999px !important;
            background: {feedback_idle_bg} !important;
            color: {feedback_idle_text} !important;
            font-size: 11px !important;
            box-shadow: none !important;
            transition: background 140ms ease, border-color 140ms ease, color 140ms ease !important;
        }}
        [class*="st-key-feedback_controls_"] [data-testid="stButton"] > button:hover {{
            background: {feedback_hover_bg} !important;
            border-color: {link_color} !important;
            color: {link_color} !important;
        }}
        [class*="st-key-feedback_controls_"] [data-testid="stButton"] > button[kind="primary"] {{
            background: {link_color} !important;
            border-color: {link_color} !important;
            color: #ffffff !important;
        }}
        @media (hover: none), (pointer: coarse) {{
            [class*="st-key-answer_"] [class*="st-key-feedback_controls_"] {{
                max-height: 52px;
                opacity: 1;
                pointer-events: auto;
                transform: translateY(0);
            }}
        }}
        .feedback-btn {{
            background: none;
            border: none;
            color: {text_secondary};
            font-size: 16px;
            cursor: pointer;
            padding: 4px 6px;
            border-radius: 6px;
            transition: all 0.2s;
        }}
        .feedback-btn:hover {{
            background: {bot_bubble_bg};
            color: #86bc42;
        }}

        /* ─── Typing Indicator ─── */
        .typing-row {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin: 10px 0;
            max-width: 800px;
            opacity: 0.6;
        }}
        .typing-bubble {{
            background: {typing_bubble_bg};
            padding: 12px 18px;
            border-radius: 18px 18px 18px 4px;
            display: flex;
            align-items: center;
            gap: 5px;
            width: 70px;
        }}
        .typing-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: {typing_dot_color};
            animation: typingBounce 1.4s infinite ease-in-out;
        }}
        .typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
        .typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
        @keyframes typingBounce {{
            0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }}
            40% {{ transform: scale(1); opacity: 1; }}
        }}

        /* ─── Bottom Chat Container (Eliminate Black Band) ─── */
        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"],
        .stChatFloatingInputContainer {{
            background: {app_bg} !important;
            background-color: {app_bg} !important;
            border-top: 1px solid {border_color} !important;
            transition: background 0.3s ease !important;
        }}

        /* ─── Input Bar Styling ─── */
        .input-wrapper {{
            max-width: 800px;
            margin: 0 auto;
            padding: 0 16px;
        }}
        .stChatInput {{
            max-width: 780px !important;
            margin: 0 auto !important;
        }}
        .stChatInput > div {{
            background: {input_bg} !important;
            border: 1.5px solid {input_border} !important;
            border-radius: 28px !important;
            box-shadow: 0 4px 20px rgba(0,0,0,{'0.15' if is_dark else '0.05'}) !important;
            transition: border-color 0.2s, box-shadow 0.2s !important;
        }}
        .stChatInput > div:focus-within {{
            border-color: #86bc42 !important;
            box-shadow: 0 4px 24px rgba(134,188,66,0.2) !important;
        }}
        .stChatInput textarea {{
            color: {text_heading} !important;
            font-size: 14px !important;
        }}
        .stChatInput textarea::placeholder {{
            color: {text_secondary} !important;
        }}
        .stChatInput button {{
            color: {'#86bc42' if is_dark else '#4a6741'} !important;
        }}
        .stChatInput button:hover {{
            background: {'#242640' if is_dark else '#eef6e8'} !important;
        }}
        .disclaimer-text {{
            text-align: center;
            font-size: 11px;
            color: {text_secondary};
            margin-top: 8px;
            padding-bottom: 8px;
        }}

        /* ─── Sidebar Brand ─── */
        .sidebar-brand {{
            padding: 4px 2px 14px 2px !important;
            margin-top: 0 !important;
        }}
        .sidebar-brand-name {{
            font-size: 24px !important;
            font-weight: 700 !important;
            color: {text_primary} !important;
            line-height: 1.15 !important;
            letter-spacing: -0.02em !important;
        }}
        .sidebar-brand-tag {{
            color: {text_secondary} !important;
            font-size: 13px !important;
            font-weight: 400 !important;
            margin-top: 2px !important;
        }}

        /* ─── Sidebar Nav Items ─── */
        .sidebar-nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 10px;
            color: {text_secondary};
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
            text-decoration: none;
            margin-bottom: 2px;
        }}
        .sidebar-nav-item:hover {{
            background: {conv_item_hover_bg};
        }}
        .sidebar-nav-item.active {{
            background: #86bc42;
            color: #ffffff;
            font-weight: 600;
        }}
        .sidebar-nav-icon {{
            font-size: 18px;
            width: 22px;
            text-align: center;
        }}

        /* ─── Conversation History ─── */
        .conv-history-label {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {text_secondary};
            padding: 8px 12px 6px;
            margin-top: 4px;
        }}
        .conv-history-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 8px;
            color: {conv_item_color};
            font-size: 13px;
            font-weight: 400;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            margin-bottom: 2px;
            border-left: 3px solid transparent;
        }}
        .conv-history-item:hover {{
            background: {conv_item_hover_bg};
            color: {text_primary};
        }}
        .conv-history-item.active {{
            border-left: 3px solid {conv_item_active_border};
            color: {text_primary};
            font-weight: 600;
            background: {conv_item_active_bg};
        }}
        .conv-history-icon {{
            font-size: 14px;
            opacity: 0.7;
            flex-shrink: 0;
        }}

        /* ─── Sidebar Footer Items ─── */
        .sidebar-footer-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            color: {conv_item_color};
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: color 0.2s;
        }}
        .sidebar-footer-item:hover {{
            color: #86bc42;
        }}
        .sidebar-footer-icon {{
            font-size: 16px;
            opacity: 0.8;
        }}

        /* ─── Sidebar Document Item ─── */
        .sidebar-doc-item {{
            display: flex !important;
            align-items: center !important;
            gap: 10px !important;
            padding: 8px 10px !important;
            border-radius: 8px !important;
            font-size: 12px !important;
            margin-bottom: 4px !important;
            background: transparent !important;
            transition: background 0.2s ease, transform 0.15s ease !important;
            cursor: pointer !important;
        }}
        .sidebar-doc-item:hover {{
            background: {'#2a2c45' if is_dark else '#edf3e7'} !important;
            transform: translateX(2px) !important;
        }}
        .doc-name {{
            font-weight: 600 !important;
            color: {doc_name_color} !important;
            font-size: 12.5px !important;
            line-height: 1.3 !important;
            word-break: break-word !important;
        }}
        .sidebar-doc-item:hover .doc-name {{
            color: {'#86bc42' if is_dark else '#406900'} !important;
        }}
        .doc-meta {{
            font-size: 11px !important;
            color: {doc_meta_color} !important;
            margin-top: 2px !important;
        }}

        /* ─── Streamlit Sidebar New Chat Button ─── */
        [data-testid="stSidebar"] .st-key-new_chat_btn button {{
            background: {sidebar_btn_bg} !important;
            color: {sidebar_btn_text} !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 10px 16px !important;
            font-weight: 600 !important;
            font-size: 0.95em !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
            margin-bottom: 6px !important;
            box-shadow: 0 2px 8px rgba(74,103,65,0.2) !important;
        }}
        [data-testid="stSidebar"] .st-key-new_chat_btn button p,
        [data-testid="stSidebar"] .st-key-new_chat_btn button span,
        [data-testid="stSidebar"] .st-key-new_chat_btn button [data-testid="stMarkdownContainer"] p {{
            color: {sidebar_btn_text} !important;
        }}
        [data-testid="stSidebar"] .st-key-new_chat_btn button:hover {{
            background: {'#6fa832' if is_dark else '#3d5636'} !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(74,103,65,0.25) !important;
        }}

        /* ─── All Session Buttons in History Scroll Container ─── */
        [data-testid="stSidebar"] .st-key-conv_history button {{
            background: transparent !important;
            border: 1px solid transparent !important;
            border-radius: 8px !important;
            padding: 8px 10px !important;
            font-size: 13px !important;
            font-weight: 400 !important;
            text-align: left !important;
            justify-content: flex-start !important;
            color: {conv_item_color} !important;
            transition: all 0.2s ease !important;
            margin-bottom: 2px !important;
            box-shadow: none !important;
            width: 100% !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history button p,
        [data-testid="stSidebar"] .st-key-conv_history button span,
        [data-testid="stSidebar"] .st-key-conv_history button [data-testid="stMarkdownContainer"] p {{
            color: {conv_item_color} !important;
            text-align: left !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
            font-size: 12.5px !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history button:hover {{
            background: {conv_item_hover_bg} !important;
            border-color: rgba(134,188,66,0.2) !important;
            transform: translateX(2px) !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history button:hover p,
        [data-testid="stSidebar"] .st-key-conv_history button:hover span,
        [data-testid="stSidebar"] .st-key-conv_history button:hover [data-testid="stMarkdownContainer"] p {{
            color: {text_primary} !important;
        }}

        /* Active Session in History Container */
        [data-testid="stSidebar"] .st-key-conv_history button[kind="primary"] {{
            background: {conv_item_active_bg} !important;
            border-left: 3.5px solid {conv_item_active_border} !important;
            border-top: 1px solid rgba(134,188,66,0.15) !important;
            border-right: 1px solid rgba(134,188,66,0.15) !important;
            border-bottom: 1px solid rgba(134,188,66,0.15) !important;
            border-radius: 8px !important;
            padding: 8px 10px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
            width: 100% !important;
            margin-bottom: 2px !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history button[kind="primary"] p,
        [data-testid="stSidebar"] .st-key-conv_history button[kind="primary"] span,
        [data-testid="stSidebar"] .st-key-conv_history button[kind="primary"] [data-testid="stMarkdownContainer"] p {{
            color: {text_primary} !important;
            font-weight: 600 !important;
            text-align: left !important;
            font-size: 12.5px !important;
        }}

        /* ─── Scrollbar for Sidebar History Container ─── */
        [data-testid="stSidebar"] .st-key-conv_history ::-webkit-scrollbar {{
            width: 4px !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history ::-webkit-scrollbar-track {{
            background: transparent !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history ::-webkit-scrollbar-thumb {{
            background: {'rgba(134,188,66,0.3)' if is_dark else 'rgba(74,103,65,0.2)'} !important;
            border-radius: 4px !important;
        }}
        [data-testid="stSidebar"] .st-key-conv_history ::-webkit-scrollbar-thumb:hover {{
            background: {'#86bc42' if is_dark else '#4a6741'} !important;
        }}

        /* ─── Top Nav Row Alignment ─── */
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) {{
            align-items: center !important;
        }}

        /* ─── Top Nav Left Column (Document Title & Status) ─── */
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:first-child {{
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
        }}

        /* ─── Avatar Button in Top Nav (Right) ─── */
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:last-child {{
            display: flex !important;
            justify-content: flex-end !important;
            align-items: center !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:last-child button {{
            background: {'#242640' if is_dark else '#eef6e8'} !important;
            border: 1.5px solid {border_color} !important;
            border-radius: 50% !important;
            width: 38px !important;
            min-width: 38px !important;
            max-width: 38px !important;
            height: 38px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: none !important;
            transition: all 0.2s ease !important;
            margin: 0 0 0 auto !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:last-child button:hover {{
            background: {'#2a3d15' if is_dark else '#d3ee74'} !important;
            border-color: #86bc42 !important;
            transform: scale(1.05) !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:last-child button p,
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:last-child button span {{
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
            font-size: 16px !important;
            color: {'#86bc42' if is_dark else '#406900'} !important;
        }}

        /* ─── Top Nav Active Link (Middle Tabs) ─── */
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="primary"] {{
            background: transparent !important;
            color: {nav_active_color} !important;
            border: none !important;
            border-radius: 0 !important;
            padding: 6px 12px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            box-shadow: none !important;
            border-bottom: 2.5px solid #86bc42 !important;
            height: 38px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="primary"] p,
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="primary"] span {{
            color: {nav_active_color} !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="primary"]:hover {{
            background: transparent !important;
            color: #86bc42 !important;
        }}

        /* ─── Top Nav Inactive Link (Middle Tabs) ─── */
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="secondary"] {{
            background: transparent !important;
            color: {nav_inactive_color} !important;
            border: none !important;
            border-radius: 0 !important;
            padding: 6px 12px !important;
            font-weight: 500 !important;
            font-size: 14px !important;
            box-shadow: none !important;
            border-bottom: 2.5px solid transparent !important;
            height: 38px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="secondary"] p,
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="secondary"] span {{
            color: {nav_inactive_color} !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-marker) div[data-testid="stColumn"]:not(:first-child):not(:last-child) button[kind="secondary"]:hover {{
            background: transparent !important;
            color: {nav_hover_color} !important;
        }}

        /* ─── Metric containers ─── */
        [data-testid="metric-container"] {{
            background: {metric_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 10px;
        }}
        [data-testid="metric-container"] [data-testid="stMetricLabel"] {{
            color: {metric_label};
        }}
        [data-testid="metric-container"] [data-testid="stMetricValue"] {{
            color: {metric_value};
        }}

        /* ─── Empty State ─── */
        .empty-chat {{
            text-align: center;
            padding: 80px 20px 40px;
            color: {empty_chat_color};
            animation: fadeInUp 0.6s ease-out;
        }}
        .empty-chat-icon {{
            width: 72px;
            height: 72px;
            background: {'#86bc42' if is_dark else '#4a6741'};
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
            box-shadow: 0 4px 16px rgba({'134,188,66' if is_dark else '74,103,65'},0.2);
            animation: floatBounce 3s ease-in-out infinite;
        }}
        .empty-chat-icon svg {{
            width: 36px;
            height: 36px;
            fill: white;
        }}
        .empty-chat h3 {{
            color: {text_heading};
            font-size: 1.8em;
            font-weight: 700;
            margin-bottom: 12px;
        }}
        .empty-chat p {{
            font-size: 1em;
            max-width: 480px;
            margin: 0 auto;
            line-height: 1.6;
            color: {empty_chat_color};
        }}

        /* ─── Divider ─── */
        hr {{
            border-color: {divider_color} !important;
        }}

        /* ─── Top Nav Bar Container ─── */
        .topnav-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid {border_color};
            margin-bottom: 14px;
        }}

        /* ─── Top Nav Avatar ─── */
        .topnav-avatar {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #d3ee74;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
            color: #2f4f00;
            border: 1px solid {border_color};
        }}

        /* ─── Stitch Login Screen ─── */
        .login-top-bar {{
            height: 6px;
            background: #86bc42;
            border-radius: 16px 16px 0 0;
            margin: -24px -28px 24px -28px;
        }}

        div[data-testid="stColumn"]:has(.stitch-login-anchor) {{
            background: {login_card_bg} !important;
            border: 1px solid {login_card_border} !important;
            border-radius: 16px !important;
            padding: 24px 28px !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, {'0.2' if is_dark else '0.05'}) !important;
            margin-top: 30px !important;
        }}

        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stForm"] {{
            border: none !important;
            padding: 0 !important;
            background: transparent !important;
            width: 100% !important;
        }}

        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] {{
            width: 100% !important;
            margin-bottom: 8px !important;
        }}

        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] label {{
            color: {login_label_color} !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}

        /* Streamlit 1.61+ text input root */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] {{
            background-color: {login_input_bg} !important;
            background: {login_input_bg} !important;
            border: 1.5px solid {login_input_border} !important;
            border-radius: 8px !important;
            overflow: hidden !important;
            box-shadow: none !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"]:focus-within {{
            border-color: #86bc42 !important;
            box-shadow: 0 0 0 2px rgba(134, 188, 66, 0.15) !important;
        }}

        /* Legacy BaseWeb fallback */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="base-input"],
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"] {{
            background-color: {login_input_bg} !important;
            background: {login_input_bg} !important;
            border: 1.5px solid {login_input_border} !important;
            border-radius: 8px !important;
            padding: 0 6px !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"]:focus-within {{
            border-color: #86bc42 !important;
            box-shadow: 0 0 0 2px rgba(134, 188, 66, 0.15) !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] input,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"] input,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] input {{
            background-color: transparent !important;
            background: transparent !important;
            color: {login_input_text} !important;
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
            padding: 10px 8px !important;
            font-size: 14px !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}

        /* Password visibility toggle */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] button,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"] button,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] button,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Show password"],
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Hide password"] {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
            width: 36px !important;
            min-width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            margin: 0 4px 0 0 !important;
            transform: none !important;
            color: {text_secondary} !important;
            border-radius: 0 !important;
            cursor: pointer !important;
            transition: color 0.2s ease !important;
            flex-shrink: 0 !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] button:hover,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"] button:hover,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] button:hover,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Show password"]:hover,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Hide password"]:hover {{
            background: transparent !important;
            background-color: transparent !important;
            color: #86bc42 !important;
            box-shadow: none !important;
            transform: none !important;
            opacity: 1 !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] button svg,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-baseweb="input"] button svg,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInput"] button svg {{
            width: 18px !important;
            height: 18px !important;
            color: {text_secondary} !important;
            fill: currentColor !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) [data-testid="stTextInputRootElement"] button:hover svg,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Show password"]:hover svg,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) button[aria-label="Hide password"]:hover svg {{
            color: #86bc42 !important;
        }}

        /* Submit Button (Đăng nhập) */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button {{
            background: #86bc42 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 11px 16px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            box-shadow: 0 2px 6px rgba(134, 188, 66, 0.3) !important;
            width: 100% !important;
            margin-top: 10px !important;
            cursor: pointer !important;
            transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button p,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button span {{
            color: #ffffff !important;
            transition: color 0.2s ease !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button:hover {{
            background: #406900 !important;
            color: #d3ee74 !important;
            box-shadow: 0 4px 12px rgba(64, 105, 0, 0.3) !important;
            transform: translateY(-1px) !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button:hover p,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stFormSubmitButton"] button:hover span {{
            color: #d3ee74 !important;
        }}

        /* Google login button */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button[kind="secondary"] {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 10px !important;
            background: {google_btn_bg} !important;
            background-color: {google_btn_bg} !important;
            color: {google_btn_color} !important;
            border: 1.5px solid {google_btn_border} !important;
            border-radius: 8px !important;
            padding: 10px 16px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            box-shadow: none !important;
            width: 100% !important;
            transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button::before {{
            content: "";
            display: inline-block;
            width: 18px;
            height: 18px;
            flex-shrink: 0;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%234285F4' d='M43.6 20.5H42V20H24v8h11.3C33.9 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z'/%3E%3Cpath fill='%2334A853' d='M6.3 14.7l6.6 4.8C14.5 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 16 4 9 8.3 6.3 14.7z'/%3E%3Cpath fill='%23FBBC05' d='M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.1C29.3 36 24.7 36 24 36c-5.2 0-9.7-3.3-11.3-8l-6.5 5C9 39.7 16 44 24 44z'/%3E%3Cpath fill='%23EA4335' d='M43.6 20.5H42V20H24v8h11.3c-.6 1.8-1.6 3.4-2.9 4.7l6.2 5.1C41.8 34.5 44 29.7 44 24c0-1.3-.1-2.7-.4-3.5z'/%3E%3C/svg%3E");
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button:hover,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button[kind="secondary"]:hover {{
            background: {google_btn_hover_bg} !important;
            background-color: {google_btn_hover_bg} !important;
            border-color: #86bc42 !important;
            color: {'#e8e8f0' if is_dark else '#2f4f00'} !important;
            transform: none !important;
            box-shadow: 0 2px 8px rgba(134, 188, 66, 0.1) !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button p,
        div[data-testid="stColumn"]:has(.stitch-login-anchor) div[data-testid="stButton"] > button span {{
            color: inherit !important;
            transition: color 0.2s ease !important;
        }}
        /* Liên kết văn bản giữa hai màn hình xác thực. */
        div[data-testid="stColumn"]:has(.stitch-login-anchor) .auth-switch-link {{
            color: {link_color} !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            text-decoration: none !important;
        }}
        div[data-testid="stColumn"]:has(.stitch-login-anchor) .auth-switch-link:hover {{
            text-decoration: underline !important;
        }}

        /* ─── Sidebar Toggle Override ─── */
        [data-testid="stSidebar"] .stToggle label span {{
            color: {text_primary} !important;
            font-size: 13px !important;
        }}
    </style>
    """, unsafe_allow_html=True)


# ─── Session State Initialization ─────────────────────────────────────────────

def init_session():
    """Khởi tạo session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False
    if "admin_display_name" not in st.session_state:
        st.session_state.admin_display_name = ""
    if "user_role" not in st.session_state:
        st.session_state.user_role = "student"
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"
    if "session_created" not in st.session_state:
        st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")
    if "show_history" not in st.session_state:
        st.session_state.show_history = False
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
    if "sidebar_state" not in st.session_state:
        st.session_state.sidebar_state = "expanded"
    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = ""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None


# ─── API Helpers ──────────────────────────────────────────────────────────────

def check_backend_health() -> dict | None:
    """Kiểm tra kết nối backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def auth_headers() -> dict:
    """Header xác thực cho các API gắn với lịch sử cá nhân."""
    token = st.session_state.get("auth_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def send_chat(question: str, session_id: str) -> dict | None:
    """Gửi câu hỏi đến backend, nhận câu trả lời."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat",
            json={"question": question, "session_id": session_id},
            headers=auth_headers(),
            timeout=120,
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
            headers=auth_headers(),
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
        resp = requests.get(f"{BACKEND_URL}/history/{session_id}", headers=auth_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
        return []
    except Exception:
        return []


# ─── Auto-scroll JavaScript ──────────────────────────────────────────────────

def inject_auto_scroll():
    """Inject JavaScript để tự cuộn xuống tin nhắn mới nhất."""
    st.html("""
    <script>
        const chatContainer = document.querySelector('[data-testid="stVerticalBlock"]');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        const main = document.querySelector('.main');
        if (main) {
            main.scrollTop = main.scrollHeight;
        }
    </script>
    """)


# ─── Chat Page ────────────────────────────────────────────────────────────────

def render_chat_page():
    """Hiển thị trang chat chính (University Style)."""

    # Handle pending question from suggestion click
    if "pending_question" in st.session_state and st.session_state.pending_question:
        question = st.session_state.pop("pending_question")
        st.session_state.messages.append({
            "role": "user",
            "content": question,
            "time": datetime.now().strftime("%H:%M"),
        })
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

    # Render chat content
    if not st.session_state.messages:
        # Empty state
        st.markdown("""
        <div class="empty-chat">
            <div class="empty-chat-icon">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/>
                </svg>
            </div>
            <h3>Xin chào! Tôi có thể giúp gì cho bạn?</h3>
            <p>Hệ thống AI hỗ trợ sinh viên tra cứu quy chế đào tạo tín chỉ, học phí, học bổng và các văn bản quy định của Khoa.</p>
        </div>
        """, unsafe_allow_html=True)

    else:
        # Date separator
        st.markdown("""
        <div class="date-separator">
            <span class="date-pill">Hôm nay</span>
        </div>
        """, unsafe_allow_html=True)

        # Render messages
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
                answer_container_key = f"answer_{message_id or 'local'}_{idx}"

                # Source badges HTML
                sources_html = ""
                if sources:
                    for src in sources:
                        fname = src.get("filename", "N/A")
                        page = src.get("page")
                        page_info = f" • Tr. {page}" if page else ""
                        sources_html += f'<span class="source-badge" title="Tài liệu tham khảo: {fname}">📄 {fname}{page_info}</span>'

                # Match score badge
                score_pct = int(score * 100) if score <= 1 else int(score)
                match_html = ""
                if score > 0:
                    match_html = f'<span class="match-badge">✓ {score_pct}% Khớp dữ liệu</span>'

                with st.container(key=answer_container_key):
                    st.markdown(f"""
                    <div class="chat-row bot">
                        <div class="chat-avatar bot-avatar">E</div>
                        <div style="display:flex; flex-direction:column; max-width:75%;">
                            <div class="chat-bubble bot-bubble">
                                {content}
                                <div class="chat-meta">{msg_time}</div>
                            </div>
                            <div class="bot-tools-row">
                                {sources_html}
                                {match_html}
                                <div class="bot-tools-spacer"></div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if message_id:
                        with st.container(horizontal=True, gap="small", key=f"feedback_controls_{message_id}_{idx}"):
                            if st.button(
                                "👍 Hữu ích",
                                key=f"feedback_up_{message_id}_{idx}",
                                type="primary" if msg.get("feedback") == "up" else "secondary",
                            ):
                                if send_feedback(message_id, "up"):
                                    st.session_state.messages[idx]["feedback"] = "up"
                                    st.toast("Cảm ơn bạn đã phản hồi!", icon="✨")
                                    st.rerun()
                            if st.button(
                                "👎 Chưa hữu ích",
                                key=f"feedback_down_{message_id}_{idx}",
                                type="primary" if msg.get("feedback") == "down" else "secondary",
                            ):
                                if send_feedback(message_id, "down"):
                                    st.session_state.messages[idx]["feedback"] = "down"
                                    st.toast("Cảm ơn bạn đã phản hồi!", icon="✨")
                                    st.rerun()

        inject_auto_scroll()

    # Input area
    prompt = st.chat_input("Nhập câu hỏi của bạn tại đây...")
    if prompt:
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "time": datetime.now().strftime("%H:%M"),
        })
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

    # Disclaimer
    st.markdown(
        '<div class="disclaimer-text">EduRAG có thể đưa ra thông tin không chính xác. Hãy kiểm tra lại các quy chế quan trọng.</div>',
        unsafe_allow_html=True,
    )


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    """Hiển thị sidebar (University Style)."""
    with st.sidebar:
        # Brand
        st.markdown("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-name">EduRAG</div>
            <div class="sidebar-brand-tag">Academic AI Assistant</div>
        </div>
        """, unsafe_allow_html=True)

        # New Chat button
        if st.button("➕ New Chat", key="new_chat_btn", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")
            st.session_state.current_page = "chat"
            st.session_state.show_history = False
            st.rerun()

        # ─── Conversation History ───
        st.markdown('<div class="conv-history-label">CONVERSATION HISTORY</div>', unsafe_allow_html=True)

        # Fetch sessions from backend
        sessions_data = []
        try:
            resp = requests.get(f"{BACKEND_URL}/sessions", headers=auth_headers(), timeout=3)
            if resp.status_code == 200:
                body = resp.json()
                sessions_data = body.get("sessions_detail", [])
                if not sessions_data:
                    sessions_data = [{"session_id": s, "title": f"Phiên {s[:8]}..."} for s in body.get("sessions", [])]
        except Exception:
            pass

        # Always include current session at top if not in list
        current_sid = st.session_state.session_id
        existing_sids = [s.get("session_id") for s in sessions_data]
        if current_sid not in existing_sids:
            cur_title = "Phiên trò chuyện mới"
            if st.session_state.messages:
                first_msg = st.session_state.messages[0].get("content", "")
                cur_title = first_msg[:24] + "..." if len(first_msg) > 24 else first_msg
            sessions_data.insert(0, {"session_id": current_sid, "title": cur_title})

        # Scrollable container for conversation history (tránh bị dài, có thanh cuộn)
        with st.container(height=250, border=False, key="conv_history"):
            for s_info in sessions_data:
                sid = s_info.get("session_id", "")
                is_active = (sid == current_sid)

                # Title resolution
                if is_active and st.session_state.messages:
                    first_msg = st.session_state.messages[0].get("content", "")
                    title = first_msg[:24] + "..." if len(first_msg) > 24 else first_msg
                else:
                    raw_title = s_info.get("title", f"Phiên {sid[:8]}...")
                    title = raw_title[:24] + "..." if len(raw_title) > 24 else raw_title

                btn_label = f"💬  {title}"
                btn_type = "primary" if is_active else "secondary"

                if st.button(btn_label, key=f"sess_btn_{sid}", type=btn_type, use_container_width=True):
                    if sid != current_sid:
                        st.session_state.session_id = sid
                        try:
                            hist_messages = get_history(sid)
                            st.session_state.messages = []
                            for item in hist_messages:
                                # User message
                                st.session_state.messages.append({
                                    "role": "user",
                                    "content": item.get("user_message", ""),
                                    "time": item.get("timestamp", "")[:16].replace("T", " "),
                                })
                                # Bot message
                                st.session_state.messages.append({
                                    "role": "bot",
                                    "content": item.get("bot_response", ""),
                                    "sources": item.get("sources", []),
                                    "retrieval_score": item.get("retrieval_score", 0),
                                    "feedback": item.get("feedback"),
                                    "message_id": item.get("id"),
                                    "time": item.get("timestamp", "")[:16].replace("T", " "),
                                })
                        except Exception:
                            st.session_state.messages = []
                        st.session_state.current_page = "chat"
                        st.session_state.show_history = False
                        st.rerun()

        # ─── Sidebar Footer (được đẩy lên ngay dưới lịch sử, không có spacer dư) ───
        st.markdown("<hr style='margin: 8px 0 10px 0;'>", unsafe_allow_html=True)

        # ─── Library: Hiển thị danh sách tài liệu ───
        with st.expander("📚 Library", expanded=False):
            try:
                resp = requests.get(f"{BACKEND_URL}/admin/documents", timeout=5)
                if resp.status_code == 200:
                    docs = resp.json().get("documents", [])
                    if docs:
                        for doc in docs:
                            file_icon = "📄" if doc.get("file_type") == "pdf" else "📝"
                            size = doc.get("file_size_kb", 0)
                            chunks = doc.get("chunk_count", 0)
                            fname = doc.get("filename", "N/A")
                            st.markdown(
                                f'<div class="sidebar-doc-item">'
                                f'<span style="font-size:18px;">{file_icon}</span>'
                                f'<div>'
                                f'<div class="doc-name">{fname}</div>'
                                f'<div class="doc-meta">{size:.0f} KB · {chunks} chunks</div>'
                                f'</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("Chưa có tài liệu nào.")
            except Exception:
                st.caption("Không thể tải danh sách tài liệu.")

        # ─── Settings: Theme Toggle ───
        with st.expander("⚙️ Settings", expanded=False):
            is_dark = st.toggle(
                "🌙 Dark Mode",
                value=st.session_state.get("theme") == "dark",
                key="dark_mode_toggle",
            )
            new_theme = "dark" if is_dark else "light"
            if new_theme != st.session_state.get("theme", "light"):
                st.session_state.theme = new_theme
                st.rerun()


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
    lines.append("Xuất bởi EduRAG v3.0")
    return "\n".join(lines)


# ─── Admin Page ───────────────────────────────────────────────────────────────

def render_admin_page():
    """Hiển thị trang quản trị tài liệu (Chỉ dành cho Admin)."""
    # ─── Kiểm tra phân quyền: Chỉ tài khoản Admin mới được vào ───
    if not st.session_state.get("is_admin", False):
        st.error("🚫 **Quyền truy cập bị từ chối**: Bạn đang đăng nhập với vai trò **Sinh viên**.")
        st.info("Chỉ tài khoản **Quản Trị Viên (Admin)** mới có quyền truy cập trang quản trị tài liệu.")
        if st.button("💬 Quay lại Trang Chat", key="back_to_chat_btn"):
            st.session_state.current_page = "chat"
            st.session_state.show_history = False
            st.rerun()
        return

    from admin_page import render_admin
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

def render_history_page():
    """Hiển thị lịch sử hội thoại từ backend."""
    st.markdown("""
    <div class="top-header-bar">
        <div class="top-header-left">
            <span class="top-header-title">📜 Lịch sử hội thoại</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    session_id = st.session_state.session_id
    history = get_history(session_id)

    if not history:
        st.info("Chưa có lịch sử hội thoại cho phiên này.")
        # Also try to list all sessions
        try:
            resp = requests.get(f"{BACKEND_URL}/sessions", headers=auth_headers(), timeout=10)
            if resp.status_code == 200:
                sessions = resp.json().get("sessions", [])
                if sessions:
                    st.markdown("**Các phiên hội thoại khác:**")
                    selected = st.selectbox(
                        "Chọn phiên:",
                        sessions,
                        format_func=lambda x: x[:16] + "...",
                        key="hist_session_select",
                    )
                    if selected and st.button("📖 Xem lịch sử phiên này", key="load_hist_btn"):
                        history = get_history(selected)
        except Exception:
            pass

    if history:
        # Date separator
        st.markdown("""
        <div class="date-separator">
            <span class="date-pill">History</span>
        </div>
        """, unsafe_allow_html=True)

        for msg in history:
            user_q = msg.get("user_message", "")
            bot_a = msg.get("bot_response", "")
            timestamp = msg.get("timestamp", "")
            feedback = msg.get("feedback", "")
            score = msg.get("retrieval_score", 0)

            # User bubble
            st.markdown(f"""
            <div class="chat-row user">
                <div class="chat-bubble user-bubble">
                    {user_q}
                    <div class="chat-meta user-meta">{timestamp}</div>
                </div>
                <div class="chat-avatar user-avatar">🧑‍🎓</div>
            </div>
            """, unsafe_allow_html=True)

            # Bot bubble
            score_pct = int(score * 100) if score and score <= 1 else int(score or 0)
            match_html = f'<span class="match-badge">✓ {score_pct}% Match</span>' if score else ""
            fb_icon = "👍" if feedback == "up" else ("👎" if feedback == "down" else "")

            st.markdown(f"""
            <div class="chat-row bot">
                <div class="chat-avatar bot-avatar">E</div>
                <div style="display:flex; flex-direction:column; max-width:75%;">
                    <div class="chat-bubble bot-bubble">
                        {bot_a}
                        <div class="chat-meta">{timestamp} {fb_icon}</div>
                    </div>
                    <div class="bot-tools-row">
                        {match_html}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─── Top Bar Nav & Sidebar Controller ──────────────────────────────────────────

# ─── Top Bar Nav ──────────────────────────────────────────────────────────────

def render_topbar_nav():
    """Render Top Bar navigation: simplified text links with avatar (Sidebar is permanently fixed)."""
    page = st.session_state.current_page
    is_admin = st.session_state.get("is_admin", False)

    if is_admin:
        # ─── Top Bar cho Admin: doc name + Trang Chat + Quản Trị + avatar ───
        col_doc, col_chat, col_admin, col_avatar = st.columns([5.5, 1.8, 1.8, 0.9])

        with col_doc:
            text_color = '#e8e8f0' if st.session_state.get('theme') == 'dark' else '#2d3a2e'
            st.markdown(
                f'<div class="nav-marker" style="display:flex;align-items:center;gap:8px;height:38px;padding-left:4px;">'
                f'<span class="online-dot"></span>'
                f'<span style="font-size:14px;font-weight:600;color:{text_color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Quy chế đào tạo tín chỉ 2023</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_chat:
            chat_kind = "primary" if page == "chat" else "secondary"
            if st.button("Trang Chat", key="topnav_chat_btn", type=chat_kind, use_container_width=True):
                st.session_state.current_page = "chat"
                st.session_state.show_history = False
                st.rerun()

        with col_admin:
            admin_kind = "primary" if page == "admin" else "secondary"
            if st.button("Quản Trị", key="topnav_admin_btn", type=admin_kind, use_container_width=True):
                st.session_state.current_page = "admin"
                st.session_state.show_history = False
                st.rerun()

        with col_avatar:
            if st.button("👤", key="topnav_avatar_btn", help="Đăng xuất", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.is_admin = False
                st.session_state.admin_logged_in = False
                st.session_state.user_email = ""
                st.session_state.auth_token = ""
                st.session_state.user_id = None
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.current_page = "chat"
                st.rerun()

    else:
        # ─── Top Bar cho Sinh viên: doc name + Trang Chat + avatar ───
        col_doc, col_chat, col_avatar = st.columns([7.3, 1.8, 0.9])

        with col_doc:
            text_color = '#e8e8f0' if st.session_state.get('theme') == 'dark' else '#2d3a2e'
            st.markdown(
                f'<div class="nav-marker" style="display:flex;align-items:center;gap:8px;height:38px;padding-left:4px;">'
                f'<span class="online-dot"></span>'
                f'<span style="font-size:14px;font-weight:600;color:{text_color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Quy chế đào tạo tín chỉ 2023</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_chat:
            if st.button("Trang Chat", key="topnav_chat_btn_student", type="primary", use_container_width=True):
                st.session_state.current_page = "chat"
                st.session_state.show_history = False
                st.rerun()

        with col_avatar:
            if st.button("👤", key="topnav_avatar_btn_student", help="Đăng xuất", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.is_admin = False
                st.session_state.admin_logged_in = False
                st.session_state.user_email = ""
                st.session_state.auth_token = ""
                st.session_state.user_id = None
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.current_page = "chat"
                st.rerun()

    st.markdown("<hr style='margin: 8px 0 16px 0;'>", unsafe_allow_html=True)


# ─── Login Page ───────────────────────────────────────────────────────────────

def render_login_page():
    """Render login page matching Stitch 'EduRAG Login (University Style)' screen 187877cff7b84f238fc1db5c4473fb25."""
    is_dark = st.session_state.get("theme") == "dark"
    title_color = '#86bc42' if is_dark else '#406900'
    subtitle_color = '#9a9ab0' if is_dark else '#434939'
    heading_color = '#e8e8f0' if is_dark else '#151c27'
    divider_border = '#2d2f48' if is_dark else '#c3c9b4'
    divider_text = '#9a9ab0' if is_dark else '#434939'
    footer_text = '#9a9ab0' if is_dark else '#434939'
    link_color = '#86bc42' if is_dark else '#406900'

    col_l, col_c, col_r = st.columns([2, 3, 2])

    with col_c:
        # Card Anchor & Top Green Bar & Header
        st.markdown(f"""
        <div class="stitch-login-anchor"></div>
        <div class="login-top-bar"></div>
        <div style="text-align:center; margin-bottom:24px;">
            <h1 style="font-size:32px; font-weight:700; color:{title_color}; margin:0 0 4px 0; letter-spacing:-0.02em; font-family:'Plus Jakarta Sans',sans-serif;">EduRAG</h1>
            <p style="font-size:14px; color:{subtitle_color}; margin:0 0 20px 0; font-family:'Plus Jakarta Sans',sans-serif;">Academic AI Assistant</p>
            <h2 style="font-size:22px; font-weight:600; color:{heading_color}; margin:0; font-family:'Plus Jakarta Sans',sans-serif;">Đăng nhập</h2>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email / Tên đăng nhập",
                placeholder="student@university.edu hoặc admin",
                key="login_email",
            )
            password = st.text_input(
                "Mật khẩu",
                type="password",
                placeholder="••••••••",
                key="login_password",
            )
            submitted = st.form_submit_button("Đăng nhập", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("❌ Vui lòng nhập tài khoản và mật khẩu!")
                else:
                    is_admin_user = False
                    login_success = False

                    # 1. Kiểm tra tài khoản Admin qua endpoint /admin/login
                    admin_result = admin_login(email, password)
                    if admin_result and admin_result.get("success"):
                        is_admin_user = True
                        login_success = True

                    # 2. Nếu không phải Admin, xác thực tài khoản sinh viên đã đăng ký.
                    if not login_success:
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/auth/login",
                                json={"username": email, "password": password},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                login_success = True
                                is_admin_user = False
                                student_result = resp.json()
                            else:
                                student_result = None
                        except Exception:
                            student_result = None

                    if login_success:
                        st.session_state.messages = []
                        st.session_state.session_id = str(uuid.uuid4())
                        st.session_state.session_created = datetime.now().strftime("%H:%M %d/%m/%Y")
                        st.session_state.logged_in = True
                        st.session_state.is_admin = is_admin_user
                        st.session_state.admin_logged_in = is_admin_user
                        st.session_state.user_role = "admin" if is_admin_user else "student"
                        auth_result = admin_result if is_admin_user else student_result
                        st.session_state.auth_token = auth_result.get("access_token", "")
                        st.session_state.user_id = auth_result.get("user", {}).get("id") if auth_result else None
                        st.session_state.user_email = auth_result.get("user", {}).get("email", email) if auth_result else email
                        st.session_state.current_page = "chat"

                        if is_admin_user:
                            st.session_state.admin_display_name = "Admin"
                            st.success("✅ Đăng nhập thành công với quyền **Quản Trị Viên (Admin)**!")
                        else:
                            st.session_state.admin_display_name = ""
                            st.success("✅ Đăng nhập thành công với quyền **Sinh viên**!")
                        st.rerun()
                    else:
                        st.error("❌ Sai tài khoản hoặc mật khẩu!")

        # Divider
        st.markdown(f"""
        <div style="display:flex; align-items:center; margin:18px 0 14px 0; text-align:center;">
            <div style="flex:1; border-top:1px solid {divider_border};"></div>
            <span style="padding:0 12px; font-size:12px; color:{divider_text}; font-weight:600; font-family:'Plus Jakarta Sans',sans-serif;">hoặc</span>
            <div style="flex:1; border-top:1px solid {divider_border};"></div>
        </div>
        """, unsafe_allow_html=True)

        # Google login chưa được kết nối OAuth nên không cho phép bỏ qua xác thực.
        if st.button("Đăng nhập với Google", key="btn_google_login", use_container_width=True):
            st.info("Đăng nhập Google sẽ được bổ sung sau. Vui lòng dùng tài khoản EduRAG.")

        # Footer
        st.markdown(
            f'<div style="text-align:center; margin-top:22px; font-size:13px; color:{footer_text};">'
            f'Chưa có tài khoản? <a class="auth-switch-link" href="?auth=register" target="_self">Đăng ký</a></div>',
            unsafe_allow_html=True,
        )


def render_register_page():
    """Trang đăng ký tài khoản sinh viên."""
    is_dark = st.session_state.get("theme") == "dark"
    title_color = '#86bc42' if is_dark else '#406900'
    heading_color = '#e8e8f0' if is_dark else '#151c27'
    footer_text = '#9a9ab0' if is_dark else '#434939'

    col_l, col_c, col_r = st.columns([2, 3, 2])
    with col_c:
        st.markdown(f"""
        <div class="stitch-login-anchor"></div>
        <div class="login-top-bar"></div>
        <div style="text-align:center; margin-bottom:24px;">
            <h1 style="font-size:32px; font-weight:700; color:{title_color}; margin:0 0 4px 0;">EduRAG</h1>
            <p style="font-size:14px; color:{footer_text}; margin:0 0 20px 0;">Academic AI Assistant</p>
            <h2 style="font-size:22px; font-weight:600; color:{heading_color}; margin:0;">Tạo tài khoản</h2>
        </div>
        """, unsafe_allow_html=True)
        with st.form("register_form", clear_on_submit=False):
            display_name = st.text_input("Họ và tên", placeholder="Nguyễn Văn A", key="register_name")
            email = st.text_input("Email", placeholder="student@university.edu", key="register_email")
            password = st.text_input("Mật khẩu", type="password", placeholder="Ít nhất 8 ký tự", key="register_password")
            confirm_password = st.text_input("Xác nhận mật khẩu", type="password", placeholder="Nhập lại mật khẩu", key="register_confirm_password")
            submitted = st.form_submit_button("Tạo tài khoản", width="stretch")
            if submitted:
                if not email or not password or not confirm_password:
                    st.error("Vui lòng điền đầy đủ email và mật khẩu.")
                elif password != confirm_password:
                    st.error("Xác nhận mật khẩu chưa khớp.")
                else:
                    try:
                        resp = requests.post(
                            f"{BACKEND_URL}/auth/register",
                            json={"email": email, "password": password, "display_name": display_name},
                            timeout=10,
                        )
                        if resp.status_code == 201:
                            result = resp.json()
                            st.session_state.logged_in = True
                            st.session_state.is_admin = False
                            st.session_state.admin_logged_in = False
                            st.session_state.user_role = "student"
                            st.session_state.auth_token = result["access_token"]
                            st.session_state.user_id = result["user"]["id"]
                            st.session_state.user_email = result["user"]["email"]
                            st.session_state.session_id = str(uuid.uuid4())
                            st.session_state.messages = []
                            st.query_params.clear()
                            st.rerun()
                        elif resp.status_code == 409:
                            st.error("Email này đã được đăng ký. Hãy đăng nhập.")
                        else:
                            st.error(resp.json().get("detail", "Không thể tạo tài khoản."))
                    except Exception:
                        st.error("Không thể kết nối đến máy chủ. Vui lòng thử lại.")
        st.markdown(
            f'<div style="text-align:center; margin-top:22px; font-size:13px; color:{footer_text};">'
            f'Đã có tài khoản? <a class="auth-switch-link" href="?auth=login" target="_self">Đăng nhập</a></div>',
            unsafe_allow_html=True,
        )

def inject_sidebar_auto_expand():
    """Tự động kích hoạt mở sidebar nếu trình duyệt đang lưu trạng thái collapsed."""
    st.html("""
    <script>
    (function() {
        const doc = (window.parent && window.parent.document) || document;
        function autoExpand() {
            const sidebar = doc.querySelector('[data-testid="stSidebar"]');
            const isCollapsed = !sidebar || sidebar.getAttribute('aria-expanded') === 'false' || sidebar.offsetWidth < 50;
            if (isCollapsed) {
                const expandBtn = doc.querySelector(
                    '[data-testid="collapsedControl"] button, ' +
                    '[data-testid="collapsedControl"], ' +
                    '[data-testid="stSidebarCollapsedControl"] button, ' +
                    '[data-testid="stSidebarCollapsedControl"], ' +
                    'button[aria-label="Open sidebar"], ' +
                    'button[aria-label="Expand sidebar"]'
                );
                if (expandBtn) {
                    expandBtn.click();
                }
            }
        }
        autoExpand();
        setTimeout(autoExpand, 50);
        setTimeout(autoExpand, 150);
        setTimeout(autoExpand, 400);
        setTimeout(autoExpand, 800);
    })();
    </script>
    """)


def main():
    init_session()
    requested_auth_page = st.query_params.get("auth")
    if requested_auth_page in {"login", "register"}:
        st.session_state.auth_page = requested_auth_page
    inject_theme_css()
    inject_sidebar_auto_expand()

    # Gate 1: Chưa đăng nhập → Hiển thị Login Page
    if not st.session_state.logged_in:
        if st.session_state.auth_page == "register":
            render_register_page()
        else:
            render_login_page()
        return

    # Gate 2: Đã đăng nhập → Render Sidebar và Top Navigation Bar theo vai trò
    render_sidebar()
    render_topbar_nav()

    # Điều hướng trang
    if st.session_state.show_history:
        render_history_page()
    elif st.session_state.current_page == "chat":
        render_chat_page()
    elif st.session_state.current_page == "admin":
        render_admin_page()


if __name__ == "__main__":
    main()

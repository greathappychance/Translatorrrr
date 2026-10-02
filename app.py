import html

import streamlit as st

import translator

LANGUAGE_LABELS = {"en": "🇺🇸 English", "ja": "🇯🇵 日本語", "fr": "🇫🇷 Français"}

st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

st.markdown(
    """
    <style>
    /* Korean: break lines between words, not inside them */
    h1, p, textarea, [data-testid="stCode"] code { word-break: keep-all !important; overflow-wrap: anywhere; }
    [data-testid="stCode"] pre, [data-testid="stCode"] code {
        font-family: inherit !important; font-size: 1rem !important; line-height: 1.7 !important;
    }
    @media (max-width: 640px) { h1 { font-size: 2rem !important; } }
    .char-count { text-align: right; font-size: 0.85rem; opacity: 0.7; margin-top: -0.5rem; }
    .char-count.over { color: #DC2626; opacity: 1; font-weight: 600; }
    .footer { text-align: center; font-size: 0.8rem; opacity: 0.6; margin-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

config = translator.get_config()
ready = translator.is_ready(config)

st.title("🌐 다국어 번역기")
st.caption("입력한 글을 영어 · 일본어 · 프랑스어 중 선택한 언어로 번역합니다")

if not ready:
    st.error(
        "OpenAI API 키가 설정되지 않아 번역할 수 없습니다.\n\n"
        "- 로컬 실행: 프로젝트 폴더의 `.env` 파일에 `OPENAI_API_KEY=sk-...`를 추가한 뒤 앱을 다시 실행하세요.\n"
        "- Streamlit Cloud: App settings → Secrets에 `OPENAI_API_KEY = \"sk-...\"`를 추가하세요."
    )

text = st.text_area(
    "번역할 글",
    placeholder="번역할 글을 입력하세요...",
    height=200,
    key="input_text",
    label_visibility="collapsed",
)
too_long = len(text) > translator.MAX_CHARS

st.markdown(
    f'<div class="char-count{" over" if too_long else ""}">'
    f"{len(text):,} / {translator.MAX_CHARS:,}자</div>",
    unsafe_allow_html=True,
)

# Filled after the button is handled, but rendered right under the input
messages = st.container()
if too_long:
    messages.warning(translator.MSG_TOO_LONG)

target = st.segmented_control(
    "번역할 언어",
    options=list(LANGUAGE_LABELS),
    format_func=LANGUAGE_LABELS.get,
    default="en",
    required=True,
    key="target_lang",
    width="stretch",
)

if st.button("번역하기", type="primary", width="stretch", disabled=not ready or too_long):
    if not text.strip():
        messages.warning(translator.MSG_EMPTY)
    else:
        try:
            with st.spinner("번역 중..."):
                st.session_state["result"] = translator.translate(text, target)
            st.session_state["result_lang"] = target
        except translator.TranslationError as exc:
            st.session_state.pop("result", None)
            st.session_state.pop("result_lang", None)
            messages.error(str(exc))

result = st.session_state.get("result")
with st.container(border=True):
    if result:
        st.markdown(f"**{LANGUAGE_LABELS[st.session_state['result_lang']]}**")
        st.code(result, language=None, wrap_lines=True)
    else:
        st.caption("번역 결과가 여기에 표시됩니다")

footer = f"Powered by {config['model']}"
if config["mock"]:
    footer += f" · 모의 모드({config['mock']})"
st.markdown(f'<div class="footer">{html.escape(footer)}</div>', unsafe_allow_html=True)

import json
import os

import httpx
import openai
import streamlit as st
from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-6-astra"
MAX_CHARS = 5000
REQUEST_TIMEOUT = 30
LANGUAGES = {"en": "English", "ja": "Japanese", "fr": "French"}

SYSTEM_PROMPT = (
    "You are a professional translator. Detect the source language automatically.\n"
    "Translate the user's text into {language}.\n"
    "If the text is already in {language}, return it polished.\n"
    "Preserve meaning, tone, formatting, and line breaks.\n"
    "Output only the translation: no explanations, notes, quotation marks, or prefixes.\n"
    'Return ONLY a JSON object of the form {{"translation": "<text>"}}.'
)

MSG_EMPTY = "번역할 글을 입력해 주세요."
MSG_TOO_LONG = f"글이 너무 깁니다. {MAX_CHARS:,}자 이하로 입력해 주세요."
MSG_NO_KEY = "API 키가 설정되지 않았습니다."
MSG_AUTH = "API 키가 올바르지 않습니다. .env 또는 Streamlit Secrets의 OPENAI_API_KEY를 확인해 주세요."
MSG_RATE = "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요."
MSG_TIMEOUT = f"응답 시간이 {REQUEST_TIMEOUT}초를 넘었습니다. 잠시 후 다시 시도하세요."
MSG_CONNECTION = "번역 서버에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요."
MSG_MODEL = "모델을 찾을 수 없습니다. OPENAI_MODEL 설정값을 확인해 주세요."
MSG_FORMAT = "번역 결과를 처리하지 못했습니다. 다시 시도해 주세요."
MSG_UNKNOWN = "번역 중 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

load_dotenv()


class TranslationError(Exception):
    """Carries a Korean message that is safe to show to the user."""


class _FormatError(Exception):
    pass


def _from_secrets(key: str) -> str | None:
    # st.secrets raises when no secrets.toml exists (local dev)
    try:
        value = st.secrets.get(key)
    except Exception:
        return None
    return value or None


def get_config() -> dict[str, str | None]:
    api_key = _from_secrets("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    model = _from_secrets("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    mock = os.getenv("TRANSLATOR_MOCK") or None
    return {"api_key": api_key, "model": model, "mock": mock}


def is_ready(config: dict[str, str | None]) -> bool:
    return bool(config["api_key"] or config["mock"])


def _parse(content: str | None) -> str:
    try:
        data = json.loads(content or "")
    except json.JSONDecodeError as exc:
        raise _FormatError from exc
    if not isinstance(data, dict) or not isinstance(data.get("translation"), str):
        raise _FormatError
    return data["translation"].strip()


def _fake_status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    return cls("mock error", response=response, body=None)


def _mock_request(mode: str, text: str, target: str) -> str:
    if mode == "error_auth":
        raise _fake_status_error(openai.AuthenticationError, 401)
    if mode == "error_rate":
        raise _fake_status_error(openai.RateLimitError, 429)
    if mode == "error_json":
        return "this is not json"
    return json.dumps({"translation": f"[{target.upper()}] {text}"})


def _api_request(config: dict[str, str | None], text: str, target: str) -> str | None:
    client = openai.OpenAI(api_key=config["api_key"], timeout=REQUEST_TIMEOUT, max_retries=1)
    response = client.chat.completions.create(
        model=config["model"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(language=LANGUAGES[target])},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content


def _user_message(exc: openai.OpenAIError) -> str:
    # APITimeoutError subclasses APIConnectionError, so it must be checked first
    if isinstance(exc, openai.AuthenticationError):
        return MSG_AUTH
    if isinstance(exc, openai.RateLimitError):
        return MSG_RATE
    if isinstance(exc, openai.APITimeoutError):
        return MSG_TIMEOUT
    if isinstance(exc, openai.APIConnectionError):
        return MSG_CONNECTION
    if isinstance(exc, openai.NotFoundError):
        return MSG_MODEL
    return MSG_UNKNOWN


def translate(text: str, target: str) -> str:
    """Translate text into the target language ("en", "ja" or "fr"), retrying once on malformed output."""
    if target not in LANGUAGES:
        raise ValueError(f"unsupported target language: {target}")
    if not text.strip():
        raise TranslationError(MSG_EMPTY)
    if len(text) > MAX_CHARS:
        raise TranslationError(MSG_TOO_LONG)

    config = get_config()
    if not is_ready(config):
        raise TranslationError(MSG_NO_KEY)

    for _ in range(2):
        try:
            if config["mock"]:
                content = _mock_request(config["mock"], text, target)
            else:
                content = _api_request(config, text, target)
            return _parse(content)
        except _FormatError:
            continue
        except openai.OpenAIError as exc:
            raise TranslationError(_user_message(exc)) from None
    raise TranslationError(MSG_FORMAT)

"""
llm_router.py

LLM Router - Groq / Gemini / DeepSeek ke beech automatic failover.
---------------------------------------------------------
Kya karta hai:
    - Teeno free-tier providers ko ek "priority list" mein rakhta hai
    - Agar ek provider fail ho jaye (rate limit, timeout, ya koi error),
      LiteLLM khud agla provider try karega - koi manual switching nahi
    - Ek simple function deta hai: ask_llm(prompt) -> jawab (string)

Security note:
    Koi bhi API key is file mein LIKHI NAHI hai. Saari keys .env file se
    load hoti hain (python-dotenv ke through). .env kabhi bhi commit/share
    nahi karna.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from litellm import Router

logger = logging.getLogger(__name__)

# .env file se saari keys environment mein load kar deta hai
load_dotenv()

# ------------------------------------------------------------------ #
# Priority order: pehle Groq (fastest, free), phir Gemini, phir DeepSeek
# Agar ek provider ka key missing hai ya rate-limit hit hota hai, Router
# khud agle model_name par switch kar dega.
# ------------------------------------------------------------------ #
# Har provider ka apna ALAG model_name hai (Router ke random-shuffle se
# bachne ke liye) - Groq "pehli pasand" hai, OpenRouter "backup".
_MODEL_LIST = [
    {
        "model_name": "groq-primary",
        "litellm_params": {
            "model": "groq/llama-3.1-70b-versatile",
            "api_key": os.getenv("GROQ_API_KEY"),
        },
    },
    {
        "model_name": "gemini-backup",
        "litellm_params": {
            "model": "gemini/gemini-2.0-flash",
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    },
    {
        "model_name": "deepseek-backup",
        "litellm_params": {
            "model": "deepseek/deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
        },
    },
    {
        "model_name": "openrouter-backup",
        "litellm_params": {
            "model": "openrouter/openai/gpt-oss-20b:free",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
        },
    },
]

# Priority order: Groq pehle try hoga, agar woh fail ho (rate limit/timeout/
# error) toh Router khud OpenRouter par switch kar dega - yeh guaranteed
# order hai, random shuffle nahi.
_FALLBACK_ORDER = [{"groq-primary": ["gemini-backup", "deepseek-backup", "openrouter-backup"]}]


_router: Router | None = None


def _get_router() -> Router:
    """
    Router ko sirf ek baar banata hai (lazy init), taaki har query par
    dobara-dobara setup na ho.
    """
    global _router
    if _router is None:
        _router = Router(
            model_list=_MODEL_LIST,
            fallbacks=_FALLBACK_ORDER,  # guaranteed order: Groq pehle, phir OpenRouter
            num_retries=2,
            timeout=30,
        )
        logger.info("LLM Router initialized: Groq -> Gemini -> DeepSeek -> OpenRouter.")
    return _router


def _call_router(messages: list[dict]) -> str:
    """
    Shared LLM-call logic - ask_llm() aur ask_llm_with_history() dono isi
    ko use karte hain, taaki error-handling sirf ek jagah likhi ho.
    """
    router = _get_router()
    try:
        response = router.completion(
            model="groq-primary",  # hamesha yahin se shuru hoga
            messages=messages,
        )
        return response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 - kabhi bhi crash nahi hona chahiye
        logger.exception("_call_router: saare providers fail ho gaye.")
        return (
            "AI se jawab nahi mil paya. Ho sakta hai providers "
            "(Groq/OpenRouter) ka aaj ka free quota khatam ho gaya ho, "
            "ya .env mein koi key galat ho. Details logs/coding_ai.log "
            f"mein hain.\n\nTechnical error: {exc}"
        )


def ask_llm(prompt: str, system_message: str | None = None) -> str:
    """
    Ek sawaal (prompt) LLM ko bhejta hai aur jawab (plain text) return
    karta hai. Single-turn use ke liye (history ke bina).
    """
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    return _call_router(messages)


def ask_llm_with_history(messages: list[dict]) -> str:
    """
    Multi-turn conversation ke liye - poori messages list (system +
    purani baatein + naya sawaal) seedhe LLM ko bhejta hai, taaki
    follow-up questions mein pichla context yaad rahe.
    """
    return _call_router(messages)


# ------------------------------------------------------------------ #
# Isko standalone test karne ke liye:
#     python llm_router.py
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_question = "Say hello in one short sentence."
    print("Testing LLM Router...")
    print(ask_llm(test_question))
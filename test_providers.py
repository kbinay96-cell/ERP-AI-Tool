import os
from dotenv import load_dotenv
import requests

load_dotenv()


def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "❌ Key not found in .env"
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            timeout=15
        )
        if res.status_code == 200: return "✅ Working"
        return f"❌ Error {res.status_code}: {res.text[:100]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ Key not found in .env"
    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": "Hi"}]}]},
            timeout=15
        )
        if res.status_code == 200: return "✅ Working"
        return f"❌ Error {res.status_code}: {res.text[:100]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


def test_deepseek():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key: return "❌ Key not found in .env"
    try:
        res = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            timeout=15
        )
        if res.status_code == 200: return "✅ Working"
        return f"❌ Error {res.status_code}: {res.text[:100]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


def test_openrouter():
    """🆕 OpenRouter test - Agent isi par chalta hai (6 free models)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return "❌ Key not found in .env"
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # OpenRouter recommends these headers (optional but good practice)
                "HTTP-Referer": "http://localhost",
                "X-Title": "ERP-AI-Tool",
            },
            json={
                "model": "openai/gpt-oss-20b:free",  # wahi model jo llm_router.py mein hai
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            },
            timeout=20
        )
        if res.status_code == 200: return "✅ Working"
        return f"❌ Error {res.status_code}: {res.text[:150]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


def test_openrouter_agent_models():
    """🆕 Agent ke 6 free models ka quick health check."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return "❌ Key not found in .env"

    agent_models = [
        ("Nemotron-Lightning", "nvidia/nemotron-3.5-lightning:free"),
        ("Nemotron-Ultra-550B", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        ("Gemma-4-31B", "google/gemma-4-31b-it:free"),
        ("Nemotron-Super-120B", "nvidia/nemotron-3-super-120b-a12b:free"),
        ("Gemma-4-26B", "google/gemma-4-26b-a4b-it:free"),
        ("North-Mini-Code", "cohere/north-mini-code:free"),
    ]

    results = []
    for name, slug in agent_models:
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": slug,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
                timeout=20
            )
            if res.status_code == 200:
                results.append(f"   ✅ {name}")
            else:
                results.append(f"   ❌ {name} — Error {res.status_code}")
        except Exception as e:
            results.append(f"   ❌ {name} — {str(e)[:50]}")

    return "\n".join(results)


print("=" * 55)
print("       API Keys Testing - ERP-AI-Tool")
print("=" * 55)
print(f"1. Groq (llama-3.3-70b-versatile)  : {test_groq()}")
print(f"2. Gemini (gemini-2.0-flash)       : {test_gemini()}")
print(f"3. DeepSeek (deepseek-chat)        : {test_deepseek()}")
print(f"4. OpenRouter (gpt-oss-20b:free)   : {test_openrouter()}")
print("-" * 55)
print("🤖 Agent Models Health Check (OpenRouter):")
print(test_openrouter_agent_models())
print("=" * 55)
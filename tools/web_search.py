"""
tools/web_search.py

Web Search Tool - ERP-AI-Tool
Agent ko web se information laane mein madad karta hai.
Bina kisi paid API ke - DuckDuckGo HTML search use karta hai.
"""

import re
import urllib.request
import urllib.parse
from typing import Optional


def search_web(query: str, max_results: int = 5) -> str:
    """
    DuckDuckGo HTML search se results lao.
    Bilkul FREE hai - koi API key nahi chahiye.
    """
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Extract search results (title + snippet + URL)
        results = []

        # DuckDuckGo HTML format: <a class="result__a" href="...">Title</a>
        title_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'

        titles = re.findall(title_pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (url_raw, title_raw) in enumerate(titles[:max_results]):
            # Clean HTML tags
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

            # DuckDuckGo redirects - extract actual URL
            if "uddg=" in url_raw:
                actual_url = urllib.parse.unquote(
                    re.search(r"uddg=([^&]+)", url_raw).group(1)
                )
            else:
                actual_url = url_raw

            results.append(
                f"📌 Result {i + 1}: {title}\n"
                f"   🔗 {actual_url}\n"
                f"   📝 {snippet[:200]}"
            )

        if not results:
            return f"🔍 No results found for: '{query}'"

        header = f"🌐 Web Search: '{query}' ({len(results)} results)\n"
        header += "=" * 60 + "\n"
        return header + "\n\n".join(results)

    except Exception as exc:
        return f"❌ Web search failed: {exc}"


def fetch_page_summary(url: str, max_chars: int = 3000) -> str:
    """
    Kisi webpage ka content fetch karke summary return karo.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Remove script, style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"\s+", " ", html).strip()

        if len(html) > max_chars:
            html = html[:max_chars] + "... [truncated]"

        header = f"📄 Page: {url}\n"
        header += "=" * 60 + "\n"
        return header + html

    except Exception as exc:
        return f"❌ Failed to fetch page: {exc}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tools/web_search.py [--url URL] \"query\"")
        sys.exit(1)

    if sys.argv[1] == "--url":
        if len(sys.argv) < 3:
            print("Missing URL")
            sys.exit(1)
        print(fetch_page_summary(sys.argv[2]))
    else:
        query = " ".join(sys.argv[1:])
        print(search_web(query))
"""
ui/markdown_renderer.py

Converts LLM markdown output (headings, code blocks, bold, lists) into
HTML for QTextEdit.setHtml() - lightweight alternative to QWebEngineView.
Layer: UI helper (pure function, no state).
"""

import html
import markdown as md_lib

_CSS = """
<style>
body { font-family: Segoe UI, sans-serif; font-size: 14px; }
h2 { color: #7C4DFF; margin-top: 14px; }
code { background-color: #2A2A35; color: #E8E8ED; padding: 2px 5px; border-radius: 4px; }
pre { background-color: #1E1E28; color: #E8E8ED; padding: 10px; border-radius: 6px; overflow-x: auto; }
strong { color: #FFFFFF; }
</style>
"""


def render_markdown_to_html(text: str) -> str:
    """Safe: escapes raw HTML in the source text first (prevents any
    accidental HTML injection from LLM output), then applies markdown."""
    escaped = html.escape(text)
    body_html = md_lib.markdown(escaped, extensions=["fenced_code", "tables"])
    return f"{_CSS}<body>{body_html}</body>"
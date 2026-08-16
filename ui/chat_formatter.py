"""
ui/chat_formatter.py

Chat message ko Claude jaisi "bubble" style mein HTML banata hai, taaki
QTextEdit (jo rich-text/HTML support karta hai) mein achha dikhe.

Yeh file kisi cheez ko crash nahi karti - agar formatting mein koi masla
aaye, plain escaped text hi dikha deta hai, taaki chat kabhi khaali ya
broken na dikhe.

Layer: UI helper (pure function, koi Qt widget nahi banata, sirf HTML
string return karta hai) - koi business logic, koi LLM call nahi.

THEME SUPPORT: format_message_html() ab `theme` parameter leta hai
("light" ya "dark"). Har theme ka apna color palette hai - bubble
background, text color, code block colors - sab theme ke hisaab se
switch ho jaate hain. Caller (main_window.py) current theme track
karta hai aur toggle hone par poori chat log ko naye theme ke saath
re-render karta hai (_rerender_chat_log()).
"""

from __future__ import annotations

import html
import re

_MONOSPACE_FONT = "Consolas, 'Courier New', monospace"

DEFAULT_FONT_SIZE_PT = 11
MIN_FONT_SIZE_PT = 8
MAX_FONT_SIZE_PT = 20

DEFAULT_THEME = "light"

# ------------------------------------------------------------------ #
# Theme palettes - har role/element ke liye alag color light aur dark
# dono ke liye. Naya theme add karna ho to bas ek aur dict entry add
# karo, baaki code automatically kaam karega.
# ------------------------------------------------------------------ #
_THEMES: dict[str, dict[str, str]] = {
    "light": {
        "user_bubble_bg": "#DCEEFB",
        "assistant_bubble_bg": "#F1F0F5",
        "error_bubble_bg": "#FBDCDC",
        "system_bubble_bg": "#EFEFEF",
        "text_color": "#1B2430",
        "label_color": "#1B2430",
        "code_block_bg": "#1E1E2E",
        "code_block_fg": "#D4D4D4",
        "inline_code_bg": "#E4E4EA",
        "inline_code_fg": "#1B2430",
        "chat_area_bg": "#FFFFFF",
    },
    "dark": {
        "user_bubble_bg": "#2B4C6F",
        "assistant_bubble_bg": "#2A2A35",
        "error_bubble_bg": "#5C2626",
        "system_bubble_bg": "#33333D",
        "text_color": "#E8E8ED",
        "label_color": "#FFFFFF",
        "code_block_bg": "#0F0F14",
        "code_block_fg": "#D4D4D4",
        "inline_code_bg": "#3A3A45",
        "inline_code_fg": "#E8E8ED",
        "chat_area_bg": "#1A1A22",
    },
}


def _get_theme(theme: str) -> dict[str, str]:
    return _THEMES.get(theme, _THEMES[DEFAULT_THEME])


def get_chat_area_background(theme: str) -> str:
    """Main window apne QTextEdit ka background isi se set karta hai,
    taaki bubble colors aur poora chat area ka background match kare."""
    return _get_theme(theme)["chat_area_bg"]


def _markdown_to_html(
    raw_text: str, palette: dict[str, str], font_size_pt: int = DEFAULT_FONT_SIZE_PT
) -> str:
    """
    Chhota, safe markdown->HTML converter. Poore CommonMark spec ko
    support nahi karta - sirf woh cheezein jo LLM jawabon mein sabse
    zyada aati hain: **bold**, *italic*, `inline code`, ```code
    blocks```, - bullet lists, 1. numbered lists, aur # headers.

    `font_size_pt` se code/header font bhi us hisaab se scale hote hain,
    taaki poora message ek hi zoom level par consistent dikhe.

    `palette` current theme ke colors deta hai (code block bg/fg,
    inline code bg/fg) - light/dark dono ke liye same logic, sirf
    colors alag.
    """
    text = raw_text.replace("\r\n", "\n")
    # Lagatar 3+ khaali lines ko ek blank line jitna hi rakhte hain,
    # warna bubbles ke beech bahut zyada khaali jagah ban jaati hai.
    text = re.sub(r"\n{3,}", "\n\n", text)

    code_font_size = max(font_size_pt - 1, MIN_FONT_SIZE_PT)

    # ---- Step 1: fenced code blocks ko pehle nikal lete hain, taaki
    # unke andar ka content baad ki formatting (bold/italic/escaping)
    # se bach jaye. ----
    code_blocks: list[str] = []

    def _stash_code_block(match: "re.Match[str]") -> str:
        code_content = match.group(2)
        escaped = html.escape(code_content)
        block_html = (
            f'<table cellspacing="0" cellpadding="8" width="100%" bgcolor="{palette["code_block_bg"]}">'
            f'<tr><td><span style="font-family:{_MONOSPACE_FONT}; font-size:{code_font_size}pt; '
            f'color:{palette["code_block_fg"]}; white-space:pre-wrap;">{escaped}</span></td></tr></table>'
        )
        code_blocks.append(block_html)
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r"```(\w*)\n?(.*?)```", _stash_code_block, text, flags=re.DOTALL)

    # ---- Step 2: inline code `...` bhi nikal lete hain ----
    inline_codes: list[str] = []

    def _stash_inline_code(match: "re.Match[str]") -> str:
        escaped = html.escape(match.group(1))
        inline_codes.append(
            f'<span style="background-color:{palette["inline_code_bg"]}; padding:1px 4px; '
            f'font-family:{_MONOSPACE_FONT}; font-size:{code_font_size}pt; '
            f'color:{palette["inline_code_fg"]};">{escaped}</span>'
        )
        return f"\x00INLINECODE{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _stash_inline_code, text)

    # ---- Step 3: baaki text ko HTML-safe escape karte hain ----
    text = html.escape(text)

    # ---- Step 4: bold aur italic (escape ke baad, kyunki ** aur * HTML
    # escape se prabhavit nahi hote). Bold ko theme ke text_color ke
    # saath explicit rakhte hain taaki dark theme mein bhi bold text
    # saaf dikhe (Gemini-style: bold thoda zyada prominent) ----
    text = re.sub(
        r"\*\*(.+?)\*\*",
        rf'<b style="color:{palette["text_color"]};">\1</b>',
        text,
    )
    text = re.sub(r"(?<!\w)\*(?!\*)(.+?)(?<!\*)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)

    # ---- Step 5: line-by-line - headers aur lists handle karte hain ----
    lines = text.split("\n")
    output_lines: list[str] = []
    list_mode: str | None = None  # "ul" ya "ol" ya None

    def _close_list() -> None:
        nonlocal list_mode
        if list_mode is not None:
            output_lines.append(f"</{list_mode}>")
            list_mode = None

    for line in lines:
        stripped = line.strip()

        header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)

        if header_match:
            _close_list()
            level = len(header_match.group(1))
            size = font_size_pt + max(6 - level, 1)
            output_lines.append(
                f'<div style="font-size:{size}pt; font-weight:bold; margin:6px 0 2px 0; '
                f'color:{palette["text_color"]};">'
                f"{header_match.group(2)}</div>"
            )
        elif bullet_match:
            if list_mode != "ul":
                _close_list()
                output_lines.append("<ul style='margin:4px 0 4px 18px;'>")
                list_mode = "ul"
            output_lines.append(f"<li>{bullet_match.group(1)}</li>")
        elif numbered_match:
            if list_mode != "ol":
                _close_list()
                output_lines.append("<ol style='margin:4px 0 4px 18px;'>")
                list_mode = "ol"
            output_lines.append(f"<li>{numbered_match.group(1)}</li>")
        elif stripped == "":
            _close_list()
            output_lines.append("<br/>")
        else:
            _close_list()
            output_lines.append(line + "<br/>")

    _close_list()
    text = "\n".join(output_lines)

    # ---- Step 6: stashed code blocks / inline code wapas daal dete hain ----
    for index, block_html in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{index}\x00", block_html)
    for index, inline_html in enumerate(inline_codes):
        text = text.replace(f"\x00INLINECODE{index}\x00", inline_html)

    return text


def _wrap_bubble(
    label: str, body_html: str, bg_color: str, align: str,
    font_size_pt: int, palette: dict[str, str], copy_id: int | None = None
) -> str:
    copy_link = ""
    if copy_id is not None:
        copy_link = (
            f'<div align="right" style="margin-top:2px;">'
            f'<a href="copy:{copy_id}" style="font-size:9pt; color:#888888; '
            f'text-decoration:none;">📋 Copy</a></div>'
        )
    return (
        f'<table align="{align}" width="72%" cellspacing="0" cellpadding="10" '
        f'bgcolor="{bg_color}"><tr><td>'
        f'<span style="font-family:\'Segoe UI\', Arial, sans-serif; '
        f'font-size:{font_size_pt}pt; color:{palette["text_color"]};">'
        f'<b style="color:{palette["label_color"]};">{label}</b><br/>{body_html}'
        f"</span>{copy_link}</td></tr></table>"
        f'<div style="margin:2px 0;"></div>'
    )


def format_message_html(
    role: str,
    raw_text: str,
    font_size_pt: int = DEFAULT_FONT_SIZE_PT,
    theme: str = DEFAULT_THEME,
    copy_id: int | None = None,
) -> str:
    """
    Public entry point. `role` in se ek hona chahiye: "user", "assistant",
    "error", "system".

    `font_size_pt` chat ke current zoom level ko control karta hai (Main
    Window ke A-/A+ buttons ye value badalte hain aur poori chat log ko
    is naye size ke saath dobara render karte hain).

    `theme` "light" ya "dark" - Main Window ke theme-toggle button ye
    value badalta hai aur poori chat log ko naye theme ke saath dobara
    render karta hai (_rerender_chat_log()).

    Kabhi bhi exception nahi uthayega - agar formatting fail ho jaye,
    plain escaped text hi ek simple bubble mein dikha dega.
    """
    font_size_pt = max(MIN_FONT_SIZE_PT, min(MAX_FONT_SIZE_PT, font_size_pt))
    palette = _get_theme(theme)

    try:
        body_html = _markdown_to_html(raw_text, palette, font_size_pt=font_size_pt)
    except Exception:  # noqa: BLE001 - chat display kabhi crash nahi honi chahiye
        body_html = html.escape(raw_text).replace("\n", "<br/>")

    if role == "user":
        return _wrap_bubble("You", body_html, palette["user_bubble_bg"], "right", font_size_pt, palette, copy_id)
    if role == "assistant":
        return _wrap_bubble("Assistant", body_html, palette["assistant_bubble_bg"], "left", font_size_pt, palette, copy_id)
    if role == "error":
        return _wrap_bubble("Error", body_html, palette["error_bubble_bg"], "left", font_size_pt, palette, copy_id)
    return _wrap_bubble("System", body_html, palette["system_bubble_bg"], "left", font_size_pt, palette, copy_id)

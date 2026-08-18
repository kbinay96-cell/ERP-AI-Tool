"""
ui/intent_router.py
Smart Intent Router - Unified Agentic Chat (T01 + T10)
---------------------------------------------------------
Ab HARD CODED keywords nahi hain.
LLM khud decide karta hai ki user ka input TASK hai ya QUESTION.
User kuch bhi likhe - koi bhi language, koi bhi words - LLM samjhega.

Fallback: Agar LLM fail ho jaye to simple heuristics use hote hain.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """User input ka detected intent."""
    QUESTION = "question"
    TASK = "task"
    COMMAND = "command"
    APPROVAL = "approval"
    REJECTION = "rejection"
    KILL = "kill"
    AMBIGUOUS = "ambiguous"


@dataclass
class IntentResult:
    """Intent detection ka result."""
    intent: IntentType
    confidence: float
    reason: str


# ------------------------------------------------------------------ #
# FAST CHECKS (LLM call se pehle - zero cost)
# ------------------------------------------------------------------ #

COMMAND_KEYWORDS = [
    "blueprint status", "blueprint tasks", "blueprint compare",
    "bp status", "bp tasks", "bp compare", "progress",
]

APPROVAL_KEYWORDS = [
    "approve", "yes", "haan", "han", "ok", "done", "y",
    "chalo", "sahi hai", "theek hai", "kar do", "kardo",
    "ha", "ji haan", "bilkul", "aage badho", "continue",
    "proceed", "go ahead", "sure", "okay", "okk",
]

REJECTION_KEYWORDS = [
    "reject", "no", "nahi", "nhi", "cancel", "n",
    "rehne do", "skip", "mat karo", "mat", "nahi chahiye",
    "band karo", "chhod do", "drop", "leave it",
]

KILL_KEYWORDS = [
    "kill", "stop", "band karo", "band kar", "roko", "abort",
    "bas karo", "khatam karo", "terminate", "exit", "force stop",
]


# ------------------------------------------------------------------ #
# MAIN DETECTION FUNCTION
# ------------------------------------------------------------------ #

def detect_intent(user_text: str, agent_waiting: bool = False) -> IntentResult:
    """
    Main entry point.
    Priority:
    1. Agent waiting → approval/rejection/kill check (fast, no LLM)
    2. Commands check (fast, no LLM)
    3. /agent prefix (fast, no LLM)
    4. LLM-based classification (smart, any language)
    """
    text_lower = user_text.strip().lower()

    if not text_lower:
        return IntentResult(IntentType.AMBIGUOUS, 0.0, "Empty input")

    # Priority 1: Agent waiting hai to approval/rejection/kill
    if agent_waiting:
        approval_result = _detect_approval_intent(text_lower)
        if approval_result.intent != IntentType.AMBIGUOUS:
            return approval_result

    # Priority 2: Commands
    for cmd in COMMAND_KEYWORDS:
        if cmd in text_lower:
            return IntentResult(IntentType.COMMAND, 0.95, f"Command: {cmd}")

    # Priority 3: /agent prefix
    if text_lower.startswith("/agent"):
        return IntentResult(IntentType.TASK, 1.0, "Explicit /agent command")

    # Priority 4: LLM-based classification (SMART - no hardcoded keywords)
    llm_result = _classify_with_llm(user_text)
    if llm_result is not None:
        return llm_result

    # Fallback: Agar LLM fail ho jaye to simple heuristic
    return _fallback_detection(text_lower)


def _detect_approval_intent(text_lower: str) -> IntentResult:
    """Agent waiting ke waqt user response detect karo."""
    # Kill (highest priority)
    for kw in KILL_KEYWORDS:
        if kw in text_lower:
            return IntentResult(IntentType.KILL, 0.95, f"Kill: {kw}")

    # Approval
    for kw in APPROVAL_KEYWORDS:
        if (text_lower == kw or
                text_lower.startswith(kw + " ") or
                text_lower.endswith(" " + kw) or
                kw in text_lower):
            return IntentResult(IntentType.APPROVAL, 0.9, f"Approval: {kw}")

    # Rejection
    for kw in REJECTION_KEYWORDS:
        if (text_lower == kw or
                text_lower.startswith(kw + " ") or
                text_lower.endswith(" " + kw) or
                kw in text_lower):
            return IntentResult(IntentType.REJECTION, 0.9, f"Rejection: {kw}")

    return IntentResult(IntentType.AMBIGUOUS, 0.0, "No approval/rejection detected")


def _classify_with_llm(user_text: str) -> IntentResult | None:
    """
    LLM se intent classify karo.
    User kuch bhi likhe - LLM samjhega.
    Koi hardcoded keyword nahi chahiye.
    """
    try:
        from llm_router import ask_llm

        prompt = f"""Classify the following user message into exactly ONE category.

Categories:
- TASK: User wants something to be DONE (create file, edit code, add function, fix bug, run command, build something, modify something, write code, delete something)
- QUESTION: User wants to KNOW something (explanation, how something works, what is something, compare, describe)

User message: "{user_text}"

Reply with ONLY one word: TASK or QUESTION"""

        response = ask_llm(prompt).strip().upper()

        if "TASK" in response:
            return IntentResult(IntentType.TASK, 0.90, "LLM classified as TASK")
        elif "QUESTION" in response:
            return IntentResult(IntentType.QUESTION, 0.90, "LLM classified as QUESTION")
        else:
            return None  # Unclear response, fallback

    except Exception:
        return None  # LLM fail, fallback


def _fallback_detection(text_lower: str) -> IntentResult:
    """
    Fallback: Agar LLM fail ho jaye.
    Simple heuristic - action verbs check karo.
    """
    action_words = [
        "banao", "bana", "create", "add", "edit", "fix", "modify",
        "delete", "remove", "update", "write", "implement", "refactor",
        "optimize", "change", "replace", "install", "run", "execute",
        "debug", "solve", "theek", "likho", "likh", "karo", "kar",
        "daalo", "daal", "improve", "better", "naya", "new",
    ]

    question_words = [
        "kya", "kaise", "kyun", "kyu", "kaun", "samjhaao", "samjhao",
        "batao", "bata", "what", "how", "why", "when", "where", "who",
        "explain", "describe", "tell", "show", "difference", "compare",
        "which", "can you", "kya hai", "kaam karta",
    ]

    action_score = sum(1 for w in action_words if w in text_lower)
    question_score = sum(1 for w in question_words if w in text_lower)

    if action_score > question_score:
        return IntentResult(IntentType.TASK, 0.6, f"Fallback: action words ({action_score})")
    elif question_score > action_score:
        return IntentResult(IntentType.QUESTION, 0.6, f"Fallback: question words ({question_score})")
    else:
        # Default: Question (safe - read-only)
        return IntentResult(IntentType.QUESTION, 0.5, "Fallback: default to question (safe)")


# ------------------------------------------------------------------ #
# STANDALONE TEST
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    test_cases = [
        ("supplier_engine mein search function add karo", False),
        ("date_engine kaise kaam karta hai?", False),
        ("blueprint status", False),
        ("approve", True),
        ("kar do", True),
        ("nahi", True),
        ("kill", True),
        ("/agent test file banao", False),
        ("hello kaise ho", False),
        ("code improve karo", False),
        ("naya feature daalo", False),
        ("ye kya hai", False),
    ]

    print("=" * 60)
    print("  Intent Router - Test Results (LLM-based)")
    print("=" * 60)

    for text, waiting in test_cases:
        result = detect_intent(text, agent_waiting=waiting)
        print(f"\n  Input: '{text}'")
        print(f"  Agent Waiting: {waiting}")
        print(f"  → Intent: {result.intent.value}")
        print(f"  → Confidence: {result.confidence:.0%}")
        print(f"  → Reason: {result.reason}")

    print("\n" + "=" * 60)
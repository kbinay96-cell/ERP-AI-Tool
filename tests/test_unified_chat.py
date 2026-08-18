import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.intent_router import detect_intent, IntentType


class TestIntentDetection:
    def test_simple_question(self):
        result = detect_intent("date_engine kaise kaam karta hai?")
        assert result.intent == IntentType.QUESTION

    def test_simple_task(self):
        result = detect_intent("supplier_engine mein function add karo")
        assert result.intent == IntentType.TASK

    def test_task_natural_language(self):
        result = detect_intent("code improve karo")
        assert result.intent == IntentType.TASK

    def test_task_hinglish(self):
        result = detect_intent("naya feature daalo")
        assert result.intent == IntentType.TASK

    def test_question_hinglish(self):
        result = detect_intent("ye kya hai")
        assert result.intent == IntentType.QUESTION

    def test_explicit_agent_command(self):
        result = detect_intent("/agent test file banao")
        assert result.intent == IntentType.TASK
        assert result.confidence == 1.0

    def test_empty_input(self):
        result = detect_intent("")
        assert result.intent == IntentType.AMBIGUOUS


class TestApprovalDetection:
    def test_approve_english(self):
        result = detect_intent("approve", agent_waiting=True)
        assert result.intent == IntentType.APPROVAL

    def test_approve_hinglish(self):
        result = detect_intent("haan", agent_waiting=True)
        assert result.intent == IntentType.APPROVAL

    def test_approve_natural(self):
        result = detect_intent("kar do", agent_waiting=True)
        assert result.intent == IntentType.APPROVAL

    def test_reject_english(self):
        result = detect_intent("reject", agent_waiting=True)
        assert result.intent == IntentType.REJECTION

    def test_reject_hinglish(self):
        result = detect_intent("nahi", agent_waiting=True)
        assert result.intent == IntentType.REJECTION

    def test_kill_command(self):
        result = detect_intent("kill", agent_waiting=True)
        assert result.intent == IntentType.KILL

    def test_kill_hinglish(self):
        result = detect_intent("band karo", agent_waiting=True)
        assert result.intent == IntentType.KILL


class TestBlueprintCommands:
    def test_blueprint_status(self):
        result = detect_intent("blueprint status")
        assert result.intent == IntentType.COMMAND

    def test_bp_status_short(self):
        result = detect_intent("bp status")
        assert result.intent == IntentType.COMMAND

    def test_progress_command(self):
        result = detect_intent("progress")
        assert result.intent == IntentType.COMMAND


class TestNotApprovalWhenNotWaiting:
    def test_haan_not_waiting(self):
        result = detect_intent("haan", agent_waiting=False)
        assert result.intent != IntentType.APPROVAL

    def test_approve_not_waiting(self):
        result = detect_intent("approve", agent_waiting=False)
        assert result.intent != IntentType.APPROVAL
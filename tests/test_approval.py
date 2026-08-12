from codex_cost_optimizer.approval import TerminalApprovalProvider
from codex_cost_optimizer.domain import Confidence, ReasoningEffort, RoutingRecommendation, TaskPhase


def rec():
    return RoutingRecommendation("gpt-sol", ReasoningEffort.HIGH, "gpt-luna", ReasoningEffort.LOW, "A etapa tornou-se mecânica.", "Redução esperada de custo.", TaskPhase.MECHANICAL, Confidence.HIGH, "abc")


def test_empty_answer_is_not_authorization():
    provider = TerminalApprovalProvider(input_fn=lambda _: "")
    assert provider.request(rec()).approved is False


def test_only_explicit_yes_is_authorized():
    assert TerminalApprovalProvider(input_fn=lambda _: "sim").request(rec()).approved is True
    assert TerminalApprovalProvider(input_fn=lambda _: "talvez").request(rec()).approved is False


def test_message_contains_required_context():
    seen = []
    TerminalApprovalProvider(input_fn=lambda prompt: seen.append(prompt) or "n").request(rec())
    text = seen[0]
    assert "gpt-sol / high" in text
    assert "gpt-luna / low" in text
    assert "A etapa tornou-se mecânica." in text
    assert "Redução esperada de custo." in text
    assert "[S/N]" in text

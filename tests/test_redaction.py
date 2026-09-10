"""Secret redaction tests."""

from unittest.mock import MagicMock, patch

from workdiary_agent.nodes.extract import extract_node
from workdiary_agent.redaction import redact_secrets
from workdiary_agent.state import StructuredInfo


def test_common_credentials_are_redacted():
    text = (
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz "
        "Authorization: Bearer abcdefghijklmnop "
        "AWS AKIAABCDEFGHIJKLMNOP "
        "CUSTOM_AUTH_TOKEN=opaquecredentialvalue"
    )

    redacted = redact_secrets(text)

    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "AKIAABCDEFGHIJKLMNOP" not in redacted
    assert "opaquecredentialvalue" not in redacted
    assert redacted.count("[REDACTED_SECRET]") == 4


def test_extract_sends_redacted_text_but_keeps_state_local():
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    mock_llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = StructuredInfo(tasks=["完成配置检查"])
    mock_llm.with_structured_output.return_value = structured
    state = {"raw_input": f"今天检查配置 {secret}"}

    with patch("workdiary_agent.nodes.extract.make_llm", return_value=mock_llm):
        extract_node(state)

    messages = structured.invoke.call_args.args[0]
    prompt = "\n".join(str(message.content) for message in messages)
    assert secret not in prompt
    assert "[REDACTED_SECRET]" in prompt
    assert secret in state["raw_input"]

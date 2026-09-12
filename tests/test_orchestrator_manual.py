"""
Manual verification script for LLM Orchestrator (Step 12B).

Verifies the orchestrator foundation locally without requiring API keys
or making real LLM / network requests.

Run from the project root:
    python tests/test_orchestrator_manual.py
"""

import os
import sys
import urllib.request

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm.orchestrator import (
    DEFAULT_MAX_INPUT_CHARS,
    LLMOrchestrator,
    chunk_or_truncate_text,
)


def test_1_short_text() -> bool:
    """Test 1: Short text HTML cleaning & chunking."""
    sample_html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "    <title>AI Frontier Inc Announcement</title>\n"
        "    <script>alert('tracking script');</script>\n"
        "    <style>body { background: #fff; }</style>\n"
        "</head>\n"
        "<body>\n"
        "    <h1>AI Frontier Inc Announces Series A</h1>\n"
        "    <p>AI Frontier Inc, an enterprise AI startup with 42 employees, has raised $10M.</p>\n"
        "</body>\n"
        "</html>"
    )

    result = chunk_or_truncate_text(sample_html)

    # Verification: scripts, styles, and tags removed
    assert "<script>" not in result, "Scripts were not stripped"
    assert "<style>" not in result, "Styles were not stripped"
    assert "<h1>" not in result, "HTML tags were not stripped"
    assert "<p>" not in result, "Paragraph tags were not stripped"

    # Verification: resulting text is non-empty and content is preserved
    assert len(result) > 0, "Resulting text is empty"
    assert "AI Frontier Inc" in result, "Entity name missing from cleaned text"
    assert "42 employees" in result, "Employee count missing from cleaned text"

    return True


def test_2_long_text() -> bool:
    """Test 2: Deterministic long text truncation preserving head and tail context."""
    head_marker = "START_CONTEXT: NovaAI was founded in 2024 by Jane Doe."
    tail_marker = "END_CONTEXT: Contact NovaAI at info@novaai.example for hiring inquiries."

    # Build deterministic text significantly exceeding DEFAULT_MAX_INPUT_CHARS
    filler = "\n\n".join([
        f"Paragraph {i}: Detailed discussion on large-scale model architectures, "
        "synthetic data curation strategies, and automated alignment verification."
        for i in range(250)
    ])
    long_text = f"{head_marker}\n\n{filler}\n\n{tail_marker}"

    assert len(long_text) > DEFAULT_MAX_INPUT_CHARS, (
        f"Generated text ({len(long_text)}) must exceed max limit ({DEFAULT_MAX_INPUT_CHARS})"
    )

    result = chunk_or_truncate_text(long_text, max_chars=DEFAULT_MAX_INPUT_CHARS)

    # Verification: length bounded within DEFAULT_MAX_INPUT_CHARS
    assert len(result) <= DEFAULT_MAX_INPUT_CHARS, (
        f"Truncated text ({len(result)}) exceeds max limit ({DEFAULT_MAX_INPUT_CHARS})"
    )

    # Verification: beginning and ending portions preserved
    assert "START_CONTEXT: NovaAI was founded in 2024" in result, "Beginning context was lost"
    assert "END_CONTEXT: Contact NovaAI at info@novaai.example" in result, "Ending context was lost"
    assert "[... content truncated for context limits ...]" in result, "Truncation marker missing"

    return True


def test_3_missing_api_keys() -> bool:
    """Test 3: Graceful fallback when all API keys are unavailable."""
    keys = ["GEMINI_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY"]
    saved_env = {k: os.environ.get(k) for k in keys}

    for k in keys:
        os.environ.pop(k, None)

    try:
        orchestrator = LLMOrchestrator()
        sample_text = "Acme AI is an AI startup with 25 employees."
        result = orchestrator.extract(sample_text, "STARTUP")

        # Verification: structured failure without crashing or hallucinating
        assert result.get("success") is False, f"Expected success == False, got {result.get('success')}"
        assert result.get("provider") is None, f"Expected provider is None, got {result.get('provider')}"
        assert result.get("data") is None, f"Expected data is None, got {result.get('data')}"
        assert "error" in result and result["error"], "Expected non-empty error message"

    finally:
        # Restore environment variables
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    return True


def test_4_no_network_dependency() -> bool:
    """Test 4: Verify zero network calls occur when keys are absent or text is processed."""
    def forbidden_urlopen(*args, **kwargs):
        raise AssertionError("Network call attempted during offline test!")

    original_urlopen = urllib.request.urlopen
    urllib.request.urlopen = forbidden_urlopen

    try:
        # Create orchestrator with explicitly absent keys
        orchestrator = LLMOrchestrator(
            gemini_api_key="",
            groq_api_key="",
            deepseek_api_key="",
        )
        sample_text = "Acme AI is an AI startup with 25 employees."
        result = orchestrator.extract(sample_text, "STARTUP")

        assert result.get("success") is False, "Expected extraction failure"
        assert result.get("provider") is None, "Expected no provider used"
    finally:
        urllib.request.urlopen = original_urlopen

    return True


def main() -> None:
    print("=" * 60)
    print("LLM Orchestrator - Manual Verification")
    print("=" * 60)

    t1 = test_1_short_text()
    print("Test 1: PASS" if t1 else "Test 1: FAIL")

    t2 = test_2_long_text()
    print("Test 2: PASS" if t2 else "Test 2: FAIL")

    t3 = test_3_missing_api_keys()
    print("Test 3: PASS" if t3 else "Test 3: FAIL")

    t4 = test_4_no_network_dependency()
    print("Test 4: PASS" if t4 else "Test 4: FAIL")

    print("=" * 60)
    print("All tests completed successfully.")


if __name__ == "__main__":
    main()

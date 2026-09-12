"""
LLM Orchestrator for the AI Intelligence Pipeline.

Provides a unified, resilient extraction interface across multiple LLM providers:
1. Gemini Flash (Google)
2. Groq Llama (Groq)
3. DeepSeek (DeepSeek)

Features:
- Cascading provider fallback in exact priority order
- Intelligent text chunking preserving head and tail context
- Exponential backoff with random jitter and Retry-After header support on HTTP 429
- Dynamic payload shrinkage and retry on HTTP 413
- Robust JSON response extraction with anti-hallucination guardrails
- Independent from crawler, database, and storage subsystems
"""

import html
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from dotenv import load_dotenv

# Load local .env file variables if present
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_INPUT_CHARS: int = 12_000
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_INITIAL_BACKOFF: float = 1.0
DEFAULT_REQUEST_TIMEOUT: float = 30.0

# API Endpoints
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEEPSEEK_API_ENDPOINT = "https://api.deepseek.com/chat/completions"

# Default Model Names
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


# ---------------------------------------------------------------------------
# Custom Exceptions for Flow Control
# ---------------------------------------------------------------------------

class MissingAPIKeyError(Exception):
    """Raised when an API key is required but missing."""


class InvalidResponseError(Exception):
    """Raised when an LLM provider returns unparseable or malformed output."""


# ---------------------------------------------------------------------------
# Intelligent Text Chunking & Sanitization
# ---------------------------------------------------------------------------

def clean_html_content(raw_text: str) -> str:
    """
    Sanitize raw HTML into readable plain text before passing to an LLM.
    Strips scripts, styles, tags, decodes HTML entities, and condenses whitespace.
    """
    if not raw_text:
        return ""

    # Remove script and style elements
    cleaned = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)

    # Replace block break tags with newlines
    cleaned = re.sub(r"</?(p|div|br|h[1-6]|li|tr|article|section)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)

    # Strip all remaining tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)

    # Unescape HTML entities (e.g., &amp; -> &)
    cleaned = html.unescape(cleaned)

    # Normalize whitespace: collapse horizontal whitespace and excessive newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    condensed = "\n".join(line for line in lines if line)
    return condensed


def chunk_or_truncate_text(
    text: str,
    max_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> str:
    """
    Intelligently truncate text to stay within max_chars.

    Preserves both beginning (head) and ending (tail) context, preferring
    natural paragraph or sentence boundaries rather than mid-word cuts.
    """
    # Clean HTML markup if present
    cleaned = clean_html_content(text)

    if len(cleaned) <= max_chars:
        return cleaned

    marker = "\n\n[... content truncated for context limits ...]\n\n"
    budget = max_chars - len(marker)
    if budget <= 100:
        return cleaned[:max_chars]

    # Allocate ~65% to beginning context (intro, entities) and ~35% to ending context
    head_target = int(budget * 0.65)
    tail_target = budget - head_target

    # Find clean cut for head portion (look back up to 25% of head_target)
    head_candidate = cleaned[:head_target]
    search_head_start = int(head_target * 0.75)
    p_idx = head_candidate.rfind("\n\n", search_head_start)
    if p_idx != -1:
        head_cut = p_idx
    else:
        s_idx = max(
            head_candidate.rfind(". ", search_head_start),
            head_candidate.rfind(".\n", search_head_start),
        )
        if s_idx != -1:
            head_cut = s_idx + 1
        else:
            w_idx = head_candidate.rfind(" ", search_head_start)
            head_cut = w_idx if w_idx != -1 else head_target

    head_part = head_candidate[:head_cut].rstrip()

    # Find clean cut for tail portion (look forward up to 25% of tail_target)
    tail_candidate = cleaned[-tail_target:]
    search_tail_end = int(tail_target * 0.25)
    p_idx = tail_candidate.find("\n\n", 0, search_tail_end)
    if p_idx != -1:
        tail_cut = p_idx + 2
    else:
        s_candidates = [
            idx for idx in (
                tail_candidate.find(". ", 0, search_tail_end),
                tail_candidate.find(".\n", 0, search_tail_end),
            ) if idx != -1
        ]
        if s_candidates:
            tail_cut = min(s_candidates) + 2
        else:
            w_idx = tail_candidate.find(" ", 0, search_tail_end)
            tail_cut = w_idx + 1 if w_idx != -1 else 0

    tail_part = tail_candidate[tail_cut:].lstrip()

    return f"{head_part}{marker}{tail_part}"


# ---------------------------------------------------------------------------
# Prompt Construction & Schema Formatting
# ---------------------------------------------------------------------------

def _get_schema_instructions(record_type: str) -> str:
    """Return schema specification and field rules for a given record type."""
    norm_type = record_type.upper().strip()

    schemas = {
        "STARTUP": (
            '{\n'
            '  "entityName": "string (name of startup or company)",\n'
            '  "employeeCount": "integer or null (total number of employees, null if unknown)"\n'
            '}'
        ),
        "PRODUCT": (
            '{\n'
            '  "startupName": "string (name of company offering the product)",\n'
            '  "pricingModel": "string (strictly one of: \'FREE\', \'FREEMIUM\', \'PAID\', \'ENTERPRISE\', or null)"\n'
            '}'
        ),
        "RESEARCH_PAPER": (
            '{\n'
            '  "title": "string (paper title)",\n'
            '  "authors": ["list of author name strings"],\n'
            '  "paper_url": "string or null (URL of paper if stated, else null)",\n'
            '  "github_url": "string or null (official repository link ONLY if explicitly stated)",\n'
            '  "github_stars": "integer or null (star count ONLY if explicitly stated)",\n'
            '  "published_date": "string or null (ISO-8601 date, e.g. \'YYYY-MM-DD\')"\n'
            '}'
        ),
        "JOB": (
            '{\n'
            '  "company": "string (hiring company name)",\n'
            '  "date": "string or null (posting or recorded date, ISO-8601 format)",\n'
            '  "is_remote": "boolean (true if remote/work-from-home, false otherwise)",\n'
            '  "role_family": "string (job function or domain, e.g. \'Engineering\', \'Research\')"\n'
            '}'
        ),
        "NEWS": (
            '{\n'
            '  "title": "string (news headline or article title)",\n'
            '  "text": "string (summary or main body of the article)",\n'
            '  "published_date": "string or null (ISO-8601 date, e.g. \'YYYY-MM-DD\')"\n'
            '}'
        ),
    }

    return schemas.get(
        norm_type,
        '{\n  "name": "string or null",\n  "description": "string or null"\n}'
    )


def build_prompts(text: str, record_type: str) -> tuple[str, str]:
    """
    Build system and user prompts enforcing strict anti-hallucination guidelines.
    """
    schema_desc = _get_schema_instructions(record_type)

    system_prompt = (
        "You are an expert, deterministic information extraction system.\n"
        f"Extract structured data from the source text into valid JSON for record type: {record_type}.\n\n"
        "STRICT ANTI-HALLUCINATION RULES:\n"
        "1. Extract ONLY information explicitly stated in and directly supported by the source text.\n"
        "2. DO NOT hallucinate, guess, infer, or fabricate any facts or metadata.\n"
        "3. Never invent company names, entity names, URLs, dates, employee counts, GitHub repositories, or numbers.\n"
        "4. If any field or detail is not explicitly mentioned in the text, set that field to null (or [] for empty lists).\n"
        "5. Source URLs and GitHub links must never be fabricated; only extract them if they appear verbatim in the text.\n"
        "6. Return ONLY a single valid, parseable JSON object. Do not include introductory text, conversational remarks, or markdown prose outside the JSON."
    )

    user_prompt = (
        f"Record Type: {record_type}\n\n"
        f"Expected JSON Schema:\n{schema_desc}\n\n"
        "Source Text:\n"
        "---\n"
        f"{text}\n"
        "---\n\n"
        "Extract the JSON matching the schema above. Return only the JSON object."
    )

    return system_prompt, user_prompt


def parse_json_response(raw_response: str) -> dict:
    """
    Extract and parse a JSON dictionary from an LLM response string.
    Safely handles markdown fences and surrounding commentary.
    """
    if not raw_response:
        raise InvalidResponseError("Received empty response from LLM provider.")

    text = raw_response.strip()

    # Strip markdown code fences if present (```json ... ```)
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if match:
            text = match.group(1).strip()
        else:
            # Try removing leading/trailing fence lines
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

    # Fallback to outermost braces if text has leading/trailing prose
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        text = text[start_brace:end_brace + 1]

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise InvalidResponseError(f"Expected JSON object/dict, got {type(data).__name__}.")
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidResponseError(f"Failed to parse LLM response as JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# LLM Orchestrator Class
# ---------------------------------------------------------------------------

class LLMOrchestrator:
    """
    Multi-provider LLM Orchestrator with cascading fallback.

    Execution Order:
    1. Gemini Flash
    2. Groq Llama
    3. DeepSeek
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ):
        self._gemini_api_key = gemini_api_key
        self._groq_api_key = groq_api_key
        self._deepseek_api_key = deepseek_api_key
        self.max_input_chars = max_input_chars
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.timeout = timeout

    # -----------------------------------------------------------------------
    # Dynamic Key Resolvers (Read at runtime, never hard-coded)
    # -----------------------------------------------------------------------

    def _get_api_key(self, provider: str) -> Optional[str]:
        """Resolve API key from instance configuration or environment variables."""
        if provider == "gemini":
            return self._gemini_api_key or os.getenv("GEMINI_API_KEY")
        elif provider == "groq":
            return self._groq_api_key or os.getenv("GROQ_API_KEY")
        elif provider == "deepseek":
            return self._deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        return None

    # -----------------------------------------------------------------------
    # Low-level HTTP POST Helper
    # -----------------------------------------------------------------------

    def _send_http_post(self, url: str, headers: dict, payload: dict) -> tuple[int, str, dict]:
        """
        Send an HTTP POST request with JSON payload.
        Returns (status_code, response_body_str, response_headers).
        """
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            status_code = resp.status
            resp_headers = dict(resp.headers)
            body = resp.read().decode("utf-8")
            return status_code, body, resp_headers

    # -----------------------------------------------------------------------
    # Isolated Provider Methods
    # -----------------------------------------------------------------------

    def _call_gemini(self, text: str, record_type: str) -> dict:
        """
        Call Gemini Flash via the Google Generative Language REST API.
        """
        api_key = self._get_api_key("gemini")
        if not api_key:
            raise MissingAPIKeyError("GEMINI_API_KEY is not set.")

        primary_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        models_to_try = [primary_model]
        if primary_model != "gemini-3.5-flash" and "1.5" not in primary_model:
            models_to_try.append("gemini-3.5-flash")

        system_prompt, user_prompt = build_prompts(text, record_type)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            }
        }
        headers = {"Content-Type": "application/json"}

        last_exc = None
        for model in models_to_try:
            url = f"{GEMINI_API_ENDPOINT.format(model=model)}?key={api_key}"
            try:
                _, body, _ = self._send_http_post(url, headers, payload)
                resp_data = json.loads(body)
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    raise InvalidResponseError("Gemini returned no candidates.")
                content_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return parse_json_response(content_part)
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429 and len(models_to_try) > 1 and model != models_to_try[-1]:
                    logger.info("Model '%s' quota reached; trying flash fallback '%s'", model, models_to_try[-1])
                    continue
                raise
            except json.JSONDecodeError as exc:
                raise InvalidResponseError(f"Gemini API returned invalid JSON: {exc}") from exc

        if last_exc:
            raise last_exc

    def _call_groq(self, text: str, record_type: str) -> dict:
        """
        Call Groq Llama via the Groq OpenAI-compatible Chat Completions API.
        """
        api_key = self._get_api_key("groq")
        if not api_key:
            raise MissingAPIKeyError("GROQ_API_KEY is not set.")

        model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        url = GROQ_API_ENDPOINT

        system_prompt, user_prompt = build_prompts(text, record_type)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        _, body, _ = self._send_http_post(url, headers, payload)

        try:
            resp_data = json.loads(body)
            choices = resp_data.get("choices", [])
            if not choices:
                raise InvalidResponseError("Groq returned no choices.")
            raw_content = choices[0].get("message", {}).get("content", "")
            return parse_json_response(raw_content)
        except json.JSONDecodeError as exc:
            raise InvalidResponseError(f"Groq API returned invalid JSON: {exc}") from exc

    def _call_deepseek(self, text: str, record_type: str) -> dict:
        """
        Call DeepSeek via the DeepSeek OpenAI-compatible Chat Completions API.
        """
        api_key = self._get_api_key("deepseek")
        if not api_key:
            raise MissingAPIKeyError("DEEPSEEK_API_KEY is not set.")

        model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        url = DEEPSEEK_API_ENDPOINT

        system_prompt, user_prompt = build_prompts(text, record_type)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        _, body, _ = self._send_http_post(url, headers, payload)

        try:
            resp_data = json.loads(body)
            choices = resp_data.get("choices", [])
            if not choices:
                raise InvalidResponseError("DeepSeek returned no choices.")
            raw_content = choices[0].get("message", {}).get("content", "")
            return parse_json_response(raw_content)
        except json.JSONDecodeError as exc:
            raise InvalidResponseError(f"DeepSeek API returned invalid JSON: {exc}") from exc

    # -----------------------------------------------------------------------
    # Provider Execution Loop with 429 Backoff & 413 Chunking
    # -----------------------------------------------------------------------

    def _execute_provider_with_retry(
        self,
        provider_name: str,
        provider_fn: Callable[[str, str], dict],
        text: str,
        record_type: str,
    ) -> Optional[dict]:
        """
        Execute a single provider call with retry handling:
        - 429: Exponential backoff with random jitter and Retry-After support
        - 413: Shrink input payload size and retry
        - Timeout/Network: Exponential backoff and retry
        - Invalid JSON / Malformed Output: Immediate fallback
        - Missing API Key: Immediate skip/fallback
        """
        current_text = text
        current_max_chars = self.max_input_chars

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "Attempting extraction with provider '%s' (record_type='%s', attempt %d/%d)...",
                    provider_name, record_type, attempt + 1, self.max_retries
                )
                result = provider_fn(current_text, record_type)
                logger.info("Provider '%s' succeeded for record_type='%s'.", provider_name, record_type)
                return result

            except MissingAPIKeyError:
                logger.info("Provider '%s' skipped: API key is not configured.", provider_name)
                return None

            except urllib.error.HTTPError as exc:
                # HTTP 429: Rate Limit
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    wait_seconds: Optional[float] = None
                    if retry_after:
                        try:
                            wait_seconds = float(retry_after)
                        except ValueError:
                            pass
                    if wait_seconds is None:
                        try:
                            err_body = exc.read().decode("utf-8")
                            delay_match = re.search(r'retry in ([0-9.]+)s', err_body, re.IGNORECASE)
                            if delay_match:
                                wait_seconds = float(delay_match.group(1)) + 1.0
                            else:
                                details_match = re.search(r'"retryDelay":\s*"([0-9.]+)s"', err_body)
                                if details_match:
                                    wait_seconds = float(details_match.group(1)) + 1.0
                        except Exception:
                            pass
                    if wait_seconds is None:
                        jitter = random.uniform(0.1, 0.5)
                        wait_seconds = (self.initial_backoff * (2 ** attempt)) + jitter

                    wait_seconds = min(wait_seconds, 60.0)
                    logger.warning(
                        "Provider '%s' returned HTTP 429 (Rate Limit). Retrying in %.2fs (attempt %d/%d)...",
                        provider_name, wait_seconds, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_seconds)
                    continue

                # HTTP 413: Payload Too Large
                elif exc.code == 413:
                    current_max_chars = max(1000, int(current_max_chars * 0.6))
                    current_text = chunk_or_truncate_text(current_text, max_chars=current_max_chars)
                    logger.warning(
                        "Provider '%s' returned HTTP 413 (Payload Too Large). Reduced input to %d chars. Retrying (attempt %d/%d)...",
                        provider_name, len(current_text), attempt + 1, self.max_retries
                    )
                    time.sleep(0.5)
                    continue

                else:
                    logger.warning(
                        "Provider '%s' failed with HTTP %d: %s. Falling back to next provider.",
                        provider_name, exc.code, exc.reason
                    )
                    return None

            except (urllib.error.URLError, TimeoutError) as exc:
                jitter = random.uniform(0.1, 0.5)
                wait_seconds = (self.initial_backoff * (2 ** attempt)) + jitter
                logger.warning(
                    "Provider '%s' network/timeout error: %s. Retrying in %.2fs (attempt %d/%d)...",
                    provider_name, exc, wait_seconds, attempt + 1, self.max_retries
                )
                time.sleep(wait_seconds)
                continue

            except InvalidResponseError as exc:
                logger.warning(
                    "Provider '%s' returned invalid JSON: %s. Falling back to next provider.",
                    provider_name, exc
                )
                return None

            except Exception as exc:
                logger.warning(
                    "Provider '%s' encountered unexpected error: %s. Falling back to next provider.",
                    provider_name, exc
                )
                return None

        logger.warning(
            "Provider '%s' exhausted all %d retries. Falling back to next provider.",
            provider_name, self.max_retries
        )
        return None

    # -----------------------------------------------------------------------
    # Main Extraction Interface
    # -----------------------------------------------------------------------

    def extract(self, text: str, record_type: str) -> dict:
        """
        Extract structured data for a record_type from raw or cleaned text.

        Tries providers in strict priority order:
        1. Gemini Flash
        2. Groq Llama
        3. DeepSeek

        Returns:
            Structured dict containing extraction result:
            {
                "success": True/False,
                "provider": "gemini" | "groq" | "deepseek" | None,
                "record_type": record_type,
                "data": parsed_dict | None,
                "error": None | error_message,
            }
        """
        if not text or not text.strip():
            return {
                "success": False,
                "provider": None,
                "record_type": record_type,
                "data": None,
                "error": "Input text is empty.",
            }

        # Prepare and bound text within configurable character limits
        prepared_text = chunk_or_truncate_text(text, max_chars=self.max_input_chars)

        providers: list[tuple[str, Callable[[str, str], dict]]] = [
            ("gemini", self._call_gemini),
            ("groq", self._call_groq),
            ("deepseek", self._call_deepseek),
        ]

        for provider_name, provider_fn in providers:
            result = self._execute_provider_with_retry(
                provider_name=provider_name,
                provider_fn=provider_fn,
                text=prepared_text,
                record_type=record_type,
            )

            if result is not None:
                return {
                    "success": True,
                    "provider": provider_name,
                    "record_type": record_type,
                    "data": result,
                    "error": None,
                }

            logger.info("Fallback occurred: switching from '%s' to next provider in chain.", provider_name)

        logger.error("All LLM providers failed or were unconfigured for record_type='%s'.", record_type)
        return {
            "success": False,
            "provider": None,
            "record_type": record_type,
            "data": None,
            "error": "All LLM providers failed or were unconfigured.",
        }


# Default module-level instance for convenience
orchestrator = LLMOrchestrator()

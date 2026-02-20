from __future__ import annotations

import json
import os
from typing import Any

import oci


class AgentConfigError(Exception):
    pass


class AgentRuntimeError(Exception):
    pass


def _log_agent_response(tag: str, payload: str) -> None:
    if os.getenv("DEBUG_AGENT_RESPONSE", "").lower() not in {"1", "true", "yes", "on"}:
        return
    max_chars = int(os.getenv("DEBUG_AGENT_RESPONSE_MAX_CHARS", "4000"))
    trimmed = payload[:max_chars]
    print(f"[agent-debug:{tag}] {trimmed}")


def _build_inference_client() -> tuple[oci.generative_ai_inference.GenerativeAiInferenceClient, str, str]:
    model_id = os.getenv("OCI_MODEL_ID")
    if not model_id:
        raise AgentConfigError("OCI_MODEL_ID is not configured.")
    compartment_id = os.getenv("OCI_COMPARTMENT_ID")
    if not compartment_id:
        raise AgentConfigError("OCI_COMPARTMENT_ID is not configured.")
    config_file = os.getenv("OCI_CONFIG_FILE")
    config_profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
    try:
        config = oci.config.from_file(file_location=config_file, profile_name=config_profile)
    except Exception as exc:
        raise AgentConfigError("Unable to load OCI config for the inference runtime.") from exc

    region = os.getenv("OCI_INFERENCE_REGION") or config.get("region")
    if region:
        config["region"] = region
    explicit_endpoint = os.getenv("OCI_INFERENCE_ENDPOINT")
    client_kwargs: dict[str, Any] = {}
    if explicit_endpoint:
        client_kwargs["service_endpoint"] = explicit_endpoint
    client = oci.generative_ai_inference.GenerativeAiInferenceClient(config, **client_kwargs)
    return client, model_id, compartment_id


def _extract_response_text_from_inference(result: Any) -> str:
    chat_response = getattr(result, "chat_response", None)
    if chat_response is None:
        return str(result)

    # Cohere format commonly returns .text
    text = getattr(chat_response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    # Generic format returns choices[].message.content[].text
    choices = getattr(chat_response, "choices", None)
    if isinstance(choices, list):
        chunks: list[str] = []
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None) if message is not None else None
            if isinstance(content, list):
                for item in content:
                    item_text = getattr(item, "text", None)
                    if isinstance(item_text, str) and item_text.strip():
                        chunks.append(item_text.strip())
        if chunks:
            return "\n".join(chunks)

    return str(chat_response)


def _chat_inference(prompt: str) -> str:
    client, model_id, compartment_id = _build_inference_client()
    request = oci.generative_ai_inference.models.CohereChatRequest(
        message=prompt,
        max_tokens=1200,
        temperature=0.2,
        top_p=0.75,
        top_k=0,
        is_stream=False,
    )
    details = oci.generative_ai_inference.models.ChatDetails(
        compartment_id=compartment_id,
        serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(model_id=model_id),
        chat_request=request,
    )
    response = client.chat(details)
    return _extract_response_text_from_inference(response.data)


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    # 1) Direct JSON payload
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2) Fenced or mixed text payload
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(stripped[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3) If the model returned a JSON string inside a wrapper
    for quote_wrapped in (stripped.strip('"'), stripped.strip("'")):
        if "{" in quote_wrapped and "}" in quote_wrapped:
            s = quote_wrapped.find("{")
            e = quote_wrapped.rfind("}")
            try:
                parsed = json.loads(quote_wrapped[s : e + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    raise AgentRuntimeError("Agent response did not contain parseable JSON.")


def generate_initial_feedback(student_text: str, instructor_text: str) -> dict[str, Any]:
    prompt = f"""
Compare a student's solution against an instructor solution.
The student solution may be step-by-step OR a final/concise answer only.

Return JSON only with this exact shape:
{{
  "comparison_feedback": {{
    "problemTitle": "string",
    "problemPrompt": "string",
    "personalizedSummary": "string",
    "score": number,
    "totalPoints": number,
    "steps": [
      {{
        "studentStep": "string",
        "status": "correct" or "incorrect",
        "whatWentWrong": "string",
        "howToFix": "string"
      }}
    ]
  }}
}}

Rules:
- Always return at least 1 item in steps.
- If no explicit steps are present in student text, create one high-level step summary and compare overall reasoning/outcome.
- Do not claim extraction failed unless text is truly empty.

Student solution text:
{student_text[:18000]}

Instructor solution text:
{instructor_text[:18000]}
""".strip()
    try:
        raw = _chat_inference(prompt)
        _log_agent_response("initial", raw)
        return _extract_json(raw)
    except AgentRuntimeError:
        raise
    except Exception as exc:
        raise AgentRuntimeError(f"Failed generating initial comparison feedback: {exc}") from exc


def generate_next_problem(student_text: str, instructor_text: str, comparison_summary: str = "") -> dict[str, Any]:
    prompt = f"""
Generate one next practice problem based on where the student went wrong compared to the instructor solution.

Return JSON only with this exact shape:
{{
  "next_problem": {{
    "question": "string",
    "solution": "string",
    "common_pitfall": "string"
  }}
}}

Rules:
- Keep difficulty similar to the original problem.
- Focus on the student's most likely misconception.
- Return valid JSON only.

Optional comparison summary:
{comparison_summary[:2000]}

Student solution text:
{student_text[:18000]}

Instructor solution text:
{instructor_text[:18000]}
""".strip()
    try:
        raw = _chat_inference(prompt)
        _log_agent_response("next_problem", raw)
        return _extract_json(raw)
    except AgentRuntimeError:
        raise
    except Exception as exc:
        raise AgentRuntimeError(f"Failed generating next problem: {exc}") from exc


def generate_practice_feedback(
    student_attempt_text: str,
    question: str,
    solution: str,
    common_pitfall: str,
) -> dict[str, Any]:
    prompt = f"""
Evaluate a student's attempt at a practice problem.
The attempt may be step-by-step OR a concise final answer.

Return JSON only with this exact shape:
{{
  "feedback": {{
    "problemTitle": "string",
    "problemPrompt": "string",
    "personalizedSummary": "string",
    "score": number,
    "totalPoints": number,
    "steps": [
      {{
        "studentStep": "string",
        "status": "correct" or "incorrect",
        "whatWentWrong": "string",
        "howToFix": "string"
      }}
    ]
  }},
  "next_problem": {{
    "question": "string",
    "solution": "string",
    "common_pitfall": "string"
  }}
}}

Rules:
- Always return at least 1 item in steps.
- If no explicit intermediate steps are shown, create one high-level step summary and evaluate the overall attempt.
- Focus comparison against the provided reference solution.

Practice question:
{question}

Reference solution:
{solution}

Known common pitfall:
{common_pitfall}

Student attempt text:
{student_attempt_text[:18000]}
""".strip()
    try:
        raw = _chat_inference(prompt)
        _log_agent_response("practice", raw)
        return _extract_json(raw)
    except AgentRuntimeError:
        raise
    except Exception as exc:
        raise AgentRuntimeError(f"Failed generating practice feedback: {exc}") from exc

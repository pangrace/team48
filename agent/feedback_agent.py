from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import oci


class AgentConfigError(Exception):
    pass


class AgentRuntimeError(Exception):
    pass


@dataclass
class AgentRuntime:
    endpoint_id: str
    client: oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient
    session_id: str | None = None

    def ensure_session(self) -> str:
        if self.session_id:
            return self.session_id
        session = self.client.create_session(
            agent_endpoint_id=self.endpoint_id,
            create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
                display_name="team48-feedback-session"
            ),
        ).data
        self.session_id = session.id
        return self.session_id

    def chat(self, message: str) -> str:
        response = self.client.chat(
            agent_endpoint_id=self.endpoint_id,
            chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                user_message=message,
                session_id=self.ensure_session(),
                should_stream=False,
            ),
        ).data
        for attr in ("message", "text", "content"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(response).strip()


def _build_runtime() -> AgentRuntime:
    endpoint_id = os.getenv("OCI_AGENT_ENDPOINT_ID")
    if not endpoint_id:
        raise AgentConfigError("OCI_AGENT_ENDPOINT_ID is not configured.")

    config_file = os.getenv("OCI_CONFIG_FILE")
    config_profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
    try:
        config = oci.config.from_file(file_location=config_file, profile_name=config_profile)
    except Exception as exc:
        raise AgentConfigError("Unable to load OCI config for the agent runtime.") from exc

    return AgentRuntime(
        endpoint_id=endpoint_id,
        client=oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(config),
    )


def _extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AgentRuntimeError("Agent response did not contain JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AgentRuntimeError("Agent returned invalid JSON.") from exc


def generate_initial_feedback(student_text: str, instructor_text: str) -> dict[str, Any]:
    runtime = _build_runtime()
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
  }},
  "next_problem": {{
    "question": "string",
    "solution": "string",
    "common_pitfall": "string"
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
        return _extract_json(runtime.chat(prompt))
    except Exception as exc:
        raise AgentRuntimeError("Failed generating initial comparison feedback.") from exc


def generate_practice_feedback(
    student_attempt_text: str,
    question: str,
    solution: str,
    common_pitfall: str,
) -> dict[str, Any]:
    runtime = _build_runtime()
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
        return _extract_json(runtime.chat(prompt))
    except Exception as exc:
        raise AgentRuntimeError("Failed generating practice feedback.") from exc

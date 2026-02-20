import json
import os
from dataclasses import dataclass
from typing import Any

import oci

SYSTEM_PROMPT = """
You are an assistant that analyzes a student's math work and returns feedback JSON only.
Return a JSON object with this exact shape:
{
  "problemTitle": "string",
  "problemPrompt": "string",
  "personalizedSummary": "string",
  "score": number,
  "totalPoints": number,
  "steps": [
    {
      "studentStep": "string",
      "status": "correct" | "incorrect",
      "whatWentWrong": "string",
      "howToFix": "string"
    }
  ]
}
Rules:
- If details are unclear from the PDF text, make reasonable assumptions and state that briefly in the summary.
- Include 3 to 6 steps when possible.
- Do not include markdown fences.
- Output valid JSON only.
""".strip()


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
                display_name="team48-math-feedback"
            ),
        ).data
        self.session_id = session.id
        return self.session_id

    def chat(self, message: str) -> Any:
        session_id = self.ensure_session()
        return self.client.chat(
            agent_endpoint_id=self.endpoint_id,
            chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                user_message=message,
                session_id=session_id,
                should_stream=False,
            ),
        ).data


def _extract_json_candidate(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AgentRuntimeError("Agent response did not contain JSON.")
    return raw[start : end + 1]


def _extract_response_text(response_obj: Any) -> str:
    for attr in ("message", "text", "content"):
        value = getattr(response_obj, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Fallback: stringify unknown SDK response shape.
    return str(response_obj).strip()


def _build_agent_runtime() -> AgentRuntime:
    endpoint_id = os.getenv("OCI_AGENT_ENDPOINT_ID")
    if not endpoint_id:
        raise AgentConfigError("OCI_AGENT_ENDPOINT_ID is not configured.")

    config_file = os.getenv("OCI_CONFIG_FILE")
    config_profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")

    try:
        config = oci.config.from_file(file_location=config_file, profile_name=config_profile)
    except Exception as exc:
        raise AgentConfigError("Unable to load OCI config for the agent runtime.") from exc

    client = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(config)
    return AgentRuntime(endpoint_id=endpoint_id, client=client)


def analyze_math_pdf_text_with_agent(pdf_text: str, filename: str) -> dict[str, Any]:
    runtime = _build_agent_runtime()

    user_prompt = (
        f"Filename: {filename}\\n\\n"
        f"{SYSTEM_PROMPT}\\n\\n"
        "Analyze the student's math work from this extracted PDF text:\\n\\n"
        f"{pdf_text[:18000]}"
    )

    try:
        raw_response = runtime.chat(user_prompt)
    except Exception as exc:
        raise AgentRuntimeError("Failed to call OCI agent runtime.") from exc

    response_text = _extract_response_text(raw_response)
    json_candidate = _extract_json_candidate(response_text)

    try:
        return json.loads(json_candidate)
    except json.JSONDecodeError as exc:
        raise AgentRuntimeError("OCI agent did not return valid JSON feedback.") from exc

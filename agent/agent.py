from __future__ import annotations

import argparse
import os
from typing import Optional

import oci


DEFAULT_AGENT_ENDPOINT_ID = (
    "ocid1.genaiagentendpoint.oc1.us-chicago-1.amaaaaaa5w6bxjiaj74lqxwuewcl2ebnowbbvcra7ntboksrsiszevt74kmq"
)


def _read_text_from_response(response: object) -> str:
    # OCI chat response field names can vary by SDK model; check common candidates.
    for attr in ("answer", "text", "message", "content"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(response)


def send_text_to_agent(
    user_message: str,
    *,
    agent_endpoint_id: Optional[str] = None,
    profile: str = "DEFAULT",
) -> str:
    endpoint_id = agent_endpoint_id or os.getenv("OCI_AGENT_ENDPOINT_ID") or DEFAULT_AGENT_ENDPOINT_ID
    config = oci.config.from_file(profile_name=profile)
    runtime = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(config)

    session = runtime.create_session(
        agent_endpoint_id=endpoint_id,
        create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
            display_name="team48-pdf-session",
            description="Session created from backend PDF analysis request",
        ),
    ).data

    response = runtime.chat(
        agent_endpoint_id=endpoint_id,
        chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
            user_message=user_message,
            session_id=session.id,
            should_stream=False,
        ),
    ).data

    return _read_text_from_response(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send text to OCI Agent endpoint.")
    parser.add_argument("message", help="Message text to send to the agent")
    parser.add_argument("--endpoint-id", dest="endpoint_id", help="Override OCI Agent endpoint id")
    parser.add_argument("--profile", default="DEFAULT", help="OCI config profile name")
    args = parser.parse_args()

    print(
        send_text_to_agent(
            args.message,
            agent_endpoint_id=args.endpoint_id,
            profile=args.profile,
        )
    )


if __name__ == "__main__":
    main()

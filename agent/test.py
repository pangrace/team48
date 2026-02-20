from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict

import oci
from langgraph.graph import StateGraph, START, END

import json
from typing import Any, Dict

# ----------------------------
# 1) OCI Agent Runtime wrapper
# ----------------------------

@dataclass
class OCIAgentLLM:
    """Tiny wrapper that uses OCI Generative AI Agents Runtime as the model."""
    agent_endpoint_id: str
    runtime_client: oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient
    session_id: Optional[str] = None

    def ensure_session(self) -> str:
        if self.session_id:
            return self.session_id

        session = self.runtime_client.create_session(
            agent_endpoint_id=self.agent_endpoint_id,
            create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
                display_name="langgraph-session"
            ),
        ).data
        self.session_id = session.id
        return self.session_id

    def chat(self, user_message: str) -> str:
        sid = self.ensure_session()

        resp = self.runtime_client.chat(
            agent_endpoint_id=self.agent_endpoint_id,
            chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                user_message=user_message,
                session_id=sid,
                should_stream=False,
            ),
        ).data

        # resp can be a structured object; stringify for now
        return str(resp)

# ----------------------------
# 3) Agentic flow (ReAct-ish)
# ----------------------------

class AgentState(TypedDict):
    student_solutions: List[str]
    instructor_solutions: List[str]
    current_problem_on: 0
    problem_threshold: 3
    next_question: None
    next_solution: None

def parse_student_solutions(state: AgentState, llm: OCIAgentLLM) -> AgentState:
    state.student_solutions.append("2+3 = 9")

def parse_solutions(state: AgentState, llm: OCIAgentLLM) -> AgentState:
    state.instructor_solutions.append("2+3 = 5")


def verify_solution(state: AgentState, llm: OCIAgentLLM) -> AgentState:
    prompt = f"""
    You are grading a student's solution.

    Instructor Solution:
    {state.instructor_solutions[0]}

    Student Solution:
    {state.student_solutions[0]}

    Respond with EXACTLY one word:
    CORRECT
    or
    INCORRECT
    """.strip()
    model_out = llm.chat(prompt).strip().upper()

    if "CORRECT" in model_out:
        return "correct"
    else:
        return "incorrect"


def should_continue(state: AgentState) -> str:
    if state.current_problem_on > state.problem_threshold:
        return "END"
    return "CONTINUE"

def generate_example(state: AgentState, llm: OCIAgentLLM) -> AgentState:
    prompt = f"""
You are a tutor.

Instructor Solution (reference):
{state.instructor_solutions[0]}

Student Incorrect Solution:
{state.student_solutions[0]}

Create ONE practice problem that targets the student's exact mistake.

Return JSON ONLY (no markdown, no backticks) in this exact format:
{{
  "question": "…",
  "solution": "…",
  "common_pitfall": "…"
}}
""".strip()

    raw = llm.chat(prompt).strip()

    # Parse JSON robustly
    try:
        item: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: store raw output so you don't lose the generation
        item = {
            "question": "(parse_error) Could not parse model JSON.",
            "solution": raw,
            "common_pitfall": "Model did not return valid JSON."
        }
    state.next_question = item.get("question", "")
    state.next_solution = item.get("solution", "")

    return state

def generate_explanation(state: AgentState, llm: OCIAgentLLM) -> AgentState:
    f"""
    Generate an explanation for why this is wrong {state.student_solutions[0]}, where this is the solution: {state.instructor_solutions[0]}
    """
    # check if correct
    return state


def build_graph(llm: OCIAgentLLM):
    g = StateGraph(AgentState)

    # Nodes
    # parse student solution
    g.add_node("parse_student_solutions")
    # generate explanation
    g.add_node("generate_explanation")
    # generate example questions
    g.add_node("generate_example")
    # check if continue (instructor threshold met)
    g.add_node("should_continue")

    # Edges
    g.add_edge(START, "parse_student_solutions")
    g.add_edge("generate_explanation", "generate_example")
    g.add_conditional_edges("parse_student_solutions", verify_solution, {"incorrect": "generate_explanation", "correct": END})
    g.add_conditional_edges("generate_example", should_continue, {"CONTINUE": "parse_student_solution", "END": END})
    return g.compile()


# ----------------------------
# 4) Wire up OCI + run
# ----------------------------

def main():
    AGENT_ENDPOINT_ID = "ocid1.genaiagentendpoint.oc1.us-chicago-1.amaaaaaa5w6bxjiaj74lqxwuewcl2ebnowbbvcra7ntboksrsiszevt74kmq"

    config = oci.config.from_file()
    runtime = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(
        config,
        # If needed, force region endpoint:
        # service_endpoint="https://agent-runtime.generativeai.us-chicago-1.oci.oraclecloud.com",
    )

    llm = OCIAgentLLM(agent_endpoint_id=AGENT_ENDPOINT_ID, runtime_client=runtime)
    app = build_graph(llm)

    state: AgentState = {
        "user_input": "Compute (12 + 8) * 3 using tools.",
        "scratchpad": [],
        "tool_name": None,
        "tool_args": None,
        "tool_result": None,
        "final": None,
    }

    out = app.invoke(state)
    print("\nFINAL:\n", out["final"])

if __name__ == "__main__":
    main()
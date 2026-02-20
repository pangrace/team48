import oci

AGENT_ENDPOINT_ID = "ocid1.genaiagentendpoint.oc1.us-chicago-1.amaaaaaa5w6bxjiaj74lqxwuewcl2ebnowbbvcra7ntboksrsiszevt74kmq"

# Loads ~/.oci/config (DEFAULT profile)
config = oci.config.from_file()

# Optional: override endpoint explicitly (otherwise derived from config["region"])
# config["region"] = "us-ashburn-1"
runtime = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(
    config,
    # service_endpoint="https://agent-runtime.generativeai.us-ashburn-1.oci.oraclecloud.com",
)

# 1) Create a chat session (recommended so the agent keeps context)
session = runtime.create_session(
    agent_endpoint_id=AGENT_ENDPOINT_ID,
    create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
        display_name="langgraph-session",
        description="Session created from a python script",
    ),
).data

session_id = session.id

# 2) Chat
resp = runtime.chat(
    agent_endpoint_id=AGENT_ENDPOINT_ID,
    chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
        user_message="What can you do with my knowledge base?",
        session_id=session_id,
        should_stream=False,
    ),
).data

print(resp)

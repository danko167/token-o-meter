"""Scenario family -> LangGraph module mapping.

Shared by AgentRunner (Level 4) and HumanCheckpointRunner (Level 5), which
both build one compiled graph per family from the corresponding module's
`AgentState`, `AgentNodes`, `initial_state`, and `route_after_plan`.
"""

import app.runners.agent_graph as agent_graph
import app.runners.diff_agent_graph as diff_agent_graph
import app.runners.hiring_agent_graph as hiring_agent_graph
import app.runners.incident_agent_graph as incident_agent_graph
import app.runners.policy_agent_graph as policy_agent_graph

FAMILY_MODULES = {
    "customer_support": agent_graph,
    "policy_qa": policy_agent_graph,
    "git_diff_review": diff_agent_graph,
    "incident_triage": incident_agent_graph,
    "hiring_screening": hiring_agent_graph,
}

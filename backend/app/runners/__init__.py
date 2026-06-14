from app.runners.agent_runner import AgentRunner
from app.runners.base import RunnerRegistry
from app.runners.human_checkpoint_runner import HumanCheckpointRunner
from app.runners.llm_runner import LLMRunner
from app.runners.rule_runner import RuleRunner
from app.runners.tool_runner import ToolRunner
from app.runners.workflow_runner import WorkflowRunner


def build_registry() -> RunnerRegistry:
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    registry.register(LLMRunner())
    registry.register(ToolRunner())
    registry.register(AgentRunner())
    registry.register(HumanCheckpointRunner())
    return registry

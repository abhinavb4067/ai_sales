"""Service layer for agent management — kept out of views/serializers per
the architecture's "views stay thin" rule."""
from apps.agents.models import Agent, AgentTool

# Default tool set enabled per goal at creation time. Business owners can
# change this afterwards via the AgentTool endpoints — this is only a
# sensible starting point, not a hard-coded behavior branch elsewhere.
_DEFAULT_TOOLS_BY_GOAL = {
    Agent.Goal.SALES: [AgentTool.ToolName.CREATE_LEAD, AgentTool.ToolName.UPDATE_LEAD, AgentTool.ToolName.HUMAN_HANDOFF],
    Agent.Goal.CUSTOMER_SUPPORT: [AgentTool.ToolName.CREATE_TICKET, AgentTool.ToolName.HUMAN_HANDOFF],
    Agent.Goal.SALES_AND_SUPPORT: [
        AgentTool.ToolName.CREATE_LEAD,
        AgentTool.ToolName.UPDATE_LEAD,
        AgentTool.ToolName.CREATE_TICKET,
        AgentTool.ToolName.HUMAN_HANDOFF,
    ],
    Agent.Goal.LEAD_GENERATION: [AgentTool.ToolName.CREATE_LEAD, AgentTool.ToolName.UPDATE_LEAD],
    Agent.Goal.INFORMATION: [AgentTool.ToolName.HUMAN_HANDOFF],
}


def provision_default_tools(agent: Agent) -> None:
    tool_names = _DEFAULT_TOOLS_BY_GOAL.get(agent.primary_goal, [AgentTool.ToolName.HUMAN_HANDOFF])
    AgentTool.objects.bulk_create(
        [
            AgentTool(business=agent.business, agent=agent, tool_name=name, enabled=True)
            for name in tool_names
        ],
        ignore_conflicts=True,
    )

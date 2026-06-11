from agents.system_agent import system_agent
from agents.file.file_agent import file_agent
from agents.veronica.veronica_agent import veronica_agent
from agents.vision.vision_agent import vision_agent
from agents.ultron.ultron_agent import ultron_agent
from agents.edith.edith_agent import edith_agent
from agents.echo.echo_agent import echo_agent
from agents.athena.athena_agent import athena_agent
from agents.personal.personal_agent import personal_agent
from agents.friday.friday_agent import friday_agent
from agents.self_improvement.self_improvement_agent import self_improvement_agent
from agents.terminator.terminator_agent import terminator_agent
from agents.automation.n8n_agent import n8n_agent
from core.scheduler import scheduler


TOOLS = {
    "system": system_agent,
    "file": file_agent,
    "veronica": veronica_agent,
    "vision": vision_agent,
    "ultron": ultron_agent,
    "edith": edith_agent,
    "echo": echo_agent,
    "athena": athena_agent,
    "personal": personal_agent,
    "friday": friday_agent,
    "scheduler": scheduler,
    "self_improvement": self_improvement_agent,
    "terminator": terminator_agent,
    "n8n": n8n_agent,
}


def register_tool(name: str, agent_obj) -> None:
    """Dynamically register a new tool (used by Echo agent for generated tools)."""
    TOOLS[name] = agent_obj
    print(f"[registry] Registered tool: {name}")


def unregister_tool(name: str) -> None:
    """Remove a dynamically registered tool."""
    TOOLS.pop(name, None)
    print(f"[registry] Unregistered tool: {name}")


def execute_tool(
    tool_name: str,
    input_text: str,
    action: str = None,
    parameters: dict = None
):
    """
    Standardized tool execution layer.

    All tools must support:
    run(input_text, action, parameters)

    Returns:
    {
        "success": bool,
        "message": str,
        "data": dict
    }
    """

    tool = TOOLS.get(tool_name)

    if not tool:
        return {
            "success": False,
            "message": f"Unknown tool: {tool_name}",
            "data": {}
        }

    try:
        result = tool.run(
            input_text=input_text,
            action=action,
            parameters=parameters or {}
        )

        if not isinstance(result, dict):
            return {
                "success": False,
                "message": (
                    f"{tool_name} returned "
                    f"invalid response format."
                ),
                "data": {}
            }

        return result

    except Exception as e:
        return {
            "success": False,
            "message": (
                f"{tool_name} execution failed: "
                f"{str(e)}"
            ),
            "data": {}
        }
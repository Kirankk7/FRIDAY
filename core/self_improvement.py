import os
import json
from core.llm import ask_llm
from core.reflection import load_reflections, get_reflection_stats

DIRECTIVE_FILE = "data/improvement_directive.txt"

_IMPROVE_PROMPT = """You are analyzing the response quality log for FRIDAY, an AI assistant.

Below are the {n} most common issues found in recent responses:
{issues}

Recent average quality score: {score}/10

Generate a short, actionable directive (3-5 sentences) telling FRIDAY exactly what to fix.
Be specific. Focus on the top issues only. Write in second person ("You should...").
Do not use bullet points. Output the directive only, nothing else.
"""


def get_current_directive() -> str:
    """Read saved improvement directive. Returns empty string if none."""
    if not os.path.exists(DIRECTIVE_FILE):
        return ""
    try:
        with open(DIRECTIVE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_directive(text: str):
    os.makedirs("data", exist_ok=True)
    with open(DIRECTIVE_FILE, "w", encoding="utf-8") as f:
        f.write(text.strip())


def self_improve() -> str:
    """Analyze reflections, generate LLM directive, save it. Returns the directive."""
    stats = get_reflection_stats()

    if stats["total"] < 5:
        return f"Not enough data yet, boss. Only {stats['total']} responses logged. Need at least 5."

    top_issues = stats.get("top_issues", [])
    if not top_issues:
        return f"No issues detected in recent responses. Quality score: {stats['recent_avg']}/10."

    issues_text = "\n".join(
        f"- {issue} (occurred {count} times)"
        for issue, count in top_issues
    )

    prompt = _IMPROVE_PROMPT.format(
        n=len(top_issues),
        issues=issues_text,
        score=stats["recent_avg"]
    )

    directive = ask_llm(prompt)
    if not directive or not directive.strip():
        return "LLM failed to generate directive."

    directive = directive.strip()
    _save_directive(directive)

    return f"Self-improvement directive updated.\n\n{directive}"


def get_stats() -> str:
    """Return human-readable stats summary."""
    stats = get_reflection_stats()

    if stats["total"] == 0:
        return "No responses logged yet, boss."

    lines = [
        f"Total responses logged: {stats['total']}",
        f"All-time avg quality score: {stats['avg_score']}/10",
        f"Recent (last 20) avg score: {stats['recent_avg']}/10",
    ]

    if stats["top_issues"]:
        lines.append("\nTop recurring issues:")
        for issue, count in stats["top_issues"]:
            lines.append(f"  {issue}: {count}x")

    directive = get_current_directive()
    if directive:
        lines.append(f"\nActive directive:\n{directive}")
    else:
        lines.append("\nNo active directive yet. Run 'analyze your responses' to generate one.")

    return "\n".join(lines)

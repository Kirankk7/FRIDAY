import requests
import json
from core.tools import TOOLS
from core.safety import is_safe_input, check_tool_permission, requires_confirmation
from core.confirmation import ask_confirmation

OLLAMA_URL = "http://localhost:11434/api/generate"


def call_llm(prompt):
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": "mistral:7b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200
                }
            },
            timeout=30
        )
        return res.json().get("response", "").strip()
    except Exception as e:
        print("[LLM ERROR]:", e)
        return ""


def get_tool_list():
    tool_desc = ""
    for name, meta in TOOLS.items():
        tool_desc += f"- {name}: {meta['description']}\n"
    return tool_desc


def decide_next_step(user_input, context, last_result):
    tool_list = get_tool_list()

    prompt = f"""
You are an autonomous AI agent.

User goal:
{user_input}

Context:
{context}

Last result:
{last_result}

Available tools:
{tool_list}

Rules:
- If enough information is gathered → finish
- If result is empty or weak → try another tool
- Prefer minimal steps
- Use chat for explanation
- Use news_search for real-time info
- Use summarize after search

Return ONLY JSON.

Format:
{{
  "action": "tool_name or finish",
  "input": "text"
}}
"""

    response = call_llm(prompt)

    try:
        return json.loads(response)
    except:
        return {"action": "finish", "input": ""}


def evaluate_result(user_input, result):
    prompt = f"""
You are a strict evaluator.

User asked:
{user_input}

Response:
{result}

Is this:
- useful?
- complete?
- relevant?

Reply ONLY with:
GOOD or BAD
"""

    verdict = call_llm(prompt).strip().upper()
    return "GOOD" in verdict


def improve_result(result):
    prompt = f"""
Improve this response to be clearer, more natural and more helpful:

{result}
"""
    improved = call_llm(prompt)
    return improved if improved else result


def run_agent_loop(user_input, context, max_steps=6):
    # 🔒 GLOBAL INPUT SAFETY
    if not is_safe_input(user_input):
        return "I can’t help with that request."

    history = ""
    last_result = ""
    last_action = ""

    for step in range(max_steps):
        decision = decide_next_step(user_input, context + history, last_result)

        action = decision.get("action", "finish")
        action_input = decision.get("input", "")

        print(f"[LOOP STEP {step+1}]: {action} -> {action_input}")

        # 🛑 FINISH CONDITION
        if action == "finish":
            break

        # 🔒 TOOL PERMISSION CHECK
        permission = check_tool_permission(action)

        if permission == "unknown":
            print("[BLOCKED]: Unknown tool")
            return "That action is not allowed."

        # 🔒 CONFIRMATION (FOR DANGEROUS TOOLS)
        if requires_confirmation(action):
            print("[CONFIRMATION REQUIRED]")
            approved = ask_confirmation(action)

            if not approved:
                print("[DENIED]: User rejected action")
                return "Alright, I won’t proceed with that."

        # ⚙️ EXECUTE TOOL
        if action in TOOLS:
            try:
                result = TOOLS[action]["function"](action_input or user_input)
            except Exception as e:
                print("[TOOL ERROR]:", e)
                result = "Tool execution failed."
        else:
            result = "Unknown action."

        print(f"[RESULT]: {result}")

        # 🔁 SELF-CORRECTION
        if not result or len(result.strip()) < 10:
            print("[RETRY]: Weak result detected")
            result = improve_result(result)

        # 🧠 QUALITY CHECK
        is_good = evaluate_result(user_input, result)

        if not is_good:
            print("[RETRY]: Improving result...")
            result = improve_result(result)

        # 🧠 UPDATE LOOP STATE
        history += f"\nStep {step+1}: {result}"
        last_result = result
        last_action = action

    # ✅ FINAL RESPONSE
    if not last_result:
        return "I couldn’t complete that properly. Try asking again."

    return last_result
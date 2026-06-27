from core.planner import create_plan
from core.executor import execute_plan
import requests

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
                    "num_predict": 120
                }
            },
            timeout=20
        )
        return res.json().get("response", "").strip()
    except:
        return ""


def autonomous_run(user_input, max_steps=3):
    print("[AUTO] Starting autonomous execution...")

    context = ""
    steps_done = 0

    while steps_done < max_steps:
        print(f"[AUTO] Step {steps_done+1}")

        # create plan using current context
        plan_input = f"{user_input}\nContext: {context}"
        plan = create_plan(plan_input)

        print("[AUTO PLAN]:", plan)

        results = execute_plan(plan)

        context += "\n".join(results)

        # [hot] decide if done
        decision_prompt = f"""
User goal: {user_input}

Current progress:
{context}

Should we continue or stop?

Answer ONLY:
- continue
- stop
"""

        decision = call_llm(decision_prompt).lower()

        print("[AUTO DECISION]:", decision)

        if "stop" in decision:
            break

        steps_done += 1

    # [hot] final response
    final_prompt = f"""
User goal: {user_input}

All gathered info:
{context}

Give final answer in a clean way.
"""

    return call_llm(final_prompt)
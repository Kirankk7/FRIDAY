from core.tools_registry import execute_tool
from core.task_manager import task_manager
from core.folder_memory import save_folder_context
from core.state import set_last_agent, set_last_action
from core.tool_memory import remember_result
from core.metrics import record as record_metric

import os
import time


def execute_plan(plan):

    results = []

    for step in plan:

        tool = step.get(
            "tool",
            "chat"
        )

        action = step.get(
            "action",
            ""
        )

        parameters = step.get(
            "parameters",
            {}
        )

        print(
            f"[STEP] "
            f"{tool} → "
            f"{action}"
        )

        try:

            # Track active agent for UI indicator
            if tool not in ("chat", "workflow"):
                set_last_agent(tool)
                set_last_action(action)

            # ==========================
            # REMEMBER THIS — inject last response
            # ==========================
            if (
                tool == "edith"
                and parameters.get("content_from") == "last_response"
            ):
                from core.memory import load_memory
                history = load_memory().get("history", [])
                last_response = next(
                    (h["content"] for h in reversed(history) if h["role"] == "assistant"),
                    None
                )
                if last_response:
                    parameters = dict(parameters)
                    del parameters["content_from"]
                    parameters["content"] = last_response
                else:
                    results.append("Nothing to remember yet, boss.")
                    continue

            # ==========================
            # CHAT RESPONSE
            # ==========================
            if tool == "chat":

                result_text = (
                    parameters.get(
                        "task",
                        "Done."
                    )
                )

                results.append(
                    result_text
                )

                continue

            # ==========================
            # WINDOWS PATH FIX
            # ==========================
            if (
                "path"
                in parameters
            ):

                parameters[
                    "path"
                ] = os.path.expanduser(
                    parameters[
                        "path"
                    ]
                )

            # ==========================
            # EXECUTE TOOL SAFELY
            # ==========================
            _t0 = time.perf_counter()
            try:

                result = (
                    execute_tool(

                        tool_name=tool,

                        input_text="",

                        action=action,

                        parameters=parameters
                    )
                )

            except Exception as tool_error:

                print(f"[exec] tool error: {tool_error}")

                result = {

                    "success":
                    False,

                    "message":
                    (
                        f"I couldn't "
                        f"complete "
                        f"{action}."
                    ),

                    "data":
                    {}
                }

            # Phase 52 #5 — telemetry (per-agent calls/latency/errors)
            try:
                record_metric(
                    tool,
                    (time.perf_counter() - _t0) * 1000.0,
                    bool(result and result.get("success", True)),
                    action,
                )
            except Exception:
                pass

            # ==========================
            # NONE PROTECTION
            # ==========================
            if result is None:

                result = {

                    "success":
                    False,

                    "message":
                    (
                        "Something "
                        "went wrong."
                    ),

                    "data":
                    {}
                }

            result_text = (
                result.get(
                    "message",
                    "Done."
                )
            )

            # ==========================
            # SAVE FOLDER MEMORY
            # ==========================
            if (

                tool == "file"

                and

                action == (
                    "list_files"
                )

                and

                result.get(
                    "success"
                )
            ):

                try:

                    save_folder_context(

                        folder_path=result[
                            "data"
                        ].get(
                            "path",
                            ""
                        ),

                        files=result[
                            "data"
                        ].get(
                            "files",
                            []
                        )
                    )

                    print("[exec] folder memory saved")

                except Exception as memory_error:

                    print(f"[exec] memory error: {memory_error}")

            # ==========================
            # TASK MANAGER SAFE
            # ==========================
            try:

                task_manager.add_step(

                    f"{tool}: "
                    f"{action}",

                    result_text
                )

            except Exception as task_error:

                print(f"[exec] task error: {task_error}")

            results.append(
                result_text
            )

            # Remember tool output for later recall (Phase 51 #6) — real tools only
            if tool not in ("chat", "workflow"):
                try:
                    remember_result(tool, action, result_text)
                except Exception as mem_err:
                    print(f"[exec] tool_memory error: {mem_err}")

            # Throttle only between steps in a multi-step plan.
            # Single-step plans (most commands) skip the wait.
            if len(plan) > 1 and step is not plan[-1]:
                time.sleep(0.3)

        except Exception as e:

            error_text = (
                f"I couldn't "
                f"complete "
                f"{action}."
            )

            print(f"[exec] error: {e}")

            results.append(
                error_text
            )

            # ==========================
            # CONTINUE WORKFLOW
            # ==========================
            continue

    return results
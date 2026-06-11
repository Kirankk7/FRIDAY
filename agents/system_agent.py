import platform
import psutil
from core.runtime_flags import is_browser_enabled, set_browser_enabled


class SystemAgent:
    """
    Standardized System Agent

    Purpose:
    - OS information
    - CPU information
    - RAM information
    - System diagnostics

    All agents must follow:
    run(input_text, action, parameters)

    All agents must return:
    {
        "success": bool,
        "message": str,
        "data": dict
    }
    """

    def get_system_info(self):
        info = {
            "OS": platform.system(),
            "Version": platform.version(),
            "CPU": platform.processor(),
            "Cores": psutil.cpu_count(),
            "RAM": f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB"
        }

        message = "\n".join(
            [f"{key}: {value}" for key, value in info.items()]
        )

        return {
            "success": True,
            "message": message,
            "data": info
        }

    def get_cpu_usage(self):
        cpu_usage = psutil.cpu_percent(interval=1)

        return {
            "success": True,
            "message": f"Current CPU usage is {cpu_usage}%",
            "data": {
                "cpu_usage": cpu_usage
            }
        }

    def get_ram_usage(self):
        ram = psutil.virtual_memory()

        ram_data = {
            "total_gb": round(ram.total / (1024**3), 2),
            "used_gb": round(ram.used / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "usage_percent": ram.percent
        }

        return {
            "success": True,
            "message": (
                f"RAM usage is {ram.percent}% "
                f"({ram_data['used_gb']} GB used "
                f"out of {ram_data['total_gb']} GB)"
            ),
            "data": ram_data
        }

    # =====================================
    # SPEED TEST (Phase 42)
    # =====================================
    def speed_test(self) -> dict:
        """Internet speed test via speedtest-cli. Takes ~10-15 seconds."""
        try:
            import speedtest as _st
            s = _st.Speedtest()
            s.get_best_server()
            download = round(s.download() / 1_000_000, 1)
            upload   = round(s.upload()   / 1_000_000, 1)
            ping     = round(s.results.ping, 1)
            server   = s.results.server.get("name", "unknown")
            return {
                "success": True,
                "message": f"Download {download} Mbps, Upload {upload} Mbps, Ping {ping} ms (server: {server})",
                "data": {"download_mbps": download, "upload_mbps": upload, "ping_ms": ping, "server": server}
            }
        except ImportError:
            return {"success": False, "message": "speedtest-cli not installed. Run: pip install speedtest-cli", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Speed test failed: {e}", "data": {}}

    # =====================================
    # BATTERY STATUS (Phase 42)
    # =====================================
    def battery_status(self) -> dict:
        """Battery level and charging status via psutil."""
        try:
            batt = psutil.sensors_battery()
            if batt is None:
                return {"success": False, "message": "No battery detected. This is a desktop.", "data": {}}
            percent = round(batt.percent, 1)
            plugged = "plugged in" if batt.power_plugged else "on battery"
            secs = batt.secsleft
            if batt.power_plugged and secs == psutil.POWER_TIME_UNLIMITED:
                time_str = "fully charged or charging"
            elif secs in (psutil.POWER_TIME_UNKNOWN, -1):
                time_str = "time remaining unknown"
            else:
                hours = secs // 3600
                mins  = (secs % 3600) // 60
                time_str = f"{hours}h {mins}m remaining" if hours else f"{mins}m remaining"
            return {
                "success": True,
                "message": f"Battery {percent}%, {plugged}. {time_str}.",
                "data": {"percent": percent, "plugged": batt.power_plugged, "secs_left": secs}
            }
        except Exception as e:
            return {"success": False, "message": f"Battery check error: {e}", "data": {}}

    # =====================================
    # RECALL TOOL RESULT (Phase 51 #6)
    # =====================================
    def recall_result(self, keyword: str = "") -> dict:
        """Recall a recent tool result without re-running it."""
        from core.tool_memory import last_result, search_results

        keyword = (keyword or "").strip()
        if keyword:
            matches = search_results(keyword)
            if not matches:
                return {"success": True,
                        "message": f"I don't have a recent '{keyword}' result, boss.", "data": {}}
            r = matches[0]
            return {"success": True,
                    "message": f"Your last {r['tool']} {r['action']} result: {r['message']}",
                    "data": r}

        r = last_result()
        if not r:
            return {"success": True, "message": "No recent tool results yet, boss.", "data": {}}
        return {"success": True,
                "message": f"Last result ({r['tool']} {r['action']}): {r['message']}",
                "data": r}

    def run(
        self,
        input_text: str,
        action: str = None,
        parameters: dict = None
    ) -> dict:
        """
        Standardized agent entrypoint.
        """

        try:
            parameters = parameters or {}

            # Default fallback
            if not action:
                action = "system_info"

            if action == "system_info":
                return self.get_system_info()

            elif action == "cpu_usage":
                return self.get_cpu_usage()

            elif action == "ram_usage":
                return self.get_ram_usage()

            elif action == "browser_enable":
                set_browser_enabled(True)
                return {"success": True, "message": "Browser on. It also auto-starts on any browser command, boss.", "data": {}}

            elif action == "browser_disable":
                set_browser_enabled(False)
                return {"success": True, "message": "Browser turned off. It'll stay off until you say 'enable browser'.", "data": {}}

            elif action == "browser_status":
                state = "enabled" if is_browser_enabled() else "disabled"
                return {"success": True, "message": f"Browser is currently {state}.", "data": {"browser_enabled": is_browser_enabled()}}

            elif action == "speed_test":
                return self.speed_test()

            elif action == "battery_status":
                return self.battery_status()

            elif action == "recall_result":
                return self.recall_result(parameters.get("keyword", ""))

            return {
                "success": False,
                "message": f"Unsupported system action: {action}",
                "data": {}
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"System agent error: {str(e)}",
                "data": {}
            }


system_agent = SystemAgent()
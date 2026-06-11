# ===== LOCAL JARVIS CONFIGURATION =====
# Privacy-first, offline, self-hosted

import os
from dotenv import load_dotenv
load_dotenv()

# OLLAMA LOCAL LLM CONFIG
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Available models (check with: ollama list):
# OLLAMA_MODEL = "gemma:2b"          # Lightweight, fast
# OLLAMA_MODEL = "mistral:7b"        # Balanced (recommended)
# OLLAMA_MODEL = "llama2:7b"         # General purpose
# OLLAMA_MODEL = "deepseek-r1:8b"    # Code & reasoning
# OLLAMA_MODEL = "neural-chat:7b"    # Conversational

# WHISPER STT CONFIG (Phase 17)
WHISPER_MODEL   = "base"    # tiny/base/small/medium — base is good balance on RTX 4060
WHISPER_DEVICE  = "cuda"    # cuda or cpu
WHISPER_DTYPE   = "float16" # float16 (GPU) or int8 (CPU)

# STT BACKEND — Phase 17b
# "whisper" = faster-whisper (default, always works)
# "parakeet" = nvidia/parakeet-tdt-1.1b via NeMo (faster, requires: pip install nemo_toolkit[asr])
STT_BACKEND = "whisper"
PARAKEET_MODEL = "nvidia/parakeet-tdt-0.6b"   # 0.6b = ~2GB VRAM, fast. 1.1b = ~4GB, more accurate

# TTS BACKEND
# "edge" = edge-tts (cloud, Microsoft Azure, requires internet)
# "kokoro" = local Kokoro-82M neural TTS (offline, no internet needed)
TTS_BACKEND = "kokoro"

# BROWSER (Veronica agent — Playwright)
# Auto-on: Playwright launches LAZILY on the first browser command (never at boot),
# so startup stays safe even if Chrome/Playwright misbehaves. No manual "enable browser"
# needed. Worker fails gracefully if Chrome can't launch. Set False only to hard-disable.
BROWSER_ENABLED = True

# VOICE LOOP — Phase 28
VOICE_LOOP_AUTO_START = False   # Set True to start autonomous voice pipeline on boot

# ── Phase 39 — Football-Data.org ──
# Free key: https://www.football-data.org/client/register
# Free tier: 10 req/min | competitions: PL, BL1, SA, PD, FL1, CL, EC + national teams
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")

# ── Phase 30a — NVD NIST API ──
# Free key: https://nvd.nist.gov/developers/request-an-api-key
# Rate limit: 50 req/30s with key, 5 req/30s without
NVD_API_KEY = os.getenv("NVD_API_KEY", "")

# ── Phase 30b — VirusTotal API ──
# Free key: https://virustotal.com/gui/join-us
# Free tier: 4 req/min, 500/day. File/URL/domain reputation.
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")

# NO CLOUD APIS
# - No OpenAI
# - No Gemini
# - No Claude
# - No Groq
# - No Together
# All inference runs locally on this machine

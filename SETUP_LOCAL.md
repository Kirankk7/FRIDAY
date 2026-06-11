# 🟠 JARVIS Local Setup Guide

**Privacy-first AI Assistant - Runs Completely Local**

## Requirements

- **Ollama** (local LLM inference)
- Python 3.10+
- ~2GB RAM
- Internet (for initial setup only)

## Setup

### 1. Install Ollama
Download from: https://ollama.ai

### 2. Start Ollama Server
```bash
ollama serve
```

This runs the local LLM API on `http://localhost:11434`

### 3. Pull a Model
```bash
ollama pull mistral
```

Available models (all run locally):
- `mistral` - Fast, balanced (recommended, ~4GB)
- `gemma` - Lightweight (~2GB)  
- `llama3` - More capable (~7GB)
- `deepseek` - Code-focused (~7GB)
- `qwen` - Good balance (~4GB)
- `neural-chat` - Conversational (~4GB)

### 4. Configure JARVIS
Edit `config.py`:
```python
OLLAMA_MODEL = "mistral"  # Change to your chosen model
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

### 6. Test Local LLM
```bash
python test_local_llm.py
```

Should show:
```
✅ Ollama is running!
✅ Model 'mistral' is available!
✅ Inference works!
```

### 7. Run JARVIS
```bash
python app.py
```

Open: http://localhost:5000

## Architecture

```
┌─ User Input ─────────────────────┐
│                                  │
├─ Flask Web Server (localhost:5000)
│
├─ Core Brain (local)
│  ├─ Emotion Detection
│  ├─ Memory Management
│  ├─ Cognitive Loop
│
├─ LLM Module
│  └─ Ollama HTTP API
│      └─ Local Model (gemma, mistral, etc)
│
└─ Voice Output (Text-to-Speech)
```

## Privacy & Security

✅ **100% Local**
- No cloud APIs
- No telemetry
- No internet required (after setup)
- No API keys for inference
- All data stays on your machine

✅ **Data Stays Local**
- Conversations saved in JSON files
- Vector embeddings local
- Emotion memory local
- User profile local

## Model Selection

| Model | Size | Speed | Quality | Type |
|-------|------|-------|---------|------|
| gemma | 2GB | Fast | Good | General |
| mistral | 4GB | Good | Very Good | General |
| llama3 | 7GB | Slower | Excellent | General |
| deepseek | 7GB | Slower | Excellent | Code |
| qwen | 4GB | Good | Very Good | General |

## Troubleshooting

### "Ollama not running?"
```bash
ollama serve
# In another terminal:
python test_local_llm.py
```

### "Model not found?"
```bash
ollama pull mistral
```

### "Connection timeout?"
- Check Ollama is running on port 11434
- Check firewall isn't blocking localhost

### "Slow responses?"
- Start with smaller model (gemma)
- Reduce chat history length
- Use faster hardware

## Config File Reference

`config.py`:
```python
OLLAMA_HOST = "http://localhost:11434"  # Local Ollama server
OLLAMA_MODEL = "mistral"                 # Active model (change anytime)
```

Change model anytime by editing config.py - no restart needed.

## Future Enhancements

- Multi-model routing (switch models per task)
- Model quantization (smaller, faster models)
- Local embedding models (better semantic search)
- Private voice synthesis (local TTS)
- Offline web search (local crawling)

---

**JARVIS**: Local. Private. Offline. Yours.

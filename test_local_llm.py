#!/usr/bin/env python3
"""
Quick test to verify Ollama is working.
Run this before starting JARVIS.
"""

import requests
from config import OLLAMA_HOST, OLLAMA_MODEL

print("🔍 Testing Local LLM Setup...\n")
print(f"OLLAMA_HOST: {OLLAMA_HOST}")
print(f"OLLAMA_MODEL: {OLLAMA_MODEL}")

try:
    url = f"{OLLAMA_HOST}/api/tags"
    response = requests.get(url, timeout=5)
    
    if response.status_code == 200:
        models = response.json().get("models", [])
        print(f"\n✅ Ollama is running!")
        print(f"📦 Available models: {len(models)}")
        
        for model in models:
            name = model.get("name", "?")
            print(f"   - {name}")
        
        # Check if selected model is available
        available_names = [m.get("name", "") for m in models]
        if any(OLLAMA_MODEL in name for name in available_names):
            print(f"\n✅ Model '{OLLAMA_MODEL}' is available!")
        else:
            print(f"\n⚠️  Model '{OLLAMA_MODEL}' not found.")
            print("   Pull it with: ollama pull mistral")
    else:
        print(f"\n❌ Ollama error: {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ OLLAMA NOT RUNNING!")
    print("   Start it with: ollama serve")
    
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*50)
print("Test quick inference...")

try:
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Say hello briefly.",
        "stream": False
    }
    
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        answer = response.json().get("response", "")
        print(f"\n✅ Inference works!")
        print(f"Response: {answer[:100]}...")
    else:
        print(f"❌ Inference failed: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n✅ Local LLM setup verified!")

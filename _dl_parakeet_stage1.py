"""
Stage 1: Download .nemo file using only requests (no NeMo/Lightning imports).
NeMo's native download crashes because PyTorch Lightning's signal handlers
corrupt socket state on Windows.
"""
import os, requests, hashlib
from pathlib import Path

# Exactly where NeMo expects the file
CACHE_DIR  = Path.home() / ".cache/torch/NeMo/NeMo_2.7.3/parakeet-tdt_ctc-110m"
NGC_URL    = "https://api.ngc.nvidia.com/v2/models/nvidia/nemo/parakeet-tdt_ctc-110m/versions/v1/files/parakeet-tdt_ctc-110m.nemo"
FILENAME   = "parakeet-tdt_ctc-110m.nemo"

# NeMo uses MD5 of URL as subfolder
subfolder  = hashlib.md5(NGC_URL.encode()).hexdigest()
dest_dir   = CACHE_DIR / subfolder
dest_file  = dest_dir / FILENAME

dest_dir.mkdir(parents=True, exist_ok=True)
print(f"Destination: {dest_file}", flush=True)

if dest_file.exists() and dest_file.stat().st_size > 1_000_000:
    print(f"Already downloaded ({dest_file.stat().st_size:,} bytes). Done.", flush=True)
else:
    print(f"Downloading from NGC...", flush=True)
    r = requests.get(NGC_URL, stream=True, allow_redirects=True, timeout=120)
    print(f"Status: {r.status_code}, Content-Type: {r.headers.get('Content-Type')}", flush=True)
    total = int(r.headers.get("Content-Length", 0))
    downloaded = 0
    with open(dest_file, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"  {downloaded:,}/{total:,} bytes ({pct:.1f}%)", flush=True)
    print(f"Done: {dest_file.stat().st_size:,} bytes", flush=True)
print(f"Cache path: {dest_file}")

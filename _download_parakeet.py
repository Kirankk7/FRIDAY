"""Download parakeet-tdt_ctc-110m from NGC (no HuggingFace, no auth needed)."""
import os, sys, faulthandler
faulthandler.enable()
os.environ["NUMBA_DISABLE_JIT"] = "1"

from unittest.mock import MagicMock
_m = MagicMock(); _m.jit = lambda f=None, **kw: (f if f else lambda fn: fn); _m.njit = _m.jit
for k, v in [
    ("numba", _m), ("numba.cuda", MagicMock()), ("numba.core", MagicMock()),
    ("numba.typed", MagicMock()), ("llvmlite", MagicMock()), ("llvmlite.binding", MagicMock())
]:
    sys.modules.setdefault(k, v)

import nemo.collections.asr.models as models
import nemo.collections.asr.data, nemo.collections.asr.losses, nemo.collections.asr.modules
print("NeMo imports OK", flush=True)

ASRModel = models.ASRModel
print("Downloading parakeet-tdt_ctc-110m from NGC (~500MB)...", flush=True)
try:
    model = ASRModel.from_pretrained("parakeet-tdt_ctc-110m")
    print(f"Download + load OK: {type(model)}", flush=True)
    model = model.cuda()
    model.eval()
    print("CUDA OK. Parakeet ready.", flush=True)
except Exception as e:
    import traceback
    print(f"EXCEPTION: {e}", flush=True)
    traceback.print_exc()

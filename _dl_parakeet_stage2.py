"""Stage 2: Load parakeet from locally cached .nemo file."""
import os, sys
os.environ["NUMBA_DISABLE_JIT"] = "1"

from unittest.mock import MagicMock
_m = MagicMock()
_m.__version__ = "0.59.0"   # NeMo checks numba.__version__ — provide fake valid version
_m.jit  = lambda f=None, **kw: (f if f else lambda fn: fn)
_m.njit = _m.jit
for k, v in [("numba", _m), ("numba.cuda", MagicMock()), ("numba.core", MagicMock()),
              ("numba.typed", MagicMock()), ("llvmlite", MagicMock()), ("llvmlite.binding", MagicMock())]:
    sys.modules.setdefault(k, v)

import nemo.collections.asr.models as models
import nemo.collections.asr.data, nemo.collections.asr.losses, nemo.collections.asr.modules
print("NeMo imports OK", flush=True)

LOCAL_NEMO = r"C:\Users\krnkk\.cache\torch\NeMo\NeMo_2.7.3\parakeet-tdt_ctc-110m\c528f28c0fb089db853adccc81b5de93\parakeet-tdt_ctc-110m.nemo"
ModelCls = models.EncDecHybridRNNTCTCBPEModel
print(f"Loading {ModelCls.__name__} from local file...", flush=True)
try:
    model = ModelCls.restore_from(LOCAL_NEMO, map_location="cpu")
    model.eval()
    print(f"LOADED: {type(model)}", flush=True)
    # Quick transcription test on silence
    import numpy as np, soundfile as sf, tempfile
    silence = np.zeros(16000, dtype=np.float32)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, silence, 16000)
        wav = f.name
    result = model.transcribe([wav])
    os.remove(wav)
    print(f"Transcription: {result}", flush=True)
    print("SUCCESS — Parakeet ready.", flush=True)
except Exception as e:
    import traceback
    print(f"EXCEPTION: {e}", flush=True)
    traceback.print_exc()

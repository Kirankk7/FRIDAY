"""
Phase 17b — Parakeet STT
NVIDIA Parakeet TDT-CTC 110M via NeMo toolkit.

Model: parakeet-tdt_ctc-110m (downloaded to NeMo cache by _dl_parakeet_stage1.py)
Runs on CPU (PyTorch in this env is CPU-only; faster-whisper uses CTranslate2 CUDA separately).

Windows notes:
- numba/llvmlite crash -> mock before any NeMo import
- numba.__version__ must exist or RNNT loss init fails -> set to "0.59.0"
- NeMo's from_pretrained(HF path) crashes (Winsock bug) -> use restore_from(local .nemo file)
- NeMo's from_pretrained(NGC) also crashes -> download via requests first (see _dl_parakeet_stage1.py)
"""

import os
import sys
import threading

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

# Windows: mock numba/llvmlite BEFORE any NeMo import
if sys.platform == "win32":
    from unittest.mock import MagicMock
    _numba_mock = MagicMock()
    _numba_mock.__version__ = "0.59.0"   # RNNT loss checks numba.__version__
    _numba_mock.cuda = MagicMock()
    _numba_mock.jit  = lambda f=None, **kw: (f if f else lambda fn: fn)
    _numba_mock.njit = _numba_mock.jit
    sys.modules.setdefault("numba",            _numba_mock)
    sys.modules.setdefault("numba.cuda",       _numba_mock.cuda)
    sys.modules.setdefault("numba.core",       MagicMock())
    sys.modules.setdefault("numba.typed",      MagicMock())
    sys.modules.setdefault("llvmlite",         MagicMock())
    sys.modules.setdefault("llvmlite.binding", MagicMock())

_LOCAL_NEMO = os.path.join(
    os.path.expanduser("~"),
    r".cache\torch\NeMo\NeMo_2.7.3\parakeet-tdt_ctc-110m"
    r"\c528f28c0fb089db853adccc81b5de93\parakeet-tdt_ctc-110m.nemo"
)

_model  = None
_lock   = threading.Lock()
_ready  = False


def load() -> bool:
    """Load Parakeet model from local cache. Returns True on success."""
    global _model, _ready

    if _ready:
        return True

    with _lock:
        if _ready:
            return True

        if not os.path.exists(_LOCAL_NEMO):
            print(f"[parakeet] Model file not found: {_LOCAL_NEMO}")
            print("[parakeet] Run: python _dl_parakeet_stage1.py  to download first.")
            return False

        try:
            # Sequential imports required — all-at-once (from X import a,b,c,d) crashes on Windows
            import nemo.collections.asr.models as _asr_models
            import nemo.collections.asr.data    # noqa
            import nemo.collections.asr.losses  # noqa
            import nemo.collections.asr.modules # noqa

            ModelCls = _asr_models.EncDecHybridRNNTCTCBPEModel
            print(f"[parakeet] Loading from local .nemo file...")
            import torch as _torch
            device = "cuda" if _torch.cuda.is_available() else "cpu"
            _model = ModelCls.restore_from(_LOCAL_NEMO, map_location=device)
            _model.eval()
            _ready = True
            print(f"[parakeet] Ready ({device})")
            return True

        except ImportError:
            print("[parakeet] NeMo not installed.")
            print("[parakeet] Install: pip install nemo_toolkit[asr]")
            return False

        except Exception as e:
            print(f"[parakeet] Load failed: {e}")
            return False


def transcribe(audio_path: str) -> str:
    """Transcribe audio file. audio_path must be WAV (16kHz mono)."""
    if not _ready:
        if not load():
            return ""

    try:
        output = _model.transcribe([audio_path])
        if output:
            first = output[0]
            # NeMo Hypothesis object
            if hasattr(first, "text"):
                return first.text.strip()
            # Plain string
            if isinstance(first, str):
                return first.strip()
        return ""

    except Exception as e:
        print(f"[parakeet] Transcribe error: {e}")
        return ""


def is_available() -> bool:
    """Check if NeMo is installed and local model file exists."""
    try:
        import nemo  # noqa
        return os.path.exists(_LOCAL_NEMO)
    except ImportError:
        return False


def is_ready() -> bool:
    return _ready

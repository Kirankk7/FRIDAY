"""Crypto / encoding toolkit — deterministic, model-independent transforms.

A unified registry of encode/decode/hash/JWT/cipher operations common in
pentesting, bug-bounty (JWT + token analysis, payload encoding) and CTF, plus
everyday "decode this base64" utility. Pure stdlib (AES needs pycryptodome,
which degrades gracefully if absent).

Adapted from VulnClaw's crypto_tools (MIT). Each op returns:
  {"success": bool, "result": str, "error": str(optional)}
"""
from __future__ import annotations

import base64
import codecs
import hashlib
import hmac
import html
import json
import re
import urllib.parse
from typing import Any, Optional

# ── Morse + Base58 tables ────────────────────────────────────────────
MORSE_ENCODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
    "'": ".----.", "!": "-.-.--", "/": "-..-.", "(": "-.--.", ")": "-.--.-",
    "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-", "+": ".-.-.",
    "-": "-....-", "_": "..--.-", '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
}
MORSE_DECODE = {v: k for k, v in MORSE_ENCODE.items()}
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

OPERATIONS: dict[str, dict[str, Any]] = {}


def _register(name: str, category: str, description: str,
              required_params: list[str], optional_params: dict[str, str] | None = None):
    def decorator(func):
        OPERATIONS[name] = {
            "function": func, "category": category, "description": description,
            "required_params": required_params, "optional_params": optional_params or {},
        }
        return func
    return decorator


# ── Encoding / decoding ──────────────────────────────────────────────
@_register("base64_encode", "encode", "Base64 encode", ["input"])
def _base64_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": base64.b64encode(input_str.encode()).decode("ascii")}


@_register("base64_decode", "decode", "Base64 decode (url-safe tolerant)", ["input"])
def _base64_decode(input_str: str, **_) -> dict:
    cleaned = input_str.strip()
    missing = len(cleaned) % 4
    padded = cleaned + ("=" * (4 - missing) if missing else "")
    try:
        return {"success": True, "result": base64.b64decode(padded).decode("utf-8", errors="replace")}
    except Exception as e:
        try:
            return {"success": True,
                    "result": base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")}
        except Exception:
            return {"success": False, "result": "", "error": f"Base64 decode failed: {e}"}


@_register("base32_encode", "encode", "Base32 encode", ["input"])
def _base32_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": base64.b32encode(input_str.encode()).decode("ascii")}


@_register("base32_decode", "decode", "Base32 decode", ["input"])
def _base32_decode(input_str: str, **_) -> dict:
    try:
        cleaned = input_str.strip().upper()
        missing = len(cleaned) % 8
        if missing:
            cleaned += "=" * (8 - missing)
        return {"success": True, "result": base64.b32decode(cleaned).decode("utf-8", errors="replace")}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Base32 decode failed: {e}"}


@_register("base58_encode", "encode", "Base58 encode (Bitcoin)", ["input"])
def _base58_encode(input_str: str, **_) -> dict:
    try:
        raw = input_str.encode()
        num = int.from_bytes(raw, "big")
        out = ""
        while num > 0:
            num, rem = divmod(num, 58)
            out = BASE58_ALPHABET[rem] + out
        for byte in raw:
            if byte == 0:
                out = "1" + out
            else:
                break
        return {"success": True, "result": out or "1"}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Base58 encode failed: {e}"}


@_register("base58_decode", "decode", "Base58 decode (Bitcoin)", ["input"])
def _base58_decode(input_str: str, **_) -> dict:
    try:
        s = input_str.strip()
        num = 0
        for char in s:
            num = num * 58 + BASE58_ALPHABET.index(char)
        leading = 0
        for char in s:
            if char == "1":
                leading += 1
            else:
                break
        body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
        return {"success": True, "result": (b"\x00" * leading + body).decode("utf-8", errors="replace")}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Base58 decode failed: {e}"}


@_register("hex_encode", "encode", "Hex encode", ["input"])
def _hex_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": input_str.encode().hex()}


@_register("hex_decode", "decode", "Hex decode", ["input"])
def _hex_decode(input_str: str, **_) -> dict:
    try:
        cleaned = input_str.strip()
        if cleaned.lower().startswith("0x"):
            cleaned = cleaned[2:]
        cleaned = cleaned.replace(" ", "")
        return {"success": True, "result": bytes.fromhex(cleaned).decode("utf-8", errors="replace")}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Hex decode failed: {e}"}


@_register("url_encode", "encode", "URL encode", ["input"])
def _url_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": urllib.parse.quote(input_str, safe="")}


@_register("url_decode", "decode", "URL decode", ["input"])
def _url_decode(input_str: str, **_) -> dict:
    try:
        return {"success": True, "result": urllib.parse.unquote(input_str.strip())}
    except Exception as e:
        return {"success": False, "result": "", "error": f"URL decode failed: {e}"}


@_register("html_encode", "encode", "HTML-entity encode", ["input"])
def _html_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": html.escape(input_str, quote=True)}


@_register("html_decode", "decode", "HTML-entity decode", ["input"])
def _html_decode(input_str: str, **_) -> dict:
    try:
        return {"success": True, "result": html.unescape(input_str.strip())}
    except Exception as e:
        return {"success": False, "result": "", "error": f"HTML decode failed: {e}"}


@_register("unicode_encode", "encode", r"Unicode-escape encode (\uXXXX)", ["input"])
def _unicode_encode(input_str: str, **_) -> dict:
    return {"success": True, "result": input_str.encode("unicode_escape").decode("ascii")}


@_register("unicode_decode", "decode", r"Unicode-escape decode (\uXXXX)", ["input"])
def _unicode_decode(input_str: str, **_) -> dict:
    try:
        return {"success": True,
                "result": input_str.strip().encode("ascii", errors="ignore").decode("unicode_escape")}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Unicode decode failed: {e}"}


@_register("rot13", "encode", "ROT13 (self-inverse)", ["input"])
def _rot13(input_str: str, **_) -> dict:
    return {"success": True, "result": codecs.encode(input_str, "rot_13")}


_register("rot13_decode", "decode", "ROT13 decode (self-inverse)", ["input"])(_rot13)


@_register("caesar_encode", "encode", "Caesar cipher encode", ["input"], {"shift": "shift amount, default 3"})
def _caesar_encode(input_str: str, shift: int = 3, **_) -> dict:
    shift = int(shift)
    out = []
    for ch in input_str:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return {"success": True, "result": "".join(out)}


@_register("caesar_decode", "decode", "Caesar decode (brute-forces all 25 if no shift)",
           ["input"], {"shift": "shift amount; omit to list all 25"})
def _caesar_decode(input_str: str, shift: Optional[int] = None, **_) -> dict:
    def shifted(s):
        out = []
        for ch in input_str:
            if ch.isalpha():
                base = ord("A") if ch.isupper() else ord("a")
                out.append(chr((ord(ch) - base - s) % 26 + base))
            else:
                out.append(ch)
        return "".join(out)
    if shift is not None:
        return {"success": True, "result": shifted(int(shift))}
    return {"success": True, "result": "\n".join(f"shift={s}: {shifted(s)}" for s in range(1, 26))}


@_register("morse_encode", "encode", "Morse encode", ["input"])
def _morse_encode(input_str: str, **_) -> dict:
    out = []
    for ch in input_str.upper():
        out.append("/" if ch == " " else MORSE_ENCODE.get(ch, "?"))
    return {"success": True, "result": " ".join(out)}


@_register("morse_decode", "decode", "Morse decode", ["input"])
def _morse_decode(input_str: str, **_) -> dict:
    try:
        out = []
        for word in input_str.strip().split("/"):
            for letter in word.strip().split():
                out.append(MORSE_DECODE.get(letter, "?"))
            out.append(" ")
        return {"success": True, "result": "".join(out).strip()}
    except Exception as e:
        return {"success": False, "result": "", "error": f"Morse decode failed: {e}"}


# ── Hashes ───────────────────────────────────────────────────────────
@_register("md5_hash", "hash", "MD5 hash", ["input"])
def _md5(input_str: str, **_) -> dict:
    return {"success": True, "result": hashlib.md5(input_str.encode()).hexdigest()}


@_register("sha1_hash", "hash", "SHA1 hash", ["input"])
def _sha1(input_str: str, **_) -> dict:
    return {"success": True, "result": hashlib.sha1(input_str.encode()).hexdigest()}


@_register("sha256_hash", "hash", "SHA256 hash", ["input"])
def _sha256(input_str: str, **_) -> dict:
    return {"success": True, "result": hashlib.sha256(input_str.encode()).hexdigest()}


@_register("sha512_hash", "hash", "SHA512 hash", ["input"])
def _sha512(input_str: str, **_) -> dict:
    return {"success": True, "result": hashlib.sha512(input_str.encode()).hexdigest()}


# ── JWT ──────────────────────────────────────────────────────────────
@_register("jwt_decode", "decode", "JWT decode (header + payload, no verify)", ["input"])
def _jwt_decode(input_str: str, **_) -> dict:
    try:
        parts = input_str.strip().split(".")
        if len(parts) != 3:
            return {"success": False, "result": "",
                    "error": "JWT must have 3 parts (header.payload.signature)"}

        def _seg(seg):
            missing = len(seg) % 4
            return json.loads(base64.urlsafe_b64decode(seg + ("=" * (4 - missing) if missing else "")))
        out = {"header": _seg(parts[0]), "payload": _seg(parts[1])}
        return {"success": True, "result": json.dumps(out, ensure_ascii=False, indent=2)}
    except Exception as e:
        return {"success": False, "result": "", "error": f"JWT decode failed: {e}"}


@_register("jwt_encode", "encode", "JWT encode (input=payload JSON)", ["input"],
           {"header": "header JSON", "secret": "HS256 key", "algorithm": "HS256 or none"})
def _jwt_encode(input_str: str, header: str = '{"alg":"HS256","typ":"JWT"}',
                secret: str = "", algorithm: str = "HS256", **_) -> dict:
    try:
        def _b64(obj):
            return base64.urlsafe_b64encode(
                json.dumps(obj, separators=(",", ":")).encode()).rstrip(b"=").decode()
        signing_input = f"{_b64(json.loads(header))}.{_b64(json.loads(input_str))}"
        if algorithm == "HS256" and secret:
            sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        elif algorithm == "none":
            sig_b64 = ""
        else:
            return {"success": False, "result": "", "error": f"Unsupported algorithm: {algorithm}"}
        return {"success": True, "result": f"{signing_input}.{sig_b64}"}
    except Exception as e:
        return {"success": False, "result": "", "error": f"JWT encode failed: {e}"}


# ── AES (CBC, PKCS7) — needs pycryptodome ────────────────────────────
@_register("aes_encrypt", "encrypt", "AES encrypt (CBC/PKCS7, base64 out)", ["input"],
           {"key": "16/24/32 bytes", "iv": "16 bytes, defaults to key"})
def _aes_encrypt(input_str: str, key: str = "", iv: str = "", **_) -> dict:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        key_bytes = key.encode() if key else b"0123456789abcdef"
        iv_bytes = (iv.encode() if iv else key_bytes)[:16]
        if len(key_bytes) not in (16, 24, 32):
            return {"success": False, "result": "", "error": "AES key must be 16/24/32 bytes"}
        enc = AES.new(key_bytes, AES.MODE_CBC, iv_bytes).encrypt(pad(input_str.encode(), AES.block_size))
        return {"success": True, "result": base64.b64encode(enc).decode()}
    except ImportError:
        return {"success": False, "result": "", "error": "AES needs pycryptodome (pip install pycryptodome)"}
    except Exception as e:
        return {"success": False, "result": "", "error": f"AES encrypt failed: {e}"}


@_register("aes_decrypt", "decrypt", "AES decrypt (CBC/PKCS7, base64 in)", ["input"],
           {"key": "16/24/32 bytes", "iv": "16 bytes, defaults to key"})
def _aes_decrypt(input_str: str, key: str = "", iv: str = "", **_) -> dict:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        key_bytes = key.encode() if key else b"0123456789abcdef"
        iv_bytes = (iv.encode() if iv else key_bytes)[:16]
        if len(key_bytes) not in (16, 24, 32):
            return {"success": False, "result": "", "error": "AES key must be 16/24/32 bytes"}
        dec = unpad(AES.new(key_bytes, AES.MODE_CBC, iv_bytes).decrypt(
            base64.b64decode(input_str.strip())), AES.block_size)
        return {"success": True, "result": dec.decode("utf-8", errors="replace")}
    except ImportError:
        return {"success": False, "result": "", "error": "AES needs pycryptodome (pip install pycryptodome)"}
    except Exception as e:
        return {"success": False, "result": "", "error": f"AES decrypt failed: {e}"}


# ── Auto-detect decode ───────────────────────────────────────────────
@_register("auto_decode", "decode", "Guess the encoding and decode (tries common schemes)", ["input"])
def _auto_decode(input_str: str, **_) -> dict:
    results, s = [], input_str.strip()
    if "%" in s:
        d = urllib.parse.unquote(s)
        if d != s:
            results.append(f"[URL] {d}")
    if "&" in s and (";" in s):
        d = html.unescape(s)
        if d != s:
            results.append(f"[HTML] {d}")
    if "\\u" in s:
        try:
            results.append(f"[Unicode] {s.encode('ascii', 'ignore').decode('unicode_escape')}")
        except Exception:
            pass
    if re.match(r"^[A-Za-z0-9+/]+=*$", s) and len(s) >= 4:
        try:
            d = base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8")
            if d and any(c.isprintable() for c in d):
                results.append(f"[Base64] {d}")
        except Exception:
            pass
    if re.match(r"^[A-Za-z0-9_-]+$", s) and len(s) >= 4:
        try:
            d = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8")
            if d and any(c.isprintable() for c in d):
                results.append(f"[Base64URL] {d}")
        except Exception:
            pass
    if re.match(r"^[A-Z2-7]+=*$", s.upper()) and len(s) >= 8:
        try:
            cleaned = s.upper()
            cleaned += "=" * (-len(cleaned) % 8)
            results.append(f"[Base32] {base64.b32decode(cleaned).decode('utf-8')}")
        except Exception:
            pass
    if re.match(r"^[0-9a-fA-F]+$", s) and len(s) % 2 == 0 and len(s) >= 2:
        try:
            d = bytes.fromhex(s).decode("utf-8")
            if d and any(c.isprintable() for c in d):
                results.append(f"[Hex] {d}")
        except Exception:
            pass
    if set(s) <= {".", "-", " ", "/"} and ("." in s or "-" in s):
        m = _morse_decode(s)
        if m["success"]:
            results.append(f"[Morse] {m['result']}")
    if s.isalpha():
        d = codecs.encode(s, "rot_13")
        if d != s:
            results.append(f"[ROT13] {d}")
    if not results:
        return {"success": False, "result": "", "error": "Could not auto-detect the encoding"}
    return {"success": True, "result": "\n".join(results)}


# ── Public API ───────────────────────────────────────────────────────
def execute(operation: str, input_str: str, **kwargs) -> dict:
    """Run a crypto op by name. Returns {success, result, error?}."""
    if operation not in OPERATIONS:
        return {"success": False, "result": "",
                "error": f"Unknown op: {operation}. Available: {', '.join(sorted(OPERATIONS))}"}
    try:
        return OPERATIONS[operation]["function"](input_str=input_str, **kwargs)
    except Exception as e:
        return {"success": False, "result": "", "error": f"Error running {operation}: {e}"}


def list_operations() -> dict[str, dict[str, str]]:
    return {
        name: {"category": info["category"], "description": info["description"],
               "required_params": ", ".join(info["required_params"]),
               "optional_params": ", ".join(f"{k}({v})" for k, v in info["optional_params"].items())}
        for name, info in sorted(OPERATIONS.items())
    }

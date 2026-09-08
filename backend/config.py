"""Local development configuration and WSL-aware Ollama discovery."""
from __future__ import annotations
import os
from pathlib import Path

def load_local_env(path: str = ".env") -> None:
    """Load local KEY=value settings without overwriting shell-provided secrets."""
    env_file = Path(path)
    if not env_file.exists(): return
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        key = key.strip(); value = value.strip().strip("'\"")
        if key and key not in os.environ: os.environ[key] = value

def windows_gateway() -> str | None:
    """Resolve the Windows/WSL NAT gateway when this process runs inside WSL."""
    try:
        for line in Path("/proc/net/route").read_text().splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[1] == "00000000":
                encoded = fields[2]
                return ".".join(str(int(encoded[offset:offset + 2], 16)) for offset in (6, 4, 2, 0))
    except OSError: pass
    return None

def ollama_hosts() -> list[str]:
    configured = os.getenv("OLLAMA_HOST", "").rstrip("/")
    candidates = [configured, "http://127.0.0.1:11434"]
    gateway = windows_gateway()
    if gateway: candidates.append(f"http://{gateway}:11434")
    return list(dict.fromkeys(host for host in candidates if host))

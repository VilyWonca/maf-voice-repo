from __future__ import annotations

"""
Basic configuration for the backend voice gateway.

In early stages we keep it simple and rely on environment variables only
where it is really necessary.
"""

import os


WS_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
WS_PORT: int = int(os.getenv("BACKEND_PORT", "8080"))

# WebSocket path that the frontend should use, e.g. ws://host:port/ws/voice
WS_PATH: str = os.getenv("BACKEND_WS_PATH", "/ws/voice")

# Duration of echo recording window in milliseconds.
# For the current MVP we simply record this long and then play it back.
ECHO_RECORD_DURATION_MS: int = int(os.getenv("ECHO_RECORD_DURATION_MS", "5000"))

# Test-only 5s echo mode (frontend audio -> backend -> back as WAV).
# Disabled by default; enable explicitly when you want to debug audio path.
ECHO_TEST_MODE: bool = os.getenv("ECHO_TEST_MODE", "0") == "1"

# Whether to log every single audio frame (very noisy).
LOG_AUDIO_FRAMES: bool = os.getenv("LOG_AUDIO_FRAMES", "0") == "1"



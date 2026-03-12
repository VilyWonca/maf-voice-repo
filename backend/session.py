from __future__ import annotations

"""
In-memory representation of a single voice session.

This is intentionally simple for the MVP:
- one WebSocket connection == one device / session
- finite set of states mirroring the frontend UI
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List
import json

from .protocol import (
    AssistantAudioEvent,
    AssistantProcessingEvent,
    AssistantTextEvent,
    AssistantTranscriptEvent,
    DebugPongEvent,
    ErrorEvent,
    SpeechEndedEvent,
    SpeechStartedEvent,
    WakeDetectedEvent,
)


class SessionState(str, Enum):
    IDLE = "idle"
    ARMED = "armed"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceSession:
    device_id: str
    websocket: Any  # websockets.WebSocketServerProtocol, but we don't hard-couple here

    state: SessionState = SessionState.IDLE
    frames_seen: int = 0
    # Raw float32 PCM payloads for current utterance (frontend -> backend)
    utterance_chunks: List[bytes] = field(default_factory=list)
    # Wall-clock timestamp (ms) when current recording started, or None.
    recording_started_at_ms: int | None = None
    # For future use: simple ring buffers for diagnostics etc.
    debug_events: List[dict[str, Any]] = field(default_factory=list)

    async def send_event(self, event: dict[str, Any]) -> None:
        await self.websocket.send(json.dumps(event, ensure_ascii=False))

    async def send_wake_detected(self) -> None:
        self.state = SessionState.ARMED
        event: WakeDetectedEvent = {"type": "wake.detected"}
        self.debug_events.append(event)
        print("[backend] EVENT wake.detected (start listening soon)")
        await self.send_event(event)

    async def send_speech_started(self) -> None:
        # Start a new utterance buffer
        self.utterance_chunks.clear()
        self.state = SessionState.RECORDING
        event: SpeechStartedEvent = {"type": "speech.started"}
        self.debug_events.append(event)
        print("[backend] EVENT speech.started (recording user audio)")
        await self.send_event(event)

    async def send_speech_ended(self) -> None:
        self.state = SessionState.PROCESSING
        event: SpeechEndedEvent = {"type": "speech.ended"}
        self.debug_events.append(event)
        print("[backend] EVENT speech.ended (stop recording, start processing)")
        await self.send_event(event)

    async def send_assistant_processing(self) -> None:
        event: AssistantProcessingEvent = {"type": "assistant.processing"}
        self.debug_events.append(event)
        print("[backend] EVENT assistant.processing")
        await self.send_event(event)

    async def send_fake_transcript_and_answer(self) -> None:
        transcript: AssistantTranscriptEvent = {
            "type": "assistant.transcript",
            "text": "Я услышал твою фразу и сейчас повторю её.",
        }
        answer: AssistantTextEvent = {
            "type": "assistant.text",
            "text": "Это эхо-режим: я просто проигрываю обратно твой голос.",
        }
        self.debug_events.append(transcript)
        self.debug_events.append(answer)
        print("[backend] EVENT assistant.transcript:", transcript["text"])
        print("[backend] EVENT assistant.text:", answer["text"])
        await self.send_event(transcript)
        await self.send_event(answer)

    async def send_assistant_audio_meta(self) -> None:
        """
        Send minimal assistant.audio meta.
        The actual binary audio data will follow as a separate binary message.
        """

        event: AssistantAudioEvent = {
            "type": "assistant.audio",
            "format": "wav",
            "mime_type": "audio/wav",
        }
        self.debug_events.append(event)
        print("[backend] EVENT assistant.audio (start speaking)")
        await self.send_event(event)
        self.state = SessionState.SPEAKING

    async def send_debug_pong(self, sent_at: int, echoed_at: int) -> None:
        event: DebugPongEvent = {
            "type": "debug.pong",
            "sent_at": sent_at,
            "echoed_at": echoed_at,
        }
        self.debug_events.append(event)
        await self.send_event(event)

    async def send_error(self, message: str) -> None:
        self.state = SessionState.ERROR
        event: ErrorEvent = {
            "type": "error",
            "message": message,
        }
        self.debug_events.append(event)
        await self.send_event(event)


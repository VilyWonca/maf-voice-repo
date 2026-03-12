from __future__ import annotations

"""
WebSocket server entry points and per-connection handler.

We intentionally keep this layer thin:
- accept connections
- instantiate VoiceSession
- route JSON and binary messages to simple MVP handlers
"""

import asyncio
import json
import time
from typing import Any, Awaitable, Callable

import websockets
from websockets.server import WebSocketServerProtocol

from backend import config
from backend.protocol import DebugPingEvent, PlaybackFinishedEvent, SessionStartEvent, build_wav_from_float32_chunks, parse_audio_frame
from backend.session import SessionState, VoiceSession


JsonHandler = Callable[[VoiceSession, dict[str, Any]], Awaitable[None]]


async def handle_client(websocket: WebSocketServerProtocol) -> None:
    """
    Handle a single WebSocket client (one robot).
    """

    print("[backend] new websocket connection")
    session: VoiceSession | None = None

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # Binary audio frame
                if session is None:
                    # Ignore stray audio before session.start, but log in future
                    print("[backend] got binary frame before session.start, ignoring")
                    continue

                await handle_audio_frame(session, message)
            else:
                # Text JSON frame
                data = json.loads(message)
                msg_type = data.get("type")

                print("[backend] JSON from client:", data)

                if msg_type == "session.start":
                    session = await handle_session_start(websocket, data)
                elif msg_type == "playback.finished" and session is not None:
                    await handle_playback_finished(session, data)
                elif msg_type == "debug.ping" and session is not None:
                    await handle_debug_ping(session, data)
                else:
                    # Unknown or out-of-order message: ignore for MVP
                    if session is not None:
                        await session.send_error(f"Unknown message type: {msg_type}")
    except websockets.ConnectionClosed:
        # Normal disconnect: nothing special to do in MVP
        return
    except Exception as exc:  # noqa: BLE001
        if session is not None:
            await session.send_error(f"Internal server error: {exc}")
        raise


async def handle_session_start(
    websocket: WebSocketServerProtocol, data: dict[str, Any]
) -> VoiceSession:
    event = SessionStartEvent(**data)  # type: ignore[arg-type]
    session = VoiceSession(device_id=event["device_id"], websocket=websocket)
    print(
        "[backend] session.start from device:",
        event["device_id"],
        "format:",
        event["audio_format"],
        "sr:",
        event["sample_rate"],
        "ch:",
        event["channels"],
    )
    return session


async def handle_playback_finished(
    session: VoiceSession, data: dict[str, Any]
) -> None:
    _event = PlaybackFinishedEvent(**data)  # type: ignore[arg-type]
    # For MVP we simply return to idle.
    session.state = SessionState.IDLE


async def handle_debug_ping(session: VoiceSession, data: dict[str, Any]) -> None:
    event = DebugPingEvent(**data)  # type: ignore[arg-type]
    now_ms = int(time.time() * 1000)
    await session.send_debug_pong(sent_at=event["sent_at"], echoed_at=now_ms)


async def handle_audio_frame(session: VoiceSession, raw: bytes) -> None:
    header, payload = parse_audio_frame(raw)
    session.frames_seen += 1

    if config.LOG_AUDIO_FRAMES:
        print(
            "[backend] audio frame:",
            "seq=",
            header.seq,
            "samples=",
            header.sample_count,
            "bytes=",
            len(raw),
            "state=",
            session.state.value,
        )

    # 5s echo test mode: record and play back audio once per session.
    if config.ECHO_TEST_MODE:
        now_ms = int(time.time() * 1000)

        # First audio we ever see in this session: start simple 5s echo recording.
        if session.state == SessionState.IDLE:
            await session.send_wake_detected()
            await session.send_speech_started()
            session.recording_started_at_ms = now_ms
            session.utterance_chunks.append(payload)
            return

        # While recording, accumulate raw float32 audio for echo
        if session.state == SessionState.RECORDING:
            session.utterance_chunks.append(payload)
            # Stop recording after configured duration and move to processing.
            if (
                session.recording_started_at_ms is not None
                and now_ms - session.recording_started_at_ms
                >= config.ECHO_RECORD_DURATION_MS
            ):
                await session.send_speech_ended()
                await session.send_assistant_processing()
                await asyncio.sleep(0.2)
                await session.send_fake_transcript_and_answer()
                await session.send_assistant_audio_meta()

                # Build a WAV file from the recorded utterance and send it back.
                wav_bytes = build_wav_from_float32_chunks(session.utterance_chunks)
                # Clear buffer so the next utterance starts fresh.
                session.utterance_chunks.clear()
                await session.websocket.send(wav_bytes)
                return

    # When ECHO_TEST_MODE is off we currently just ignore audio frames here;
    # higher-level voice pipeline will be plugged in later.


async def start_server() -> None:
    """
    Start the WebSocket server.

    For simplicity we currently accept all paths; the frontend is expected
    to connect to WS_PATH (e.g. /ws/voice), but we don't enforce it here
    to avoid tight coupling to the websockets.process_request API.
    """

    async def handler(websocket: WebSocketServerProtocol) -> None:
        await handle_client(websocket)

    server = await websockets.serve(
        handler,
        host=config.WS_HOST,
        port=config.WS_PORT,
    )

    await server.wait_closed()


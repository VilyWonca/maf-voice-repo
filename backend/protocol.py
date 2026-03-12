from __future__ import annotations

"""
Protocol definitions shared across the backend:

- JSON event payloads for client<->server control messages
- Binary audio frame codec (Float32 PCM LE, 48kHz, mono)
"""

from dataclasses import dataclass
from typing import Any, Literal, TypedDict, Iterable
import struct
import math


# === JSON event types ===

ClientEventType = Literal["session.start", "playback.finished", "debug.ping"]


class SessionStartEvent(TypedDict):
    type: Literal["session.start"]
    device_id: str
    audio_format: Literal["f32le"]
    sample_rate: int
    channels: int


class PlaybackFinishedEvent(TypedDict, total=False):
    type: Literal["playback.finished"]


class DebugPingEvent(TypedDict):
    type: Literal["debug.ping"]
    sent_at: int


ServerEventType = Literal[
    "wake.detected",
    "speech.started",
    "speech.ended",
    "assistant.processing",
    "assistant.transcript",
    "assistant.text",
    "assistant.audio",
    "error",
    "debug.pong",
]


class WakeDetectedEvent(TypedDict):
    type: Literal["wake.detected"]


class SpeechStartedEvent(TypedDict):
    type: Literal["speech.started"]


class SpeechEndedEvent(TypedDict):
    type: Literal["speech.ended"]


class AssistantProcessingEvent(TypedDict):
    type: Literal["assistant.processing"]


class AssistantTranscriptEvent(TypedDict):
    type: Literal["assistant.transcript"]
    text: str


class AssistantTextEvent(TypedDict):
    type: Literal["assistant.text"]
    text: str


class AssistantAudioEvent(TypedDict):
    type: Literal["assistant.audio"]
    format: str
    mime_type: str


class ErrorEvent(TypedDict, total=False):
    type: Literal["error"]
    message: str


class DebugPongEvent(TypedDict):
    type: Literal["debug.pong"]
    sent_at: int
    echoed_at: int


ServerEvent = (
    WakeDetectedEvent
    | SpeechStartedEvent
    | SpeechEndedEvent
    | AssistantProcessingEvent
    | AssistantTranscriptEvent
    | AssistantTextEvent
    | AssistantAudioEvent
    | ErrorEvent
    | DebugPongEvent
)


def as_json(event: ServerEvent) -> dict[str, Any]:
    """
    Identity helper with a clear return type.
    """

    return dict(event)


# === Binary audio frame codec ===

# < = little-endian
# I = uint32 (seq)
# H = uint16 (sample_count)
# H = uint16 (reserved)
FRAME_HEADER_STRUCT = struct.Struct("<IHH")


@dataclass
class AudioFrameHeader:
    seq: int
    sample_count: int
    reserved: int = 0

    def pack(self) -> bytes:
        return FRAME_HEADER_STRUCT.pack(self.seq, self.sample_count, self.reserved)

    @classmethod
    def unpack(cls, data: bytes) -> "AudioFrameHeader":
        if len(data) != FRAME_HEADER_STRUCT.size:
            raise ValueError(
                f"Invalid header size: expected {FRAME_HEADER_STRUCT.size}, got {len(data)}"
            )
        seq, sample_count, reserved = FRAME_HEADER_STRUCT.unpack(data)
        return cls(seq=seq, sample_count=sample_count, reserved=reserved)


def parse_audio_frame(raw: bytes) -> tuple[AudioFrameHeader, bytes]:
    """
    Split raw binary frame into header struct and PCM payload.
    """

    if len(raw) < FRAME_HEADER_STRUCT.size:
        raise ValueError("Frame too short to contain header")

    header_bytes = raw[: FRAME_HEADER_STRUCT.size]
    payload = raw[FRAME_HEADER_STRUCT.size :]
    header = AudioFrameHeader.unpack(header_bytes)

    expected_payload_size = header.sample_count * 4  # float32 mono
    if len(payload) != expected_payload_size:
        raise ValueError(
            f"Invalid payload size: expected {expected_payload_size}, got {len(payload)}"
        )

    return header, payload


def build_silent_audio_frame(seq: int, sample_count: int) -> bytes:
    """
    Build a simple 'silence' frame for assistant.audio playback.
    We don't care about real audio yet; we just want a valid frame.
    """

    header = AudioFrameHeader(seq=seq, sample_count=sample_count, reserved=0)
    # All-zero float32 samples == silence
    payload = b"\x00" * (sample_count * 4)
    return header.pack() + payload


def build_silent_wav(
    duration_seconds: float,
    sample_rate: int = 48_000,
    channels: int = 1,
) -> bytes:
    """
    Build a simple mono WAV file with a quiet test tone.

    We don't care about actual audio content here, only that the browser
    can decode it as audio/wav.
    """

    num_samples = int(math.ceil(duration_seconds * sample_rate))
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    data_size = num_samples * block_align
    fmt_chunk_size = 16
    riff_chunk_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)

    # RIFF header
    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", riff_chunk_size))
    header.extend(b"WAVE")

    # fmt chunk
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", fmt_chunk_size))
    header.extend(struct.pack("<H", 1))  # PCM
    header.extend(struct.pack("<H", channels))
    header.extend(struct.pack("<I", sample_rate))
    header.extend(struct.pack("<I", byte_rate))
    header.extend(struct.pack("<H", block_align))
    header.extend(struct.pack("<H", bits_per_sample))

    # data chunk header
    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))

    # Simple sine wave at 440 Hz, low amplitude to avoid clipping
    frequency = 440.0
    amplitude = 0.3  # 0..1
    samples = bytearray()
    for n in range(num_samples):
        t = n / sample_rate
        value = amplitude * math.sin(2.0 * math.pi * frequency * t)
        int_sample = int(max(-1.0, min(1.0, value)) * 32767)
        samples.extend(struct.pack("<h", int_sample))

    return bytes(header) + bytes(samples)


def build_wav_from_float32_chunks(
    chunks: Iterable[bytes],
    sample_rate: int = 48_000,
    channels: int = 1,
) -> bytes:
    """
    Convert raw Float32 PCM LE chunks (mono) into a 16-bit PCM WAV file.

    This lets us "echo" the user utterance back to the browser.
    """

    # Decode float32 samples from all chunks
    float_samples: list[float] = []
    for chunk in chunks:
        # Each sample is 4 bytes, little-endian float32
        for (value,) in struct.iter_unpack("<f", chunk):
            # Clamp to [-1.0, 1.0] just in case
            if value > 1.0:
                value = 1.0
            elif value < -1.0:
                value = -1.0
            float_samples.append(value)

    if not float_samples:
        # Fallback: short tone if we somehow have no data
        return build_silent_wav(duration_seconds=0.3, sample_rate=sample_rate, channels=channels)

    num_samples = len(float_samples)
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = num_samples * block_align
    fmt_chunk_size = 16
    riff_chunk_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)

    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", riff_chunk_size))
    header.extend(b"WAVE")

    header.extend(b"fmt ")
    header.extend(struct.pack("<I", fmt_chunk_size))
    header.extend(struct.pack("<H", 1))  # PCM
    header.extend(struct.pack("<H", channels))
    header.extend(struct.pack("<I", sample_rate))
    header.extend(struct.pack("<I", byte_rate))
    header.extend(struct.pack("<H", block_align))
    header.extend(struct.pack("<H", bits_per_sample))

    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))

    samples_bytes = bytearray()
    for v in float_samples:
        int_sample = int(v * 32767.0)
        samples_bytes.extend(struct.pack("<h", int_sample))

    return bytes(header) + bytes(samples_bytes)


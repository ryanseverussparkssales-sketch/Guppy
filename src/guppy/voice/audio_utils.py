"""Shared audio format utilities for the voice module."""
from __future__ import annotations

import io
import struct


def pcm_to_wav(pcm: bytes, sample_rate: int = 22050, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw 16-bit PCM bytes in a minimal WAV container."""
    data_size = len(pcm)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack(
        "<IHHIIHH",
        16, 1, channels, sample_rate,
        sample_rate * channels * bits // 8,
        channels * bits // 8,
        bits,
    ))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm)
    return buf.getvalue()

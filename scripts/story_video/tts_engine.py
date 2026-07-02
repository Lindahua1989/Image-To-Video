import asyncio
import json
import re
from pathlib import Path
from typing import List, Tuple

import edge_tts

DEFAULT_VOICE = "zh-CN-YunxiNeural"
VOICES = {
    "yunxi": "zh-CN-YunxiNeural",
    "yunjian": "zh-CN-YunjianNeural",
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "yunyang": "zh-CN-YunyangNeural",
}

CHINESE_PUNCT = "，。！？；：、""''（）【】《》…—"
SPLIT_PATTERN = re.compile(rf"[{re.escape(CHINESE_PUNCT)}]")


def split_text_to_subtitles(text: str, max_chars: int = 12) -> List[Tuple[str, int, int]]:
    """
    Split Chinese text into subtitle segments at punctuation marks.
    Returns list of (text, start_index, end_index) tuples.
    """
    segments = []
    current = ""
    start_idx = 0

    for i, char in enumerate(text):
        current += char
        if SPLIT_PATTERN.match(char) and len(current) >= max_chars // 2:
            segments.append((current.strip(), start_idx, i + 1))
            current = ""
            start_idx = i + 1
        elif len(current) >= max_chars:
            segments.append((current.strip(), start_idx, i + 1))
            current = ""
            start_idx = i + 1

    if current.strip():
        segments.append((current.strip(), start_idx, len(text)))

    return segments


async def _generate_tts(
    text: str,
    output_path: str,
    voice: str,
) -> List[dict]:
    """
    Generate TTS audio and collect word/sentence-level timing.
    Returns list of {text, offset_ms, duration_ms} dicts.
    """
    comm = edge_tts.Communicate(text, voice)
    segments = []
    audio_data = bytearray()

    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            segments.append({
                "text": chunk["text"],
                "offset_ms": chunk["offset"] / 10000,
                "duration_ms": chunk["duration"] / 10000,
            })

    with open(output_path, "wb") as f:
        f.write(audio_data)

    return segments


def generate_audio(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
) -> dict:
    """
    Generate TTS audio and subtitle timing data.
    Returns {"audio_path": str, "duration": float, "segments": [...]}
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if voice in VOICES:
        voice = VOICES[voice]

    segments = asyncio.run(_generate_tts(text, output_path, voice))

    total_duration = 0
    if segments:
        total_duration = (segments[-1]["offset_ms"] + segments[-1]["duration_ms"]) / 1000.0

    print(f"[TTS] Audio: {output_path} | Duration: {total_duration:.1f}s | Segments: {len(segments)}")

    return {
        "audio_path": output_path,
        "duration": total_duration,
        "segments": segments,
    }


def generate_srt(segments: List[dict], output_path: str):
    """Generate SRT subtitle file from word-level segments, grouped into subtitle lines."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lines = []
    current_text = ""
    current_start = None
    current_end = None
    max_chars = 14

    for seg in segments:
        if current_start is None:
            current_start = seg["offset_ms"]
        if current_text == "":
            current_text = seg["text"]
        else:
            current_text += seg["text"]
        current_end = seg["offset_ms"] + seg["duration_ms"]

        if len(current_text) >= max_chars or seg["text"] in "。！？":
            lines.append((current_text.strip(), current_start, current_end))
            current_text = ""
            current_start = None

    if current_text.strip() and current_start is not None:
        lines.append((current_text.strip(), current_start, current_end))

    def ms_to_srt_time(ms):
        hours = int(ms // 3600000)
        minutes = int((ms % 3600000) // 60000)
        seconds = int((ms % 60000) // 1000)
        millis = int(ms % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    with open(output_path, "w", encoding="utf-8") as f:
        for i, (text, start, end) in enumerate(lines, 1):
            f.write(f"{i}\n")
            f.write(f"{ms_to_srt_time(start)} --> {ms_to_srt_time(end)}\n")
            f.write(f"{text}\n\n")

    print(f"[TTS] SRT saved: {output_path} | {len(lines)} subtitle lines")
    return lines

"""
FFmpeg-based video composer - 10x faster than moviepy.

Uses zoompan for Ken Burns effect, xfade for crossfade transitions,
and subtitles filter for SRT overlay. Calls the bundled imageio_ffmpeg binary.
"""

import json
import subprocess
import random
from pathlib import Path
from typing import List, Optional

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

TARGET_W, TARGET_H = 1080, 1920
FPS = 30
FADE_DURATION = 0.5
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

ZOOM_PRESETS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_down"]


def _build_zoompan_filter(
    effect: str,
    duration: float,
    fps: int = FPS,
) -> str:
    """Build zoompan filter string for a given effect."""
    d = int(duration * fps)

    if effect == "zoom_in":
        return (
            f"zoompan=z='1+0.15*on/{d}'"
            f":d={d}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )
    elif effect == "zoom_out":
        return (
            f"zoompan=z='1.15-0.15*on/{d}'"
            f":d={d}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )
    elif effect == "pan_left":
        return (
            f"zoompan=z='1.3':d={d}"
            f":x='(iw-iw/zoom)*(1-on/{max(d-1,1)})':y='ih/2-(ih/zoom/2)'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )
    elif effect == "pan_right":
        return (
            f"zoompan=z='1.3':d={d}"
            f":x='(iw-iw/zoom)*on/{max(d-1,1)}':y='ih/2-(ih/zoom/2)'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )
    elif effect == "pan_down":
        return (
            f"zoompan=z='1.3':d={d}"
            f":x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{max(d-1,1)}'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )
    else:
        return (
            f"zoompan=z='1+0.1*on/{d}'"
            f":d={d}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={TARGET_W}x{TARGET_H}:fps={fps}"
        )


def _build_scene_filter(
    image_path: str,
    duration: float,
    effect: str,
    label: str,
) -> str:
    """Build filter string for one scene: scale + crop + zoompan + format."""
    zoompan = _build_zoompan_filter(effect, duration)
    safe_path = image_path.replace("\\", "/").replace(":", "\\:")

    return (
        f"[{label}:v]"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"{zoompan},"
        f"settb=AVTB,"
        f"setpts=PTS-STARTPTS,"
        f"format=yuv420p"
        f"[v{label}]"
    )


def _build_blurred_bg_filter(
    image_path: str,
    duration: float,
    label: str,
) -> str:
    """Build filter for blurred background + centered foreground image with zoompan."""
    d = int(duration * FPS)

    return (
        f"[{label}:v]split=2[bg{label}][fg{label}];"
        f"[bg{label}]"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"gblur=sigma=25,"
        f"eq=brightness=-0.2[bgblurred{label}];"
        f"[fg{label}]"
        f"scale=-1:{int(TARGET_H * 0.72)}:force_original_aspect_ratio=decrease[fgscaled{label}];"
        f"[bgblurred{label}][fgscaled{label}]"
        f"overlay=(W-w)/2:(H-h)/2:format=auto,"
        f"format=yuv420p,"
        f"fps={FPS},"
        f"settb=AVTB,"
        f"setpts=PTS-STARTPTS"
        f"[v{label}]"
    )


def _generate_merged_srt(
    scenes: List[dict],
    output_path: str,
    fade_duration: float = FADE_DURATION,
) -> str:
    """Merge per-scene SRT timings into one global SRT file."""
    lines = []
    idx = 1
    current_time = 0.0

    for i, scene in enumerate(scenes):
        duration = scene["duration"]
        scene_start = current_time

        for text, start_ms, end_ms in scene.get("subtitles", []):
            abs_start = scene_start + start_ms / 1000.0
            abs_end = scene_start + end_ms / 1000.0

            if i > 0:
                abs_start = max(abs_start, current_time + fade_duration)

            lines.append(str(idx))
            lines.append(f"{_srt_time(abs_start)} --> {_srt_time(abs_end)}")
            lines.append(text)
            lines.append("")
            idx += 1

        current_time += duration

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[FFmpeg] Merged SRT: {output_path} | {idx-1} entries")
    return output_path


def _srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _merge_audio_files(
    audio_paths: List[str],
    durations: List[float],
    output_path: str,
    buffer: float = 0.3,
) -> str:
    """Concatenate per-scene audio files with silence buffer using ffmpeg."""
    if len(audio_paths) == 1:
        return audio_paths[0]

    list_file = Path(output_path).with_suffix(".txt")
    lines = []
    for ap in audio_paths:
        lines.append(f"file '{ap.replace(chr(92), "/")}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "Merge audio")
    list_file.unlink(missing_ok=True)
    return str(output_path)


def _run_ffmpeg(cmd: List[str], label: str = "FFmpeg"):
    """Run ffmpeg command and raise on error."""
    print(f"[FFmpeg] {label}...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr_tail = result.stderr[-3000:] if result.stderr else ""
        raise RuntimeError(f"FFmpeg failed ({label}):\n{stderr_tail}")


def compose_video_ffmpeg(
    scenes: List[dict],
    output_path: str,
    fps: int = FPS,
    fade_duration: float = FADE_DURATION,
    use_blur_bg: bool = True,
) -> str:
    """
    Compose final video using FFmpeg zoompan + xfade.

    Two-pass approach:
    1. Render each scene as an intermediate MP4 (reliable, avoids filter_complex issues)
    2. Concatenate with xfade transitions + overlay subtitles + add audio

    Each scene: {image_path, audio_path, duration, subtitles: [(text, start_ms, end_ms)]}
    """
    if not scenes:
        raise ValueError("No scenes to compose")

    work_dir = Path(output_path).parent
    work_dir.mkdir(parents=True, exist_ok=True)

    n = len(scenes)
    print(f"[FFmpeg] Composing {n} scenes, target {TARGET_W}x{TARGET_H}@{fps}fps")

    effects = [random.choice(ZOOM_PRESETS) for _ in range(n)]
    if n >= 2:
        for i in range(1, n):
            while effects[i] == effects[i-1]:
                effects[i] = random.choice(ZOOM_PRESETS)

    scene_videos = []
    for i, scene in enumerate(scenes):
        duration = scene["duration"]
        image_path = scene["image_path"]
        scene_mp4 = str(work_dir / f"_scene_{i:02d}.mp4")

        if use_blur_bg:
            scene_filter = _build_blurred_bg_filter(image_path, duration, "0")
        else:
            scene_filter = _build_scene_filter(image_path, duration, effects[i], "0")

        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
            "-i", image_path,
            "-filter_complex", f"[0:v]{scene_filter[4:]}",  
            "-map", "[v0]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            scene_mp4,
        ]

        filter_str = scene_filter
        if use_blur_bg:
            filter_str = (
                f"[0:v]split=2[bg0][fg0];"
                f"[bg0]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
                f"crop={TARGET_W}:{TARGET_H},gblur=sigma=25,eq=brightness=-0.2[bgblurred0];"
                f"[fg0]scale=-1:{int(TARGET_H * 0.72)}:force_original_aspect_ratio=decrease[fgscaled0];"
                f"[bgblurred0][fgscaled0]overlay=(W-w)/2:(H-h)/2:format=auto,"
                f"format=yuv420p,fps={fps},settb=AVTB,setpts=PTS-STARTPTS[v0]"
            )
        else:
            zoompan = _build_zoompan_filter(effects[i], duration, fps)
            filter_str = (
                f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
                f"crop={TARGET_W}:{TARGET_H},{zoompan},"
                f"settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v0]"
            )

        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
            "-i", image_path,
            "-filter_complex", filter_str,
            "-map", "[v0]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-video_track_timescale", str(fps),
            scene_mp4,
        ]

        _run_ffmpeg(cmd, f"Scene {i+1}/{n} ({effects[i] if not use_blur_bg else 'blur'})")
        scene_videos.append(scene_mp4)

    print(f"[FFmpeg] Concatenating {n} scenes with xfade transitions...")

    if n == 1:
        final_video = scene_videos[0]
    else:
        inputs = []
        for sv in scene_videos:
            inputs.extend(["-i", sv])

        filter_parts = []
        prev = "[0:v]"
        accumulated = scenes[0]["duration"]

        for i in range(1, n):
            offset = accumulated - fade_duration
            new_label = f"[x{i}]"
            transition = random.choice(["fade", "fade", "dissolve", "wipeleft"])
            filter_parts.append(
                f"{prev}[{i}:v]xfade="
                f"transition={transition}:"
                f"duration={fade_duration}:"
                f"offset={offset:.3f}{new_label}"
            )
            prev = new_label
            accumulated += scenes[i]["duration"] - fade_duration

        final_label = prev

        srt_path = str(work_dir / "_subtitles.srt")
        _generate_merged_srt(scenes, srt_path, fade_duration)
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        filter_parts.append(
            f"{final_label}subtitles="
            f"filename='{srt_escaped}':"
            f"force_style='Fontname=SimHei,Fontsize=18,Bold=1,"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"BorderStyle=3,Outline=2,Shadow=0,MarginV=60'"
            f"[vfinal]"
        )

        filter_complex = ";".join(filter_parts)

        audio_files = [s.get("audio_path") for s in scenes if s.get("audio_path")]
        audio_input = []
        audio_map = []
        if audio_files:
            if len(audio_files) == 1:
                audio_input = ["-i", audio_files[0]]
                audio_map = ["-map", f"{n}:a"]
            else:
                merged_audio = str(work_dir / "_merged_audio.mp3")
                _merge_audio_files(audio_files, [s["duration"] for s in scenes], merged_audio)
                audio_input = ["-i", merged_audio]
                audio_map = ["-map", f"{n}:a"]

        concat_cmd = [
            FFMPEG, "-y",
            *inputs,
            *audio_input,
            "-filter_complex", filter_complex,
            "-map", "[vfinal]",
            *audio_map,
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
        ]

        if audio_files:
            concat_cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])

        concat_cmd.append(str(output_path))
        _run_ffmpeg(concat_cmd, f"Concatenate + subtitles ({n} scenes)")

        for sv in scene_videos:
            Path(sv).unlink(missing_ok=True)
        for tmp in [work_dir / "_merged_audio.mp3", work_dir / "_subtitles.srt"]:
            tmp.unlink(missing_ok=True)

    file_size = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"[FFmpeg] Done! {output_path} ({file_size:.1f} MB)")
    return output_path

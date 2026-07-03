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

DEFAULT_SUBTITLE_STYLE = {
    "fontname": "SimHei",
    "fontsize": 28,
    "bold": 1,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H00000000",
    "back_colour": "&H80000000",
    "border_style": 3,
    "outline": 2,
    "shadow": 0,
    "alignment": 2,
    "margin_l": 60,
    "margin_r": 60,
    "margin_v": 100,
    "spacing": 1,
}


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB to (R, G, B) tuple for PIL."""
    c = hex_color.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _render_text_card_image(
    width: int,
    height: int,
    bg_color: str,
    lines: list,
    output_path: str,
) -> str:
    """Render a text card image using PIL (avoids FFmpeg drawtext escaping issues)."""
    from PIL import Image, ImageDraw, ImageFont

    bg_rgb = _hex_to_rgb(bg_color)
    img = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(img)

    total_lines = len(lines)
    center_y = height // 2

    for idx, (text, color, fontsize) in enumerate(lines):
        text_rgb = _hex_to_rgb(color)
        try:
            font = ImageFont.truetype(FONT_PATH, fontsize)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        spacing = 100
        y_offset = -((total_lines - 1) * spacing) // 2 + idx * spacing
        x = (width - text_w) // 2
        y = center_y + y_offset - text_h // 2

        draw.text((x, y), text, fill=text_rgb, font=font)

    img.save(output_path, "PNG")
    return output_path


def _generate_intro_video(
    config: dict,
    topic: str,
    output_path: str,
    fps: int = FPS,
) -> str:
    """Generate intro title card video: PIL image → FFmpeg video with fades."""
    duration = config.get("duration", 2.5)
    bg_color = config.get("bg_color", "#1a0a2e")
    text_color = config.get("text_color", "#FFD700")
    subtitle_color = config.get("subtitle_color", "#C0C0C0")

    title = config.get("title_template", "{topic}").format(topic=topic)
    subtitle = config.get("subtitle_template", "")

    work_dir = Path(output_path).parent
    img_path = str(work_dir / "_intro_card.png")

    lines = [(title, text_color, 90)]
    if subtitle:
        lines.append((subtitle, subtitle_color, 40))

    _render_text_card_image(TARGET_W, TARGET_H, bg_color, lines, img_path)

    fade_in_end = min(0.5, duration / 3)
    fade_out_start = duration - fade_in_end

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
        "-i", img_path,
        "-vf", f"fade=t=in:st=0:d={fade_in_end},fade=t=out:st={fade_out_start}:d={fade_in_end},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-video_track_timescale", str(fps),
        output_path,
    ]
    _run_ffmpeg(cmd, "Intro title card")
    Path(img_path).unlink(missing_ok=True)
    return output_path


def _generate_outro_video(
    config: dict,
    output_path: str,
    fps: int = FPS,
) -> str:
    """Generate outro follow-prompt video: PIL image → FFmpeg video with fades."""
    duration = config.get("duration", 2.5)
    bg_color = config.get("bg_color", "#1a0a2e")
    text_color = config.get("text_color", "#FFD700")

    text = config.get("text", "关注我\n看更多精彩故事")
    lines_raw = text.split("\n")

    work_dir = Path(output_path).parent
    img_path = str(work_dir / "_outro_card.png")

    lines = []
    for idx, line in enumerate(lines_raw):
        fontsize = 80 if idx == 0 else 44
        lines.append((line, text_color, fontsize))

    _render_text_card_image(TARGET_W, TARGET_H, bg_color, lines, img_path)

    fade_in_end = min(0.5, duration / 3)
    fade_out_start = duration - fade_in_end

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
        "-i", img_path,
        "-vf", f"fade=t=in:st=0:d={fade_in_end},fade=t=out:st={fade_out_start}:d={fade_in_end},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-video_track_timescale", str(fps),
        output_path,
    ]
    _run_ffmpeg(cmd, "Outro follow card")
    Path(img_path).unlink(missing_ok=True)
    return output_path


def _build_complete_audio(
    scene_audio_files: List[str],
    scene_durations: List[float],
    output_path: str,
    intro_duration: float = 0.0,
    outro_duration: float = 0.0,
    buffer: float = 0.3,
    bgm_path: str = "",
    bgm_volume: float = 0.12,
) -> str:
    """Build complete audio track: silence(intro) + narration + silence(outro) + BGM mix."""
    work_dir = Path(output_path).parent

    parts = []

    if intro_duration > 0:
        intro_silence = str(work_dir / "_silence_intro.mp3")
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{intro_duration:.3f}",
            "-c:a", "libmp3lame",
            intro_silence,
        ]
        _run_ffmpeg(cmd, "Intro silence")
        parts.append(intro_silence)

    for af in scene_audio_files:
        parts.append(af)

    if outro_duration > 0:
        outro_silence = str(work_dir / "_silence_outro.mp3")
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{outro_duration:.3f}",
            "-c:a", "libmp3lame",
            outro_silence,
        ]
        _run_ffmpeg(cmd, "Outro silence")
        parts.append(outro_silence)

    if len(parts) == 1:
        merged = parts[0]
    else:
        list_file = work_dir / "_audio_list.txt"
        lines = [f"file '{p.replace(chr(92), '/')}'" for p in parts]
        list_file.write_text("\n".join(lines), encoding="utf-8")

        merged = str(work_dir / "_narration_full.mp3")
        cmd = [
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy",
            merged,
        ]
        _run_ffmpeg(cmd, "Merge narration + silence")
        list_file.unlink(missing_ok=True)
        for p in parts:
            if "silence" in p:
                Path(p).unlink(missing_ok=True)

    if bgm_path and Path(bgm_path).exists():
        mixed = str(work_dir / "_audio_final.mp3")
        cmd = [
            FFMPEG, "-y",
            "-i", merged,
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]aloop=loop=-1:size=2e9,volume={bgm_volume}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "[aout]",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            mixed,
        ]
        _run_ffmpeg(cmd, "Mix BGM + narration")
        if merged != parts[0]:
            Path(merged).unlink(missing_ok=True)
        merged = mixed

    return merged


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
    time_offset: float = 0.0,
) -> str:
    """Merge per-scene SRT timings into one global SRT file.

    time_offset: seconds to shift all timestamps (for intro duration).
    """
    lines = []
    idx = 1
    current_time = time_offset

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

    print(f"[FFmpeg] Merged SRT: {output_path} | {idx-1} entries | offset={time_offset:.1f}s")
    return output_path


def _srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format: H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _generate_merged_ass(
    scenes: List[dict],
    output_path: str,
    style: dict,
    fade_duration: float = FADE_DURATION,
    time_offset: float = 0.0,
    fade_ms: int = 200,
) -> str:
    """Generate an ASS subtitle file with fade animations and fixed positioning.

    Uses \\an8\\pos(x,y) to anchor the TOP of every subtitle at a fixed Y
    coordinate, eliminating position jumping between 1-line and multi-line
    subtitles. The top Y is computed from margin_v (bottom margin) and the
    max line count so the longest subtitle's bottom matches margin_v.

    style: dict of ASS style parameters (fontname, fontsize, colours, etc.)
    time_offset: seconds to shift all timestamps (for intro duration).
    fade_ms: fade in/out duration in milliseconds.
    """
    s = {**DEFAULT_SUBTITLE_STYLE, **(style or {})}

    def colour(val):
        return val if str(val).startswith("&H") else f"&H{val}"

    fontsize = s.get("fontsize", 28)
    margin_v = s.get("margin_v", 60)
    line_height = fontsize * 1.3  # CJK line height approximation

    header = f"""[Script Info]
Title: Story Subtitles
ScriptType: v4.00+
WrapStyle: 2
PlayResX: {TARGET_W}
PlayResY: {TARGET_H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{s['fontname']},{fontsize},{colour(s['primary_colour'])},&H000000FF,{colour(s['outline_colour'])},{colour(s['back_colour'])},{s.get('bold',0)},0,0,0,100,100,{s.get('spacing',0)},0,{s.get('border_style',1)},{s.get('outline',2)},{s.get('shadow',0)},2,{s.get('margin_l',20)},{s.get('margin_r',20)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    current_time = time_offset

    # First pass: process all subtitles with auto-wrapping
    processed = []  # list of (abs_start, abs_end, wrapped_text)
    for i, scene in enumerate(scenes):
        duration = scene["duration"]
        scene_start = current_time

        for text, start_ms, end_ms in scene.get("subtitles", []):
            abs_start = scene_start + start_ms / 1000.0
            abs_end = scene_start + end_ms / 1000.0

            if i > 0:
                abs_start = max(abs_start, current_time + fade_duration)

            # Escape any special ASS characters in text
            safe_text = text.replace("\\N", "\\\\N").replace("\\n", "\\\\n")
            # Wrap long lines: insert \N at ~16 chars for readability
            if len(safe_text) > 16:
                mid = len(safe_text) // 2
                # Find nearest space or punctuation
                for offset in range(min(6, len(safe_text) - mid)):
                    for pos in [mid + offset, mid - offset]:
                        if 0 <= pos < len(safe_text):
                            if safe_text[pos] in "，。、！？ ":
                                safe_text = safe_text[:pos+1] + "\\N" + safe_text[pos+1:]
                                break
                    else:
                        continue
                    break

            processed.append((abs_start, abs_end, safe_text))

        current_time += duration

    # Find max line count to compute a fixed top Y position
    max_lines = max((t.count("\\N") + 1 for _, _, t in processed), default=1)
    # Top Y: so that a max_lines-tall subtitle has its bottom at (TARGET_H - margin_v)
    top_y = int(TARGET_H - margin_v - max_lines * line_height)
    center_x = TARGET_W // 2

    # Second pass: write dialogue lines with \an8\pos for fixed top position
    override = f"\\fad({fade_ms},{fade_ms})\\an8\\pos({center_x},{top_y})"

    for abs_start, abs_end, safe_text in processed:
        lines.append(
            f"Dialogue: 0,{_ass_time(abs_start)},{_ass_time(abs_end)},"
            f"Default,,0,0,0,,{{{override}}}{safe_text}"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    n_entries = len(lines) - 1  # subtract header block
    print(f"[FFmpeg] Merged ASS: {output_path} | {n_entries} entries | offset={time_offset:.1f}s | fade={fade_ms}ms")
    return output_path


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
        encoding="utf-8",
        errors="replace",
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
    bgm_path: str = "",
    bgm_volume: float = 0.12,
    subtitle_style=None,
    intro_config: Optional[dict] = None,
    outro_config: Optional[dict] = None,
    topic: str = "",
) -> str:
    """
    Compose final video using FFmpeg zoompan + xfade.

    Two-pass approach:
    1. Render each scene as an intermediate MP4 (reliable, avoids filter_complex issues)
    2. Concatenate with xfade transitions + overlay subtitles + add audio

    Each scene: {image_path, audio_path, duration, subtitles: [(text, start_ms, end_ms)]}

    Optional:
    - bgm_path: path to BGM audio file, mixed at bgm_volume
    - subtitle_style: FFmpeg force_style string for subtitles
    - intro_config: dict with intro settings (enabled, duration, title_template, etc.)
    - outro_config: dict with outro settings (enabled, duration, text, etc.)
    - topic: used for intro title text
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

    # Generate intro/outro if enabled
    intro_dur = 0.0
    outro_dur = 0.0

    segments = []  # list of (video_path, duration)

    if intro_config and intro_config.get("enabled"):
        intro_path = str(work_dir / "_intro.mp4")
        _generate_intro_video(intro_config, topic or "故事", intro_path, fps)
        intro_dur = intro_config.get("duration", 2.5)
        segments.append((intro_path, intro_dur))
        print(f"[FFmpeg] Intro: {intro_dur:.1f}s")

    for i, sv in enumerate(scene_videos):
        segments.append((sv, scenes[i]["duration"]))

    if outro_config and outro_config.get("enabled"):
        outro_path = str(work_dir / "_outro.mp4")
        _generate_outro_video(outro_config, outro_path, fps)
        outro_dur = outro_config.get("duration", 2.5)
        segments.append((outro_path, outro_dur))
        print(f"[FFmpeg] Outro: {outro_dur:.1f}s")

    total_n = len(segments)

    if total_n == 1:
        import shutil
        shutil.copy2(segments[0][0], output_path)
    else:
        inputs = []
        for sv_path, _ in segments:
            inputs.extend(["-i", sv_path])

        filter_parts = []
        prev = "[0:v]"
        accumulated = segments[0][1]

        for i in range(1, total_n):
            offset = accumulated - fade_duration
            new_label = f"[x{i}]"
            is_edge = (i == 1 and intro_dur > 0) or (i == total_n - 1 and outro_dur > 0)
            transition = "fade" if is_edge else random.choice(["fade", "fade", "dissolve", "wipeleft"])
            filter_parts.append(
                f"{prev}[{i}:v]xfade="
                f"transition={transition}:"
                f"duration={fade_duration}:"
                f"offset={offset:.3f}{new_label}"
            )
            prev = new_label
            accumulated += segments[i][1] - fade_duration

        final_label = prev

        if isinstance(subtitle_style, dict):
            sub_path = str(work_dir / "_subtitles.ass")
            _generate_merged_ass(scenes, sub_path, subtitle_style, fade_duration, time_offset=intro_dur)
            sub_escaped = sub_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(
                f"{final_label}subtitles="
                f"filename='{sub_escaped}'"
                f"[vfinal]"
            )
        else:
            style_str = subtitle_style or DEFAULT_SUBTITLE_STYLE
            if isinstance(style_str, dict):
                style_str = ",".join(f"{k}={v}" for k, v in style_str.items())
            srt_path = str(work_dir / "_subtitles.srt")
            _generate_merged_srt(scenes, srt_path, fade_duration, time_offset=intro_dur)
            srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(
                f"{final_label}subtitles="
                f"filename='{srt_escaped}':"
                f"force_style='{style_str}'"
                f"[vfinal]"
            )

        filter_complex = ";".join(filter_parts)

        audio_files = [s.get("audio_path") for s in scenes if s.get("audio_path")]
        audio_input = []
        audio_map = []
        if audio_files:
            complete_audio = _build_complete_audio(
                audio_files,
                [s["duration"] for s in scenes],
                str(work_dir / "_audio_complete.mp3"),
                intro_duration=intro_dur,
                outro_duration=outro_dur,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
            )
            audio_input = ["-i", complete_audio]
            audio_map = ["-map", f"{total_n}:a"]

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
        _run_ffmpeg(concat_cmd, f"Concatenate + subtitles ({total_n} segments)")

        for sv_path, _ in segments:
            Path(sv_path).unlink(missing_ok=True)
        for tmp in [
            work_dir / "_audio_complete.mp3",
            work_dir / "_narration_full.mp3",
            work_dir / "_audio_final.mp3",
            work_dir / "_subtitles.srt",
            work_dir / "_subtitles.ass",
        ]:
            tmp.unlink(missing_ok=True)

    file_size = Path(output_path).stat().st_size / (1024 * 1024)
    total_dur = sum(s["duration"] for s in scenes) + intro_dur + outro_dur
    print(f"[FFmpeg] Done! {output_path} ({file_size:.1f} MB, ~{total_dur:.1f}s)")
    return output_path

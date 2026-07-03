from pathlib import Path
from typing import List, Tuple, Optional

TARGET_W, TARGET_H = 1080, 1920
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
FONT_SIZE = 48
SUBTITLE_BOTTOM_RATIO = 0.82


def compose_video(
    scenes: List[dict],
    output_path: str,
    fps: int = 30,
    fade_duration: float = 0.5,
    renderer: str = "ffmpeg",
    bgm_path: str = "",
    bgm_volume: float = 0.12,
    subtitle_style: str = "",
    intro_config: Optional[dict] = None,
    outro_config: Optional[dict] = None,
    topic: str = "",
) -> str:
    """
    Compose final video from scenes.
    renderer: "ffmpeg" (default, 10x faster) or "moviepy" (fallback)

    Each scene: {image_path, audio_path, duration, subtitles: [(text, start_ms, end_ms)]}

    Optional: bgm_path, bgm_volume, subtitle_style, intro_config, outro_config, topic
    (only used by ffmpeg renderer)
    """
    if renderer == "ffmpeg":
        from story_video.ffmpeg_composer import compose_video_ffmpeg
        return compose_video_ffmpeg(
            scenes, output_path, fps=fps, fade_duration=fade_duration,
            bgm_path=bgm_path, bgm_volume=bgm_volume,
            subtitle_style=subtitle_style,
            intro_config=intro_config, outro_config=outro_config,
            topic=topic,
        )
    else:
        return compose_video_moviepy(
            scenes, output_path, fps=fps, fade_duration=fade_duration
        )


# --- moviepy renderer (fallback, kept for compatibility) ---

import numpy as np
from PIL import Image, ImageFilter
from moviepy import (
    VideoClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
)
from moviepy.video.fx import FadeIn, FadeOut


def create_blurred_bg(image_path: str) -> np.ndarray:
    """Create a blurred, darkened background filling the 9:16 frame."""
    img = Image.open(image_path).convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = TARGET_W / TARGET_H

    if img_ratio > target_ratio:
        new_h = TARGET_H
        new_w = int(TARGET_H * img_ratio)
    else:
        new_w = TARGET_W
        new_h = int(TARGET_W / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - TARGET_W) // 2
    top = (new_h - TARGET_H) // 2
    img = img.crop((left, top, left + TARGET_W, top + TARGET_H))
    img = img.filter(ImageFilter.GaussianBlur(radius=25))
    dark = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
    img = Image.blend(img, dark, 0.4)
    return np.array(img)


def create_scene_clip(
    image_path: str,
    audio_path: Optional[str],
    duration: float,
    zoom_to: float = 1.08,
) -> VideoClip:
    """Create a video clip for one scene with Ken Burns (slow zoom) effect."""
    bg = create_blurred_bg(image_path)
    img = Image.open(image_path).convert("RGB")

    img_ratio = img.width / img.height
    base_h = int(TARGET_H * 0.72)
    base_w = int(base_h * img_ratio)
    if base_w > TARGET_W * 0.88:
        base_w = int(TARGET_W * 0.88)
        base_h = int(base_w / img_ratio)

    def make_frame(t):
        progress = (t / duration) if duration > 0 else 0
        zoom = 1.0 + (zoom_to - 1.0) * progress

        cur_w = max(1, int(base_w * zoom))
        cur_h = max(1, int(base_h * zoom))
        resized = img.resize((cur_w, cur_h), Image.LANCZOS)
        img_arr = np.array(resized)

        frame = bg.copy()
        x = (TARGET_W - cur_w) // 2
        y = (TARGET_H - cur_h) // 2

        fy_s, fy_e = max(0, y), min(TARGET_H, y + cur_h)
        fx_s, fx_e = max(0, x), min(TARGET_W, x + cur_w)
        sy_s = max(0, -y)
        sx_s = max(0, -x)
        sy_e = sy_s + (fy_e - fy_s)
        sx_e = sx_s + (fx_e - fx_s)

        frame[fy_s:fy_e, fx_s:fx_e] = img_arr[sy_s:sy_e, sx_s:sx_e]
        return frame

    clip = VideoClip(make_frame, duration=duration)

    if audio_path and Path(audio_path).exists():
        audio = AudioFileClip(audio_path)
        clip = clip.with_audio(audio)

    return clip


def create_subtitle_clip(
    text: str,
    start: float,
    end: float,
) -> Optional[TextClip]:
    """Create a subtitle TextClip positioned at bottom."""
    duration = end - start
    if duration <= 0 or not text.strip():
        return None

    txt = TextClip(
        font=FONT_PATH,
        text=text,
        font_size=FONT_SIZE,
        color="white",
        stroke_color="black",
        stroke_width=2,
        size=(int(TARGET_W * 0.85), None),
        method="caption",
        text_align="center",
        duration=duration,
    )
    txt = txt.with_position(("center", TARGET_H * SUBTITLE_BOTTOM_RATIO)).with_start(start)
    return txt


def compose_video_moviepy(
    scenes: List[dict],
    output_path: str,
    fps: int = 24,
    fade_duration: float = 0.5,
) -> str:
    """
    Compose final video using moviepy (slow, ~5fps rendering).
    Each scene: {image_path, audio_path, duration, subtitles: [(text, start_ms, end_ms)]}
    """
    scene_clips = []
    all_subtitles = []
    current_time = 0.0

    for i, scene in enumerate(scenes):
        print(f"[Video] Scene {i+1}/{len(scenes)}: image={Path(scene['image_path']).name}")

        clip = create_scene_clip(
            scene["image_path"],
            scene.get("audio_path"),
            scene["duration"],
        )

        if i > 0:
            clip = clip.with_effects([FadeIn(fade_duration)])
        if i < len(scenes) - 1:
            clip = clip.with_effects([FadeOut(fade_duration)])

        for text, start_ms, end_ms in scene.get("subtitles", []):
            abs_start = current_time + start_ms / 1000.0
            abs_end = current_time + end_ms / 1000.0
            all_subtitles.append((text, abs_start, abs_end))

        scene_clips.append(clip)
        current_time += scene["duration"]

    print(f"[Video] Concatenating {len(scene_clips)} scenes...")
    video = concatenate_videoclips(scene_clips, method="compose")

    sub_clips = []
    for text, start, end in all_subtitles:
        sc = create_subtitle_clip(text, start, end)
        if sc:
            sub_clips.append(sc)

    if sub_clips:
        print(f"[Video] Adding {len(sub_clips)} subtitles...")
        video = CompositeVideoClip([video] + sub_clips)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    print(f"[Video] Exporting {output_path} (1080x1920, {fps}fps)...")
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(Path(output_path).with_suffix(".aac")),
        remove_temp=True,
        bitrate="4M",
        logger="bar",
    )
    video.close()

    file_size = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"[Video] Done! {output_path} ({file_size:.1f} MB)")
    return output_path

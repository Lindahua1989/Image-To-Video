"""
Story Video Generator - 一句话生成历史人物故事短视频

Usage:
    python -m story_video.main --topic "苏轼的赤壁怀古"
    python -m story_video.main --topic "诸葛亮的空城计" --voice yunxi --output video.mp4

Pipeline:
    1. LLM 生成故事脚本 + 分镜描述
    2. 即梦 AI 生成分镜图片
    3. edge-tts 合成旁白语音 + 字幕
    4. moviepy 合成最终视频 (1080x1920 竖版)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from story_video.story_generator import generate_story, save_story
from story_video.tts_engine import generate_audio, generate_srt
from story_video.video_composer import compose_video

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"
CONFIG_PATH = PROJECT_DIR / "config" / "api-config.json"

IMAGE_MODEL = "doubao-seedream-5-0-260128"
IMAGE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def load_api_key() -> str:
    key = os.environ.get("VOLCENGINE_API_KEY", "")
    if key:
        return key
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("volcengine_api_key", "")
    return ""


def generate_scene_images(
    story: dict,
    api_key: str,
    work_dir: Path,
) -> list:
    """Generate images for each scene using doubao-seedream."""
    from openai import OpenAI

    client = OpenAI(base_url=IMAGE_BASE_URL, api_key=api_key)
    art_style = story.get("art_style", "")
    scenes = story.get("scenes", [])
    image_paths = []

    for i, scene in enumerate(scenes):
        prompt = scene.get("image_prompt", "")
        if art_style:
            prompt = f"{prompt}，{art_style}"

        print(f"\n[Image] Scene {i+1}/{len(scenes)}: {prompt[:60]}...")

        response = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size="2K",
            response_format="url",
            extra_body={
                "sequential_image_generation": "disabled",
                "stream": False,
                "watermark": False,
            },
        )

        item = response.data[0]
        if hasattr(item, "url") and item.url:
            import urllib.request
            img_path = work_dir / f"scene_{i+1:02d}.png"
            urllib.request.urlretrieve(item.url, str(img_path))
            image_paths.append(str(img_path))
            print(f"[Image] Saved: {img_path.name}")
        else:
            raise RuntimeError(f"No image data for scene {i+1}")

    return image_paths


def generate_scene_audios(
    story: dict,
    voice: str,
    work_dir: Path,
) -> list:
    """Generate TTS audio and subtitle timing for each scene."""
    scenes = story.get("scenes", [])
    results = []

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        audio_path = work_dir / f"audio_{i+1:02d}.mp3"
        srt_path = work_dir / f"subtitle_{i+1:02d}.srt"

        print(f"\n[TTS] Scene {i+1}/{len(scenes)}: {narration[:50]}...")

        tts_result = generate_audio(narration, str(audio_path), voice)
        subtitle_lines = generate_srt(tts_result["segments"], str(srt_path))

        results.append({
            "audio_path": str(audio_path),
            "duration": tts_result["duration"],
            "subtitles": subtitle_lines,
        })

    return results


def run_pipeline(
    topic: str,
    api_key: str,
    voice: str = "yunxi",
    output_path: str = "",
    num_scenes: int = 5,
    skip_story: bool = False,
    skip_images: bool = False,
    story_file: str = "",
) -> str:
    """Run the full story video generation pipeline."""
    if story_file:
        work_dir = Path(story_file).resolve().parent
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        work_dir = OUTPUT_DIR / f"story_{timestamp}"
        work_dir.mkdir(parents=True, exist_ok=True)

    if not output_path:
        output_path = str(work_dir / "video.mp4")

    # Step 1: Generate story script
    print("\n" + "=" * 60)
    print("STEP 1: Generate story script (LLM)")
    print("=" * 60)

    story_path = work_dir / "story.json"
    if skip_story or story_file:
        if not story_path.exists() and story_file:
            story_path = Path(story_file)
        if story_path.exists():
            with open(story_path, "r", encoding="utf-8") as f:
                story = json.load(f)
            print(f"[Story] Loaded existing: {story_path}")
        else:
            print(f"[Story] File not found: {story_path}, generating new...")
            story = generate_story(topic, api_key, num_scenes)
            save_story(story, str(work_dir / "story.json"))
    else:
        story = generate_story(topic, api_key, num_scenes)
        save_story(story, str(story_path))

    # Step 2: Generate scene images
    print("\n" + "=" * 60)
    print("STEP 2: Generate scene images (Jimeng AI)")
    print("=" * 60)

    if skip_images:
        image_paths = sorted(str(p) for p in work_dir.glob("scene_*.png"))
        if not image_paths:
            raise RuntimeError("--skip-images but no images found")
        print(f"[Image] Found {len(image_paths)} existing images")
    else:
        image_paths = generate_scene_images(story, api_key, work_dir)

    # Step 3: Generate TTS audio + subtitles
    print("\n" + "=" * 60)
    print("STEP 3: Generate narration audio (edge-tts)")
    print("=" * 60)

    audio_results = generate_scene_audios(story, voice, work_dir)

    # Step 4: Compose video
    print("\n" + "=" * 60)
    print("STEP 4: Compose video (moviepy)")
    print("=" * 60)

    scenes = story.get("scenes", [])
    video_scenes = []
    for i, scene in enumerate(scenes):
        audio_data = audio_results[i]
        buffer = 0.3
        video_scenes.append({
            "image_path": image_paths[i],
            "audio_path": audio_data["audio_path"],
            "duration": audio_data["duration"] + buffer,
            "subtitles": audio_data["subtitles"],
        })

    compose_video(video_scenes, output_path)

    print("\n" + "=" * 60)
    print(f"COMPLETE! Video: {output_path}")
    print(f"Work dir: {work_dir}")
    print("=" * 60)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="一句话生成历史人物故事短视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m story_video.main --topic "苏轼的赤壁怀古"
    python -m story_video.main --topic "诸葛亮的空城计" --voice yunjian
    python -m story_video.main --topic "岳飞的满江红" --num-scenes 4 --output my_video.mp4
        """,
    )
    parser.add_argument("--topic", "-t", required=True, help="故事主题，如：苏轼的赤壁怀古")
    parser.add_argument("--voice", "-v", default="yunxi",
                        choices=["yunxi", "yunjian", "xiaoxiao", "yunyang"],
                        help="配音语音 (default: yunxi)")
    parser.add_argument("--output", "-o", default="", help="输出视频路径")
    parser.add_argument("--num-scenes", "-n", type=int, default=5, help="场景数量 (default: 5)")
    parser.add_argument("--api-key", default="", help="Volcengine API Key")
    parser.add_argument("--skip-story", action="store_true", help="跳过故事生成，使用已有story.json")
    parser.add_argument("--skip-images", action="store_true", help="跳过图片生成，使用已有图片")
    parser.add_argument("--story-file", default="", help="指定story.json路径")
    args = parser.parse_args()

    api_key = args.api_key or load_api_key()
    if not api_key:
        print("[ERROR] No API key. Set $env:VOLCENGINE_API_KEY or configure config/api-config.json")
        sys.exit(1)

    run_pipeline(
        topic=args.topic,
        api_key=api_key,
        voice=args.voice,
        output_path=args.output,
        num_scenes=args.num_scenes,
        skip_story=args.skip_story,
        skip_images=args.skip_images,
        story_file=args.story_file,
    )


if __name__ == "__main__":
    main()

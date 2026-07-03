"""
Generate background music via MiniMax Music 2.6 API (free tier).

Uses the music-2.6-free model with is_instrumental=true for pure
instrumental BGM suitable for narration videos.

Daily free quota: 100 API calls per account.

Usage:
    python scripts/generate_bgm.py --prompt "中国风, 古筝, 笛子, 神话, 庄重, 叙事"
    python scripts/generate_bgm.py --prompt "..." --output templates/assets/bgm/mythology_bgm.mp3
    python scripts/generate_bgm.py --list         # list generated BGM files
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config" / "api-config.json"
BGM_DIR = PROJECT_DIR / "templates" / "assets" / "bgm"

API_URL = "https://api.minimaxi.com/v1/music_generation"


def load_api_key() -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("minimax_api_key", "")
        if key:
            return key
    print("[ERROR] No MiniMax API key. Add 'minimax_api_key' to config/api-config.json")
    sys.exit(1)


def generate_bgm(
    prompt: str,
    output_path: str,
    api_key: str,
    is_instrumental: bool = True,
    max_retries: int = 3,
) -> str:
    """Call MiniMax Music API and download the generated MP3."""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "music-2.6-free",
        "is_instrumental": is_instrumental,
        "prompt": prompt,
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3",
        },
        "output_format": "url",
    }

    print(f"[BGM] Generating music...")
    print(f"  Prompt: {prompt}")
    print(f"  Instrumental: {is_instrumental}")

    for attempt in range(1, max_retries + 1):
        print(f"  Calling API (attempt {attempt}/{max_retries}, may take 2-3 min)...")
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=300)
        result = resp.json()

        status = result.get("base_resp", {}).get("status_code", -1)
        if status == 0:
            audio_url = result["data"]["audio"]
            print(f"  Audio URL: {audio_url[:80]}...")

            # Download the MP3
            print(f"  Downloading...")
            audio_resp = requests.get(audio_url, timeout=120)
            audio_resp.raise_for_status()

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_resp.content)

            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
            return output_path
        else:
            msg = result.get("base_resp", {}).get("status_msg", str(result))
            print(f"  Attempt {attempt}/{max_retries} failed: {msg}")
            if attempt < max_retries:
                time.sleep(5 * attempt)

    print(f"[ERROR] BGM generation failed after {max_retries} attempts")
    sys.exit(1)


def list_bgm_files():
    """List all BGM files in the templates/assets/bgm directory."""
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BGM_DIR.glob("*.mp3"))
    if not files:
        print(f"No BGM files found in {BGM_DIR}")
        return
    print(f"BGM files in {BGM_DIR}:")
    for f in files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name:40s}  {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description="Generate BGM via MiniMax Music 2.6 API (free)")
    parser.add_argument("--prompt", "-p", default="",
                        help='Music style prompt, e.g. "中国风, 古筝, 笛子, 神话, 庄重, 叙事"')
    parser.add_argument("--output", "-o", default="",
                        help="Output MP3 path (default: templates/assets/bgm/bgm_<timestamp>.mp3)")
    parser.add_argument("--api-key", default="", help="MiniMax API Key")
    parser.add_argument("--list", action="store_true", help="List existing BGM files")
    parser.add_argument("--no-instrumental", action="store_true",
                        help="Generate with vocals (default: instrumental only)")
    args = parser.parse_args()

    if args.list:
        list_bgm_files()
        return

    if not args.prompt:
        parser.error("--prompt is required (or use --list)")

    api_key = args.api_key or load_api_key()

    if not args.output:
        BGM_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        args.output = str(BGM_DIR / f"bgm_{ts}.mp3")

    generate_bgm(
        prompt=args.prompt,
        output_path=args.output,
        api_key=api_key,
        is_instrumental=not args.no_instrumental,
    )


if __name__ == "__main__":
    main()

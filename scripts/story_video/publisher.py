"""
Multi-platform video publisher.

Supports Douyin, Xiaohongshu, Bilibili, Kuaishou, Tencent via social-auto-upload.
Account/cookie info is kept in config/publish-config.json (gitignored).

Usage:
    from story_video.publisher import Publisher
    pub = Publisher()
    pub.publish("output/story_xxx/video.mp4", title="...", tags=[...], platforms=["douyin","xiaohongshu"])
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
CONFIG_PATH = PROJECT_DIR / "config" / "publish-config.json"


def load_publish_config() -> dict:
    """Load publish config from JSON file or environment variable."""
    config_env = os.environ.get("PUBLISH_CONFIG", "")
    if config_env:
        return json.loads(config_env)

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    print("[Publisher] No publish-config.json found. See publish-config.example.json")
    print(f"[Publisher] Copy config/publish-config.example.json -> config/publish-config.json and edit")
    sys.exit(1)


def get_sau_cli(sau_path: str) -> str:
    """Get the sau CLI executable path from social-auto-upload installation."""
    sau_cli = Path(sau_path) / ".venv" / "Scripts" / "sau.exe"
    if sau_cli.exists():
        return str(sau_cli)

    sau_cli_alt = Path(sau_path) / ".venv" / "bin" / "sau"
    if sau_cli_alt.exists():
        return str(sau_cli_alt)

    print(f"[Publisher] sau CLI not found at {sau_cli}")
    print("[Publisher] Please install social-auto-upload first:")
    print(f"  git clone https://github.com/dreammis/social-auto-upload.git {sau_path}")
    print(f"  cd {sau_path}")
    print("  python -m venv .venv && .venv\\Scripts\\activate")
    print("  pip install -e .")
    print("  patchright install chromium")
    print("  Copy-Item conf.example.py conf.py")
    sys.exit(1)


class Publisher:
    """Multi-platform video publisher using social-auto-upload."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_publish_config()
        self.sau_path = self.config.get("social_auto_upload_path", "C:/tools/social-auto-upload")
        self.sau_cli = get_sau_cli(self.sau_path)
        self.account_name = self.config.get("account_name", "storybot")
        self.headless = self.config.get("headless", True)
        self.platforms = self.config.get("platforms", {})

    def _run_sau(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run sau CLI command."""
        cmd = [self.sau_cli] + args
        if self.headless and "--headless" not in args and "--headed" not in args:
            cmd.append("--headless")

        print(f"[Publisher] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def check_cookie(self, platform: str) -> bool:
        """Check if the saved cookie/session is still valid for a platform."""
        if platform not in self.platforms:
            print(f"[Publisher] Platform '{platform}' not configured")
            return False

        result = self._run_sau([platform, "check", "--account", self.account_name])
        is_valid = result.returncode == 0 and "valid" in result.stdout.lower()
        print(f"[Publisher] {platform} cookie: {'valid' if is_valid else 'invalid'}")
        return is_valid

    def check_all(self) -> dict:
        """Check cookies for all enabled platforms."""
        results = {}
        for platform, cfg in self.platforms.items():
            if cfg.get("enabled", False):
                results[platform] = self.check_cookie(platform)
        return results

    def login(self, platform: str, headed: bool = True):
        """
        Trigger QR code login for a platform.
        Requires human interaction (scan QR code with phone app).
        """
        if platform not in self.platforms:
            print(f"[Publisher] Platform '{platform}' not configured")
            return

        args = [platform, "login", "--account", self.account_name]
        if headed:
            args.append("--headed")

        print(f"[Publisher] Starting login for {platform}...")
        print("[Publisher] Please scan the QR code with your phone app")
        result = subprocess.run([self.sau_cli] + args)
        if result.returncode == 0:
            print(f"[Publisher] Login successful for {platform}")
        else:
            print(f"[Publisher] Login failed for {platform}")

    def publish(
        self,
        video_path: str,
        title: str,
        tags: List[str] = None,
        cover_path: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        schedule: Optional[str] = None,
        desc: str = "",
    ) -> dict:
        """
        Publish video to multiple platforms.

        Args:
            video_path: Path to the MP4 video file
            title: Video title (will be truncated per platform limits)
            tags: List of tag strings
            cover_path: Path to cover/thumbnail image
            platforms: List of platform names (default: all enabled)
            schedule: Scheduled publish time "YYYY-MM-DD HH:MM" (must be >2h future)
            desc: Video description

        Returns:
            dict of {platform: {"success": bool, "message": str}}
        """
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        if platforms is None:
            platforms = [p for p, c in self.platforms.items() if c.get("enabled", False)]

        if not platforms:
            print("[Publisher] No platforms to publish to")
            return {}

        tags_str = ",".join(tags or [])
        results = {}

        for i, platform in enumerate(platforms):
            if i > 0:
                interval = self.config.get("publish_interval_seconds", 300)
                print(f"[Publisher] Waiting {interval}s before next platform...")
                time.sleep(interval)

            results[platform] = self._publish_to_platform(
                platform, video_path, title, tags_str, cover_path, schedule, desc
            )

        print("\n[Publisher] Summary:")
        for platform, result in results.items():
            status = "OK" if result["success"] else "FAIL"
            print(f"  {platform}: {status} - {result['message']}")

        return results

    def _publish_to_platform(
        self,
        platform: str,
        video_path: str,
        title: str,
        tags_str: str,
        cover_path: Optional[str],
        schedule: Optional[str],
        desc: str,
    ) -> dict:
        """Publish to a single platform."""
        plat_config = self.platforms.get(platform, {})
        max_chars = plat_config.get("title_max_chars", 30)
        max_tags = plat_config.get("tags_max_count", 5)

        title = title[:max_chars]
        tags_limited = ",".join(tags_str.split(",")[:max_tags])

        args = [
            platform, "upload-video",
            "--account", self.account_name,
            "--file", video_path,
            "--title", title,
            "--tags", tags_limited,
        ]

        if desc:
            args.extend(["--desc", desc])

        if cover_path and Path(cover_path).exists():
            if platform == "douyin":
                args.extend(["--thumbnail-portrait", cover_path])
            else:
                args.extend(["--thumbnail", cover_path])

        if schedule:
            args.extend(["--schedule", schedule])

        if self.headless:
            args.append("--headless")

        print(f"\n[Publisher] Publishing to {platform}...")
        print(f"  Title: {title}")
        print(f"  Tags: {tags_limited}")
        print(f"  Cover: {cover_path or 'none'}")

        result = subprocess.run(
            [self.sau_cli] + args,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return {"success": True, "message": "Published successfully"}
        else:
            err = result.stderr[-500:] if result.stderr else result.stdout[-500:]
            return {"success": False, "message": err.strip()}

    def generate_cover(
        self,
        video_path: str,
        title: str,
        output_path: str,
    ) -> str:
        """Generate a cover image from the first frame of the video with title overlay."""
        import imageio_ffmpeg
        from PIL import Image, ImageDraw, ImageFont

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        raw_frame = Path(output_path).with_suffix(".raw.png")

        subprocess.run([
            ffmpeg, "-y", "-i", video_path,
            "-vframes", "1", "-q:v", "2",
            "-vf", f"scale={1080}:{1440}",
            str(raw_frame),
        ], capture_output=True)

        if not raw_frame.exists():
            print("[Publisher] Failed to extract cover frame")
            return ""

        img = Image.open(raw_frame).convert("RGB")
        draw = ImageDraw.Draw(img)

        overlay = Image.new("RGB", img.size, (0, 0, 0))
        img = Image.blend(img, overlay, 0.3)
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype(FONT_PATH, 64)
        except Exception:
            font_large = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), title, font=font_large)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img.width - text_w) // 2
        y = img.height - text_h - 150
        draw.text((x, y), title, fill="white", font=font_large, stroke_width=3, stroke_fill="black")

        img.save(output_path, "PNG")
        raw_frame.unlink(missing_ok=True)
        print(f"[Publisher] Cover generated: {output_path}")
        return output_path

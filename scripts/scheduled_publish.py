"""
Scheduled batch generate + publish for the mythology series.

Generates videos for pending characters, then publishes each to configured
platforms with a scheduled publish time (e.g. tomorrow 20:00).

Workflow:
  1. Pick next N pending characters (that have story.json pre-generated)
  2. For each: generate images → TTS → video → (optional BGM)
  3. Publish to platforms with --schedule for a future date
  4. Mark each as completed in progress tracker

Usage:
    # Dry run: show what would be done
    python scripts/scheduled_publish.py --count 7 --dry-run

    # Generate 7 videos, schedule publish for next 7 days at 20:00
    python scripts/scheduled_publish.py --count 7 --time 20:00

    # Generate 1 video, publish to douyin only, schedule for tomorrow 18:30
    python scripts/scheduled_publish.py --count 1 --time 18:30 --platforms douyin

    # Generate with auto BGM generation
    python scripts/scheduled_publish.py --count 3 --generate-bgm

    # Setup Windows Task Scheduler to run daily at 10:00
    python scripts/scheduled_publish.py --setup-task --task-time 10:00
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
TEMPLATES_DIR = PROJECT_DIR / "templates"
OUTPUT_DIR = PROJECT_DIR / "output"
CONFIG_DIR = PROJECT_DIR / "config"
CHARACTERS_PATH = TEMPLATES_DIR / "mythology_characters.json"
PROGRESS_PATH = TEMPLATES_DIR / "mythology_progress.json"
TEMPLATE_NAME = "mythology"


def load_progress() -> dict:
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress: dict):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_characters() -> dict:
    with open(CHARACTERS_PATH, "r", encoding="utf-8") as f:
        return {c["name"]: c for c in json.load(f)}


def load_api_config() -> dict:
    config_path = CONFIG_DIR / "api-config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_publish_config() -> dict:
    config_path = CONFIG_DIR / "publish-config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_pending_with_story(progress: dict) -> list:
    """Get pending characters that have story.json pre-generated."""
    chars = load_characters()
    ready = []
    for name in progress["pending"]:
        story_path = OUTPUT_DIR / f"story_{name}" / "story.json"
        if story_path.exists():
            ready.append(name)
        else:
            ready.append(None)  # placeholder, filtered later
    return [(n, chars.get(n, {})) for n in ready if n]


def generate_bgm_if_needed(dry_run: bool = False) -> bool:
    """Check if template BGM exists, generate via MiniMax if not."""
    bgm_path = TEMPLATES_DIR / "assets" / "bgm" / "mythology_bgm.mp3"
    if bgm_path.exists():
        return True

    if dry_run:
        print(f"  [DRY] Would generate BGM via MiniMax: {bgm_path}")
        return True

    config = load_api_config()
    minimax_key = config.get("minimax_api_key", "")
    if not minimax_key:
        print("  [WARN] No minimax_api_key, skipping BGM generation")
        return False

    print("  [BGM] Generating BGM via MiniMax...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "generate_bgm.py"),
         "--prompt", "中国古风管弦乐, 庄重而神秘, 笛子和古筝, 适合作为神话人物介绍视频的背景音乐",
         "--output", str(bgm_path),
         "--api-key", minimax_key],
        encoding="utf-8", errors="replace",
    )
    return result.returncode == 0


def generate_and_publish_one(
    name: str,
    char_info: dict,
    publish_date: datetime.date,
    publish_time: str,
    platforms: list,
    api_key: str,
    generate_bgm: bool,
    dry_run: bool = False,
) -> bool:
    """Generate one video and schedule publish. Returns True on success."""

    story_path = OUTPUT_DIR / f"story_{name}" / "story.json"
    schedule_str = f"{publish_date.isoformat()} {publish_time}"

    title = f"{name}：{char_info.get('title', '')}"
    brief = char_info.get("brief", "")

    print(f"\n{'=' * 60}")
    print(f"  Character: {name} - {title}")
    print(f"  Story: {story_path}")
    print(f"  Publish schedule: {schedule_str}")
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"{'=' * 60}")

    if dry_run:
        print("  [DRY] Would generate video + schedule publish")
        return True

    # Generate BGM if needed
    if generate_bgm:
        generate_bgm_if_needed()

    # Build command: generate video + publish with schedule
    cmd = [
        sys.executable, "-m", "story_video.main",
        "--topic", name,
        "--template", TEMPLATE_NAME,
        "--story-file", str(story_path),
        "--publish", ",".join(platforms),
        "--schedule", schedule_str,
    ]
    if api_key:
        cmd.extend(["--api-key", api_key])

    result = subprocess.run(
        cmd,
        cwd=str(SCRIPTS_DIR),
        encoding="utf-8",
        errors="replace",
    )

    return result.returncode == 0


def mark_completed(name: str, success: bool):
    progress = load_progress()
    if success:
        if name in progress["pending"]:
            progress["pending"].remove(name)
        if name not in progress["completed"]:
            progress["completed"].append(name)
        if name in progress.get("failed", []):
            progress["failed"].remove(name)
    else:
        if name not in progress.get("failed", []):
            progress.setdefault("failed", []).append(name)
    save_progress(progress)


def setup_windows_task(task_time: str = "10:00"):
    """Create a Windows Task Scheduler entry to run this script daily."""
    script_path = Path(__file__).resolve()
    python_exe = sys.executable

    # Build the scheduled task command
    task_name = "MythologyVideoDaily"
    cmd = f'{python_exe} "{script_path}" --count 1 --time 20:00 --generate-bgm'

    ps_script = f"""
$action = New-ScheduledTaskAction -Execute '{python_exe}' -Argument '"{script_path}" --count 1 --time 20:00 --generate-bgm'
$trigger = New-ScheduledTaskTrigger -Daily -At {task_time}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -Description 'Daily mythology video generation + scheduled publish' -Force
"""

    print(f"Setting up Windows Task Scheduler: '{task_name}'")
    print(f"  Runs daily at {task_time}")
    print(f"  Command: python {script_path} --count 1 --time 20:00 --generate-bgm")
    print()

    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    if result.returncode == 0:
        print(f"Task '{task_name}' created successfully!")
        print(f"  To view: Get-ScheduledTask -TaskName '{task_name}'")
        print(f"  To delete: Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false")
    else:
        print(f"Failed to create task: {result.stderr or result.stdout}")
        print("  Try running as Administrator")


def main():
    parser = argparse.ArgumentParser(
        description="定时批量生成+预约发布神话人物视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 预览（不执行）
    python scripts/scheduled_publish.py --count 7 --dry-run

    # 生成7个视频，预约未来7天每天20:00发布
    python scripts/scheduled_publish.py --count 7 --time 20:00

    # 仅发布到抖音
    python scripts/scheduled_publish.py --count 1 --time 18:30 --platforms douyin

    # 自动生成BGM
    python scripts/scheduled_publish.py --count 3 --generate-bgm

    # 设置Windows定时任务（每天10:00自动运行）
    python scripts/scheduled_publish.py --setup-task --task-time 10:00
        """,
    )
    parser.add_argument("--count", "-c", type=int, default=1, help="生成并预约N个视频")
    parser.add_argument("--time", "-t", default="20:00", help="每日发布时间 HH:MM (默认 20:00)")
    parser.add_argument("--start-date", "-d", default="", help="首个发布日期 YYYY-MM-DD (默认明天)")
    parser.add_argument("--platforms", "-p", default="douyin", help="发布平台逗号分隔 (默认 douyin)")
    parser.add_argument("--generate-bgm", action="store_true", help="BGM不存在时自动用MiniMax生成")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    parser.add_argument("--api-key", default="", help="Volcengine API Key")
    parser.add_argument("--setup-task", action="store_true", help="创建Windows定时任务")
    parser.add_argument("--task-time", default="10:00", help="Windows定时任务运行时间 (默认 10:00)")
    args = parser.parse_args()

    if args.setup_task:
        setup_windows_task(args.task_time)
        return

    # Parse publish config for default platforms
    pub_config = load_publish_config()
    configured_platforms = [p for p, c in pub_config.get("platforms", {}).items() if c.get("enabled", False)]
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    # Parse start date
    if args.start_date:
        start_date = datetime.date.fromisoformat(args.start_date)
    else:
        start_date = datetime.date.today() + datetime.timedelta(days=1)

    # Get API key
    config = load_api_config()
    api_key = args.api_key or config.get("volcengine_api_key", "")

    # Get pending characters with story.json
    progress = load_progress()
    ready = get_pending_with_story(progress)

    if not ready:
        print("No pending characters with pre-generated story.json found!")
        print("The AI assistant must generate story.json first.")
        print(f"\nPending characters (need story.json): {progress['pending'][:10]}")
        return

    count = min(args.count, len(ready))
    selected = ready[:count]

    print(f"\n{'=' * 60}")
    print(f"  Scheduled Batch Publish Plan")
    print(f"{'=' * 60}")
    print(f"  Videos to generate: {count}")
    print(f"  Publish time: {args.time} daily")
    print(f"  Start date: {start_date.isoformat()}")
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"  Generate BGM: {args.generate_bgm}")
    print(f"  Dry run: {args.dry_run}")
    print(f"\n  Schedule:")
    for i, (name, info) in enumerate(selected):
        date = start_date + datetime.timedelta(days=i)
        title = info.get("title", "")
        print(f"    {date.isoformat()} {args.time} | {name} - {title}")

    print(f"\n  Characters without story.json (skipped):")
    chars = load_characters()
    missing = [n for n in progress["pending"]
               if not (OUTPUT_DIR / f"story_{n}" / "story.json").exists()]
    if missing:
        for n in missing[:10]:
            print(f"    {n} - {chars.get(n, {}).get('title', '')}")
        if len(missing) > 10:
            print(f"    ... and {len(missing) - 10} more")
    else:
        print("    (none)")
    print(f"{'=' * 60}\n")

    if not args.dry_run:
        confirm = input(f"Generate {count} videos and schedule publish? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    success_count = 0
    fail_count = 0

    for i, (name, info) in enumerate(selected):
        publish_date = start_date + datetime.timedelta(days=i)

        ok = generate_and_publish_one(
            name=name,
            char_info=info,
            publish_date=publish_date,
            publish_time=args.time,
            platforms=platforms,
            api_key=api_key,
            generate_bgm=args.generate_bgm,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            continue

        mark_completed(name, ok)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    if not args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"  Batch complete: {success_count} success, {fail_count} failed")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

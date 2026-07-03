"""
Batch generate videos for all Chinese mythology characters.

Usage:
    # Generate next 5 pending characters
    python scripts/generate_mythology_batch.py --count 5

    # Generate specific character
    python scripts/generate_mythology_batch.py --name 盘古

    # Generate all pending (careful!)
    python scripts/generate_mythology_batch.py --all

    # List progress
    python scripts/generate_mythology_batch.py --status

    # Mark a character as manually completed
    python scripts/generate_mythology_batch.py --mark-done 盘古
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_DIR / "templates"
CHARACTERS_PATH = TEMPLATES_DIR / "mythology_characters.json"
PROGRESS_PATH = TEMPLATES_DIR / "mythology_progress.json"


def load_progress() -> dict:
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress: dict):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def show_status():
    p = load_progress()
    print(f"\n{'=' * 60}")
    print(f"  中国神话人物图谱 - 进度")
    print(f"{'=' * 60}")
    print(f"  总数: {p['total']}")
    print(f"  已完成: {len(p['completed'])}")
    print(f"  待制作: {len(p['pending'])}")
    print(f"  失败: {len(p['failed'])}")
    print(f"  完成率: {len(p['completed']) / p['total'] * 100:.1f}%")
    print(f"\n  分类明细:")
    for cat, names in p.get("categories", {}).items():
        done = [n for n in names if n in p["completed"]]
        total = len(names)
        status = " ".join(["✓" if n in p["completed"] else "·" for n in names])
        print(f"    {cat} ({len(done)}/{total})")
        print(f"      {status}")
        print(f"      {' '.join(names)}")
    print(f"\n  下一个待制作: {p['pending'][:5]}")
    print(f"{'=' * 60}\n")


def generate_one(name: str, brief: str, api_key: str = "") -> bool:
    """Generate one character video. Returns True on success."""
    cmd = [
        sys.executable, "-m", "story_video.main",
        "--topic", name,
        "--template", "mythology",
    ]
    if api_key:
        cmd.extend(["--api-key", api_key])

    print(f"\n{'=' * 60}")
    print(f"  Generating: {name} - {brief}")
    print(f"{'=' * 60}")

    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_DIR / "scripts"),
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="批量生成中国神话人物视频")
    parser.add_argument("--count", "-c", type=int, default=0, help="生成N个待制作人物")
    parser.add_argument("--all", action="store_true", help="生成所有待制作人物")
    parser.add_argument("--name", "-n", default="", help="生成指定人物")
    parser.add_argument("--status", "-s", action="store_true", help="查看进度")
    parser.add_argument("--mark-done", default="", help="标记人物为已完成")
    parser.add_argument("--api-key", default="", help="Volcengine API Key")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.mark_done:
        p = load_progress()
        if args.mark_done in p["pending"]:
            p["pending"].remove(args.mark_done)
            p["completed"].append(args.mark_done)
            save_progress(p)
            print(f"Marked '{args.mark_done}' as completed.")
        else:
            print(f"'{args.mark_done}' not in pending list.")
        return

    p = load_progress()
    chars = {}
    with open(CHARACTERS_PATH, "r", encoding="utf-8") as f:
        for c in json.load(f):
            chars[c["name"]] = c

    if args.name:
        names_to_gen = [args.name]
    elif args.all:
        names_to_gen = p["pending"]
    elif args.count > 0:
        names_to_gen = p["pending"][:args.count]
    else:
        parser.error("Use --count, --all, --name, --status, or --mark-done")

    if not names_to_gen:
        print("No pending characters to generate!")
        return

    print(f"\nWill generate {len(names_to_gen)} characters:")
    for i, name in enumerate(names_to_gen, 1):
        c = chars.get(name, {})
        print(f"  {i}. {name} - {c.get('title', '')}")

    confirm = input(f"\nGenerate {len(names_to_gen)} videos? (y/N): ")
    if confirm.lower() != "y":
        print("Cancelled.")
        return

    success = 0
    failed = 0
    for name in names_to_gen:
        c = chars.get(name, {})
        ok = generate_one(name, c.get("brief", ""), args.api_key)
        if ok:
            success += 1
            p = load_progress()
            if name in p["pending"]:
                p["pending"].remove(name)
                p["completed"].append(name)
                save_progress(p)
        else:
            failed += 1
            p = load_progress()
            if name not in p["failed"]:
                p["failed"].append(name)
                save_progress(p)

    print(f"\n{'=' * 60}")
    print(f"  Batch complete: {success} success, {failed} failed")
    print(f"{'=' * 60}")
    show_status()


if __name__ == "__main__":
    main()

"""
Template loader - loads JSON templates and provides config to the pipeline.

Templates live in templates/ directory. Each template defines:
  - story prompts (system + user)
  - defaults (voice, num_scenes, art_style)
  - bgm config
  - intro/outro config
  - subtitle styling
  - publish metadata
"""

import json
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_DIR / "templates"


def list_templates() -> list:
    """List all available template names."""
    if not TEMPLATES_DIR.exists():
        return []
    names = []
    for p in TEMPLATES_DIR.glob("*.json"):
        if p.name.endswith("_characters.json") or p.name.endswith("_progress.json"):
            continue
        names.append(p.stem)
    return sorted(names)


def load_template(name: str = "default") -> dict:
    """Load a template by name. Returns template dict or raises FileNotFoundError."""
    if not name or name == "default":
        path = TEMPLATES_DIR / "default.json"
    else:
        path = TEMPLATES_DIR / f"{name}.json"

    if not path.exists():
        available = list_templates()
        raise FileNotFoundError(
            f"Template '{name}' not found at {path}\n"
            f"Available templates: {available}"
        )

    with open(path, "r", encoding="utf-8") as f:
        tpl = json.load(f)

    print(f"[Template] Loaded: {tpl.get('name', name)} ({path.name})")
    return tpl


def get_story_prompts(tpl: dict) -> tuple:
    """Extract (system_prompt, user_prompt_template) from template."""
    story = tpl.get("story", {})
    sys_prompt = story.get("system_prompt", "")
    usr_template = story.get("user_prompt_template", "")
    return sys_prompt, usr_template


def get_defaults(tpl: dict) -> dict:
    """Get default settings from template."""
    return tpl.get("defaults", {})


def get_bgm_config(tpl: dict) -> dict:
    """Get BGM config from template."""
    return tpl.get("bgm", {"enabled": False})


def get_intro_config(tpl: dict) -> dict:
    """Get intro config from template."""
    return tpl.get("intro", {"enabled": False})


def get_outro_config(tpl: dict) -> dict:
    """Get outro config from template."""
    return tpl.get("outro", {"enabled": False})


def get_subtitle_style(tpl: dict) -> dict:
    """Get subtitle style dict for ASS generation."""
    style = tpl.get("subtitle_style", {})
    if not style:
        return {}
    return style


def get_publish_config(tpl: dict) -> dict:
    """Get publish metadata from template."""
    return tpl.get("publish", {})


def format_prompt(template: str, topic: str, num_scenes: int) -> str:
    """Format a prompt template with topic and num_scenes."""
    return template.format(topic=topic, num_scenes=num_scenes)


if __name__ == "__main__":
    print("Available templates:")
    for name in list_templates():
        tpl = load_template(name)
        print(f"  {name}: {tpl.get('name', '')} - {tpl.get('description', '')[:60]}")

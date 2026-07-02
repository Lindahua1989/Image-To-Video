import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DEFAULT_CONFIG = PROJECT_DIR / "config" / "api-config.json"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"

VOLCENGINE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
VOLCENGINE_DEFAULT_MODEL = "doubao-seedream-5-0-260128"

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-image-1"

BFL_DEFAULT_MODEL = "flux-pro-1.1"

SIZE_MAP_VOLCENGINE = {
    "1024x1024": "1K",
    "1536x1536": "1.5K",
    "2048x2048": "2K",
    "4096x4096": "4K",
    "1024x576": "1K",
    "576x1024": "1K",
    "2048x1152": "2K",
    "1152x2048": "2K",
    "4096x2304": "4K",
    "2304x4096": "4K",
}


def load_api_key(provider: str, config_file: str = "") -> str:
    env_map = {
        "volcengine": "VOLCENGINE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "bfl": "BFL_API_KEY",
    }
    key = os.environ.get(env_map.get(provider, ""), "")
    if key:
        return key

    config_path = Path(config_file) if config_file else DEFAULT_CONFIG
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        key_field = f"{provider}_api_key"
        return config.get(key_field, "")
    return ""


def get_client(provider: str, api_key: str) -> OpenAI:
    if provider == "volcengine":
        return OpenAI(base_url=VOLCENGINE_BASE_URL, api_key=api_key)
    elif provider == "openai":
        return OpenAI(base_url=OPENAI_BASE_URL, api_key=api_key)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def generate_volcengine(
    client: OpenAI,
    prompt: str,
    model: str,
    size: str,
    output_path: str,
):
    if not model:
        model = VOLCENGINE_DEFAULT_MODEL

    volc_size = SIZE_MAP_VOLCENGINE.get(size, "2K")
    if size and size.endswith("K"):
        volc_size = size

    print(f"[INFO] Provider: Volcengine (Jimeng) | Model: {model} | Size: {volc_size}")
    trunc = prompt[:120] + "..." if len(prompt) > 120 else prompt
    print(f"[INFO] Prompt: {trunc}")

    response = client.images.generate(
        model=model,
        prompt=prompt,
        size=volc_size,
        response_format="url",
        extra_body={
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        },
    )

    return _download_or_decode(response, output_path)


def generate_openai(
    client: OpenAI,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    output_path: str,
):
    if not model:
        model = OPENAI_DEFAULT_MODEL

    print(f"[INFO] Provider: OpenAI | Model: {model} | Size: {size}")
    trunc = prompt[:120] + "..." if len(prompt) > 120 else prompt
    print(f"[INFO] Prompt: {trunc}")

    kwargs = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }
    if model == "gpt-image-1":
        kwargs["output_format"] = "png"
    else:
        kwargs["quality"] = quality
        kwargs["response_format"] = "b64_json"

    response = client.images.generate(**kwargs)
    return _download_or_decode(response, output_path)


def _download_or_decode(response, output_path: str) -> bool:
    item = response.data[0]
    if hasattr(item, "url") and item.url:
        print("[INFO] Image ready, downloading...")
        urllib.request.urlretrieve(item.url, output_path)
        return True
    elif hasattr(item, "b64_json") and item.b64_json:
        import base64
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(item.b64_json))
        return True
    else:
        print("[ERROR] No image data in response")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate images via OpenAI-compatible API")
    parser.add_argument("--prompt", "-p", required=True, help="Image generation prompt")
    parser.add_argument("--output", "-o", default="", help="Output file path")
    parser.add_argument("--provider", default="volcengine", choices=["volcengine", "openai"])
    parser.add_argument("--model", "-m", default="", help="Model name")
    parser.add_argument("--size", "-s", default="2K", help="Image size (e.g. 2K, 1024x1024)")
    parser.add_argument("--quality", "-q", default="high", help="Image quality")
    parser.add_argument("--config", default="", help="Config file path")
    args = parser.parse_args()

    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.output:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        args.output = str(output_dir / f"img_{timestamp}.png")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    api_key = load_api_key(args.provider, args.config)
    if not api_key:
        env_var = {
            "volcengine": "VOLCENGINE_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(args.provider, "")
        print(f"[ERROR] No API key found for provider '{args.provider}'.")
        print(f"Set ${env_var} or configure in {DEFAULT_CONFIG}")
        sys.exit(1)

    client = get_client(args.provider, api_key)

    try:
        if args.provider == "volcengine":
            success = generate_volcengine(client, args.prompt, args.model, args.size, args.output)
        else:
            success = generate_openai(client, args.prompt, args.model, args.size, args.quality, args.output)

        if success:
            file_size = Path(args.output).stat().st_size / 1024
            print(f"[OK] Image saved: {args.output} ({file_size:.1f} KB)")
        else:
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

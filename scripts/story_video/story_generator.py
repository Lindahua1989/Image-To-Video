import json
import os
from pathlib import Path
from openai import OpenAI

VOLCENGINE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
STORY_MODEL = "doubao-seed-2-0-pro-260215"

SYSTEM_PROMPT = """你是一位专业的短视频文案编剧，擅长将历史人物和事件改编成引人入胜的抖音短视频故事。

用户会给你一个主题（如"苏轼的赤壁怀古"），你需要生成一个结构化的JSON故事脚本。

要求：
1. 生成4-6个场景（scenes）
2. 每个场景包含：
   - narration: 旁白文案（2-3句话，口语化，适合朗读，有感染力）
   - image_prompt: 图片生成提示词（中文，详细描述画面内容、风格、光线、氛围）
3. 旁白要符合历史事实，但用讲故事的方式表达，有悬念和情感
4. 图片提示词要具体描述场景，包含人物、环境、服饰、光线、色调、艺术风格
5. 图片艺术风格保持一致（如统一用水墨画风格、或统一用写实油画风格）
6. 总时长控制在30-60秒（按每句旁白3-4秒估算）

只返回JSON，不要其他文字。格式如下：
{
  "title": "故事标题",
  "art_style": "统一的艺术风格描述",
  "scenes": [
    {
      "narration": "旁白文字...",
      "image_prompt": "图片提示词..."
    }
  ]
}"""


def get_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=VOLCENGINE_BASE_URL, api_key=api_key)


def generate_story(topic: str, api_key: str, num_scenes: int = 5) -> dict:
    client = get_client(api_key)

    user_prompt = f"""主题：{topic}

请生成{num_scenes}个场景的历史故事短视频脚本。

注意：
- 旁白用中文，口语化，适合AI语音朗读
- 图片提示词用中文，描述要具体，包含人物外貌、服饰、场景环境、光线、色调
- 艺术风格要统一，建议用中国传统水墨画或工笔画风格（历史题材）
- 第一个场景要引人入胜，最后一个场景要有情感升华或哲理总结"""

    response = client.chat.completions.create(
        model=STORY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        extra_body={"response_format": {"type": "json_object"}},
    )

    content = response.choices[0].message.content
    story = json.loads(content)

    print(f"[Story] 标题: {story.get('title', 'N/A')}")
    print(f"[Story] 艺术风格: {story.get('art_style', 'N/A')}")
    print(f"[Story] 场景数: {len(story.get('scenes', []))}")
    for i, scene in enumerate(story.get("scenes", [])):
        narration = scene.get("narration", "")
        print(f"[Story] 场景{i+1} 旁白: {narration[:50]}...")

    return story


def save_story(story: dict, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)
    print(f"[Story] 脚本已保存: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", "-t", required=True, help="故事主题")
    parser.add_argument("--output", "-o", default="", help="输出JSON路径")
    parser.add_argument("--api-key", default="", help="Volcengine API Key")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("VOLCENGINE_API_KEY", "")
    if not api_key:
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "api-config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                api_key = json.load(f).get("volcengine_api_key", "")

    if not api_key:
        print("[ERROR] No API key found")
        exit(1)

    if not args.output:
        output_dir = Path(__file__).resolve().parent.parent.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / "story.json")

    story = generate_story(args.topic, api_key)
    save_story(story, args.output)

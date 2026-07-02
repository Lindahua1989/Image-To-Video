# AI 图片生成 & 历史故事短视频工作流

基于火山引擎方舟（即梦AI）+ edge-tts + moviepy 的自动化内容生成工具。

## 功能

### 1. 单张图片生成
使用即梦AI (doubao-seedream-5.0) 通过 OpenAI SDK 生成高质量图片。

```bash
python scripts/generate_image.py --prompt "你的提示词" --provider volcengine --size 2K
```

### 2. 历史故事短视频生成
一句话生成抖音竖版短视频（1080x1920），包含旁白语音 + 字幕 + 图片动画。

```bash
python -m story_video.main --story-file story.json --voice yunjian
```

工作流：
1. **文案 + 分镜**：由 AI 助手直接生成 story.json（旁白 + 图片提示词）
2. **图片生成**：即梦AI doubao-seedream-5-0 生成场景图
3. **语音合成**：edge-tts 生成中文旁白 + 字幕时间轴
4. **视频合成**：moviepy 合成竖版视频（Ken Burns缩放 + 模糊背景 + 字幕 + 淡入淡出）

## 安装

```bash
pip install openai edge-tts moviepy Pillow
```

## 配置

1. 注册火山引擎账号 https://console.volcengine.com/ark
2. 开通模型：`doubao-seedream-5-0-260128`（图片生成）
3. 创建 API Key
4. 复制 `config/api-config.example.json` 为 `config/api-config.json`，填入 API Key

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 图片生成 | 即梦AI 5.0 (doubao-seedream) | 火山引擎方舟API，OpenAI SDK调用 |
| 语音合成 | edge-tts | 微软TTS，免费，6种中文语音 |
| 视频合成 | moviepy + FFmpeg | Ken Burns效果，模糊背景，字幕 |
| API调用 | OpenAI Python SDK | 兼容火山方舟API格式 |

## 项目结构

```
├── config/
│   ├── api-config.example.json    # 配置模板
│   └── api-config.json            # 实际配置（gitignore）
├── scripts/
│   ├── generate_image.py          # 单张图片生成
│   └── story_video/
│       ├── story_generator.py     # 故事脚本生成（可选，也可AI直接生成）
│       ├── tts_engine.py          # edge-tts 语音合成 + 字幕
│       ├── video_composer.py      # moviepy 视频合成
│       └── main.py                # 主编排器
├── output/                        # 生成结果（gitignore）
└── .opencode/
    └── skills/generate-image/     # opencode 图片生成skill
```

# AI 图片生成 & 历史故事短视频工作流

基于火山引擎方舟（即梦AI）+ edge-tts + FFmpeg + social-auto-upload 的自动化内容生成与发布工具。

## 功能

### 1. 单张图片生成
使用即梦AI (doubao-seedream-5.0) 通过 OpenAI SDK 生成高质量图片。

```bash
python scripts/generate_image.py --prompt "你的提示词" --provider volcengine --size 2K
```

### 2. 历史故事短视频生成
一句话生成抖音竖版短视频（1080x1920），包含旁白语音 + 字幕 + 图片动画。

```bash
# 生成视频
python -m story_video.main --topic "苏轼的赤壁怀古"

# 生成并直接发布到抖音+小红书
python -m story_video.main --topic "曹操" --publish douyin,xiaohongshu

# 使用已有story.json发布已有视频
python -m story_video.main --topic "test" --publish-only --story-file output/story_xxx/story.json --publish douyin
```

工作流：
1. **文案 + 分镜**：由 AI 助手直接生成 story.json（旁白 + 图片提示词）
2. **图片生成**：即梦AI doubao-seedream-5-0 生成场景图
3. **语音合成**：edge-tts 生成中文旁白 + 字幕时间轴
4. **视频合成**：FFmpeg 合成竖版视频（Ken Burns缩放 + 模糊背景 + 字幕 + 交叉转场）
5. **自动发布**：social-auto-upload 自动上传到抖音/小红书/B站等平台

## 安装

### 基础安装

```bash
pip install openai edge-tts moviepy Pillow imageio-ffmpeg
```

### 自动发布功能安装（可选）

```bash
# 克隆 social-auto-upload
git clone https://github.com/dreammis/social-auto-upload.git C:\tools\social-auto-upload
cd C:\tools\social-auto-upload

# 创建虚拟环境并安装
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\patchright.exe install chromium

# 创建配置文件
Copy-Item conf.example.py conf.py
```

## 配置

### 1. API 配置
1. 注册火山引擎账号 https://console.volcengine.com/ark
2. 开通模型：`doubao-seedream-5-0-260128`（图片生成）
3. 创建 API Key
4. 复制 `config/api-config.example.json` 为 `config/api-config.json`，填入 API Key

### 2. 发布配置
1. 复制 `config/publish-config.example.json` 为 `config/publish-config.json`
2. 配置 social-auto-upload 路径和账号名
3. 首次使用需扫码登录：
```bash
python -m story_video.main --topic "test" --login douyin
python -m story_video.main --topic "test" --login xiaohongshu
```

**注意**：`config/publish-config.json` 和所有 cookie 文件已在 `.gitignore` 中排除，不会提交到 GitHub。

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 图片生成 | 即梦AI 5.0 (doubao-seedream) | 火山引擎方舟API，OpenAI SDK调用 |
| 语音合成 | edge-tts | 微软TTS，免费，6种中文语音 |
| 视频合成 | FFmpeg (imageio_ffmpeg) | zoompan Ken Burns效果，xfade转场，字幕叠加 |
| 自动发布 | social-auto-upload | Playwright浏览器自动化，支持抖音/小红书/B站等 |
| API调用 | OpenAI Python SDK | 兼容火山方舟API格式 |

## 性能对比

| 渲染器 | 3场景视频(35秒) | 文件大小 | 说明 |
|--------|---------------|---------|------|
| moviepy | ~3分钟 | 18.9MB | 逐帧PIL渲染，慢但功能全 |
| **FFmpeg** | **~32秒** | **6.9MB** | zoompan滤镜，10倍加速，默认使用 |

## CLI 参数

```
--topic, -t          故事主题（必填）
--voice, -v          配音语音: yunxi/yunjian/xiaoxiao/yunyang
--output, -o         输出视频路径
--num-scenes, -n     场景数量 (default: 5)
--renderer           渲染器: ffmpeg(默认) 或 moviepy
--publish            发布平台: douyin,xiaohongshu
--publish-only       仅发布已有视频
--schedule           定时发布: 2026-07-04 20:00
--login              扫码登录平台: douyin 或 xiaohongshu
--skip-story         跳过故事生成
--skip-images        跳过图片生成
--story-file         指定story.json路径
```

## 项目结构

```
├── config/
│   ├── api-config.example.json       # API配置模板
│   ├── api-config.json               # 实际API配置（gitignore）
│   ├── publish-config.example.json   # 发布配置模板
│   └── publish-config.json           # 实际发布配置（gitignore）
├── scripts/
│   ├── generate_image.py             # 单张图片生成
│   └── story_video/
│       ├── story_generator.py        # 故事脚本生成
│       ├── tts_engine.py             # edge-tts 语音合成 + 字幕
│       ├── ffmpeg_composer.py        # FFmpeg 视频合成（默认，10x加速）
│       ├── video_composer.py         # 视频合成入口（ffmpeg/moviepy切换）
│       ├── publisher.py              # 多平台自动发布模块
│       └── main.py                   # 主编排器
├── output/                           # 生成结果（gitignore）
└── .opencode/
    └── skills/generate-image/        # opencode 图片生成skill
```

## 支持的发布平台

| 平台 | 状态 | 说明 |
|------|------|------|
| 抖音 | ✅ | 浏览器自动化上传 |
| 小红书 | ✅ | 浏览器自动化上传 |
| B站 | ✅ | biliup CLI工具 |
| 快手 | ✅ | 浏览器自动化上传 |
| 视频号 | ✅ | 浏览器自动化上传 |
| TikTok | ✅ | 浏览器自动化上传 |
| YouTube | ✅ | 浏览器自动化上传 |

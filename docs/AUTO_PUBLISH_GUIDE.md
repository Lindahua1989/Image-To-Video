# 自动发布指南

将生成的短视频自动发布到抖音、小红书、B站等平台。

## 原理

使用 [social-auto-upload](https://github.com/dreammis/social-auto-upload) 开源项目（13K+ stars），
通过 Playwright 浏览器自动化模拟人工上传，支持 QR 码登录和 cookie 持久化。

## 一次性安装（约10分钟）

### 1. 克隆并安装 social-auto-upload

```powershell
git clone https://github.com/dreammis/social-auto-upload.git C:\tools\social-auto-upload
cd C:\tools\social-auto-upload
```

### 2. 修复 Python 3.13 兼容性

social-auto-upload 官方要求 Python <3.13，我们需要做以下修改：

**2a. 修改版本限制**
```powershell
# 编辑 C:\tools\social-auto-upload\pyproject.toml
# 将 requires-python = ">=3.10,<3.13" 改为 requires-python = ">=3.10"
```

**2b. 创建虚拟环境并安装**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install charset-normalizer
.\.venv\Scripts\python.exe -m pip install -e .
```

**2c. 降级 greenlet（Python 3.13 兼容）**
```powershell
.\.venv\Scripts\python.exe -m pip install "greenlet==3.1.1"
```

**2d. 安装 Chromium 浏览器**
```powershell
.\.venv\Scripts\patchright.exe install chromium
```

**2e. 创建配置文件**
```powershell
Copy-Item conf.example.py conf.py
```

**2f. 修改 conf.py（启用有头模式，QR码登录需要）**
```powershell
# 编辑 C:\tools\social-auto-upload\conf.py
# 将 LOCAL_CHROME_HEADLESS = True 改为 LOCAL_CHROME_HEADLESS = False
```

**2g. 修复 cookie_auth 浏览器启动（避免找不到系统Chrome）**
```powershell
# 编辑 C:\tools\social-auto-upload\uploader\douyin_uploader\main.py
# 第56行：将 "channel": "chrome" 改为 "channel": "chromium"
```

**2h. 修复 _wait_for_douyin_login 变量未定义 bug**
```powershell
# 编辑 C:\tools\social-auto-upload\uploader\douyin_uploader\main.py
# 在 _wait_for_douyin_login 函数开头添加：
#   original_url = page.url
#   saw_2fa = False
# 将 for _ in range 改为 for i in range
```

### 3. 配置发布参数

```powershell
# 在项目目录下
Copy-Item config\publish-config.example.json config\publish-config.json
```

编辑 `config/publish-config.json`，确认 `social_auto_upload_path` 指向正确路径。

### 4. 首次登录（扫码，每个平台一次）

```powershell
# 设置环境变量
$env:PYTHONPATH = "D:\00 lindahua\00 project\image\scripts"

# 登录抖音（会弹出浏览器，用手机抖音App扫码）
python -m story_video.main --topic "test" --login douyin

# 登录小红书（用手机小红书App扫码）
python -m story_video.main --topic "test" --login xiaohongshu
```

登录后 cookie 自动保存到 `C:\tools\social-auto-upload\cookies\douyin_storybot.json`，
之后发布无需再登录，cookie 会自动刷新。

## 日常使用

### 生成视频并发布

```powershell
$env:PYTHONPATH = "D:\00 lindahua\00 project\image\scripts"

# 生成并发布到抖音
python -m story_video.main --topic "曹操" --publish douyin

# 生成并发布到抖音+小红书
python -m story_video.main --topic "苏轼的赤壁怀古" --publish douyin,xiaohongshu

# 定时发布（需提前2小时以上）
python -m story_video.main --topic "诸葛亮" --publish douyin --schedule "2026-07-04 20:00"
```

### 仅发布已有视频

```powershell
python -m story_video.main --topic "test" --publish-only --story-file output\story_caocao\story.json --publish douyin
```

### 检查登录状态

```powershell
# 直接用 sau CLI
C:\tools\social-auto-upload\.venv\Scripts\sau.exe douyin check --account storybot
C:\tools\social-auto-upload\.venv\Scripts\sau.exe xiaohongshu check --account storybot
```

## 注意事项

| 事项 | 说明 |
|------|------|
| **封面图** | 当前不传自定义封面，让平台自动从视频截取。自定义封面上传在抖音会卡弹窗 |
| **标题长度** | 抖音≤30字，小红书≤20字，自动截断 |
| **标签数量** | 抖音≤5个，小红书≤10个，自动截断 |
| **发布间隔** | 多平台发布时默认间隔300秒，避免风控 |
| **cookie过期** | 发布时自动检测，失效会提示重新扫码 |
| **反爬检测** | 抖音 cookie check 必须用有头模式（headed），无头模式会被误判失效 |
| **账号安全** | publish-config.json 和所有 cookie 文件已在 .gitignore 中排除 |

## 支持的平台

| 平台 | 登录 | 视频上传 | 图文上传 | 定时发布 |
|------|------|---------|---------|---------|
| 抖音 | QR码 | ✅ 已验证 | ✅ | ✅ |
| 小红书 | QR码 | ✅ | ✅ | ✅ |
| B站 | biliup | ✅ | - | ✅ |
| 快手 | QR码 | ✅ | ✅ | ✅ |
| 视频号 | QR码 | ✅ | ✅ | ✅ |
| TikTok | QR码 | ✅ | - | - |
| YouTube | QR码 | ✅ | - | ✅ |

## 故障排除

### Q: 登录后发布失败，提示 cookie 失效
```powershell
# 重新检查 cookie
C:\tools\social-auto-upload\.venv\Scripts\sau.exe douyin check --account storybot
# 如果显示 invalid，重新登录
python -m story_video.main --topic "test" --login douyin
```

### Q: 发布时浏览器卡住
- 确认 `conf.py` 中 `LOCAL_CHROME_HEADLESS = False`
- 确认 `cookie_auth` 函数中 `channel` 为 `"chromium"` 而非 `"chrome"`
- 尝试不传封面图（`cover_path=None`）

### Q: greenlet DLL 加载失败
```powershell
C:\tools\social-auto-upload\.venv\Scripts\python.exe -m pip install "greenlet==3.1.1"
```

### Q: patchright chromium 找不到
```powershell
C:\tools\social-auto-upload\.venv\Scripts\patchright.exe install chromium
```

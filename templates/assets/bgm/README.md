# BGM 背景音乐文件

将背景音乐 MP3 文件放在此目录下。

## 命名规则

- `mythology_bgm.mp3` - 中国神话模板的BGM（推荐：古风、大气、神秘感）
- 其他模板按 `<template_name>_bgm.mp3` 命名

## 获取方式

1. 免费无版权音乐网站：
   - https://www.bensound.com
   - https://freemusicarchive.org
   - https://www.youtube.com/audiolibrary

2. 推荐风格：
   - 神话系列：古风、大气、有鼓点和笛声
   - 历史系列：沉稳、古风、水墨感
   - 科普系列：轻快、现代、电子

3. 音频格式：MP3，时长建议 3-5 分钟（会自动循环）

## 配置

在模板 JSON 中设置：
```json
"bgm": {
  "enabled": true,
  "file": "templates/assets/bgm/mythology_bgm.mp3",
  "volume": 0.12
}
```

volume 建议 0.08-0.15，太高会盖过旁白。

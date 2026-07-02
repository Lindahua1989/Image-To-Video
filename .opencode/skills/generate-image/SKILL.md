---
name: generate-image
description: Use when the user asks to generate, create, or produce any image, picture, illustration, photo, artwork, wallpaper, poster, or visual content. Handles text-to-image generation with automatic prompt enhancement for maximum quality. Also use when the user wants to batch generate images or set up image generation.
---

# Image Generation Skill

You have access to a high-quality image generation pipeline. Your job is to
**fully automate** the process: the user describes what they want in natural
language, and you handle everything — prompt engineering, API calls, file
management — without requiring the user to provide technical details.

## Setup Check

Before first use, verify the API key exists. Run:

```bash
python "D:\00 lindahua\00 project\image\scripts\generate_image.py" --prompt "test"
```

If it reports "No API key found", tell the user they need an API key and guide them:

> You need an API key to generate images. Choose one:
>
> **Option A - Volcengine / Jimeng (Recommended, 即梦AI 5.0, domestic China):**
> 1. Go to https://console.volcengine.com/ark
> 2. Register and complete real-name authentication
> 3. Enable the image generation model `doubao-seedream-5-0-260128` in Model Plaza
> 4. Create an API Key in "API Key Management" (format: `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
> 5. Tell me the key and I'll save it securely
>
> **Option B - OpenAI (gpt-image-1, requires foreign payment method):**
> 1. Go to https://platform.openai.com/api-keys
> 2. Create a new key
> 3. Tell me the key and I'll save it securely

When the user provides a key, save it by editing the config file:

```bash
python -c "import json; json.dump({'volcengine_api_key':'THE_KEY_HERE','openai_api_key':'','bfl_api_key':''}, open('D:/00 lindahua/00 project/image/config/api-config.json','w'), indent=2, ensure_ascii=False)"
```

## Prompt Enhancement

**This is the most critical step.** Never pass the user's raw prompt directly.
Transform it into a high-quality generation prompt following these rules:

### Enhancement Framework

1. **Subject Clarity**: Make the main subject explicit and detailed
2. **Style Specification**: Add art style (photorealistic, digital art, oil painting, watercolor, anime, 3D render, etc.)
3. **Lighting**: Add professional lighting description (golden hour, studio lighting, volumetric light, rim lighting, etc.)
4. **Composition**: Specify camera angle, framing, depth of field
5. **Quality Modifiers**: Add technical quality terms
6. **Color Palette**: Describe the mood through color
7. **Negative Context**: Note what to avoid (if the model supports it)

### Quality Modifier Library

**For Photorealistic images:**
```
photorealistic, ultra-detailed, 8K resolution, professional photography, sharp focus, natural lighting, high dynamic range, shot on [camera], f/[aperture], [focal length]mm lens
```

**For Digital Art / Illustration:**
```
masterpiece, best quality, highly detailed, sharp lines, vibrant colors, professional digital art, artstation trending, concept art
```

**For Creative / Artistic:**
```
intricate details, rich color palette, dramatic lighting, atmospheric, cinematic composition, award-winning, gallery quality
```

### Example Enhancements

User says: "a cat"
Enhanced: "A majestic Maine Coon cat with amber eyes sitting on a velvet cushion, warm golden hour sunlight streaming through a window, soft bokeh background, photorealistic, ultra-detailed fur texture, professional pet photography, 85mm lens, shallow depth of field, 8K resolution"

User says: "a cyberpunk city"
Enhanced: "A sprawling cyberpunk metropolis at night, towering neon-lit skyscrapers with holographic advertisements, flying vehicles between buildings, rain-slicked streets reflecting colorful lights, volumetric fog, cinematic wide-angle composition, blade runner aesthetic, ultra-detailed, dramatic lighting with cyan and magenta color palette, 8K concept art"

User says: "logo for a coffee shop"
Enhanced: "Minimalist modern logo design for a specialty coffee shop, clean vector style, warm brown and cream color palette, coffee bean motif integrated with steam swirl, professional branding, white background, high contrast, scalable design"

## Generation Workflow

### Step 1: Determine Parameters

Based on the user's request, decide:
- **Provider**: `volcengine` (default, 即梦AI, best for domestic China) or `openai` (best all-around) or `bfl` (best photorealism)
- **Model**: See model table below
- **Size**: Match the user's needs (default `1024x1024`)
- **Quality**: `high` for best results

### Model Selection Guide

| Provider | Model | Best For | Notes |
|----------|-------|----------|-------|
| volcengine | doubao-seedream-5-0-260128 | All-purpose, Chinese-friendly, 2K | 即梦AI 5.0, default, highest quality |
| openai | gpt-image-1 | All-purpose, text in images | Best quality, latest model |
| openai | dall-e-3 | Creative, artistic | Good prompt following |
| bfl | flux-pro-1.1 | Photorealism | Excellent detail |

### Size Guide

| Use Case | Size | Provider |
|----------|------|----------|
| Square (social media) | 1024x1024 | both |
| Portrait (phone wallpaper) | 1024x1536 | openai |
| Landscape (desktop wallpaper) | 1536x1024 | openai |
| Widescreen (banner) | 1024x576 | openai |
| Tall (story/poster) | 576x1024 | openai |

### Step 2: Run the Script

```bash
python "D:\00 lindahua\00 project\image\scripts\generate_image.py" --prompt "YOUR_ENHANCED_PROMPT" --provider volcengine --model "doubao-seedream-5-0-260128" --size "2K"
```

The script auto-generates the output filename with timestamp in the `output/` directory.

### Step 3: Report Result

After generation, tell the user:
- The image file path
- The enhanced prompt used (so they can learn and iterate)
- File size
- Offer to regenerate with adjustments

## Batch Generation

When the user wants multiple images:

1. Generate each with a unique seed or slight prompt variation
2. Use different filenames for each
3. Present all results together

Example for batch:
```bash
python "D:\00 lindahua\00 project\image\scripts\generate_image.py" --prompt "prompt variant 1" --output "D:\00 lindahua\00 project\image\output\img_1.png"
python "D:\00 lindahua\00 project\image\scripts\generate_image.py" --prompt "prompt variant 2" --output "D:\00 lindahua\00 project\image\output\img_2.png"
python "D:\00 lindahua\00 project\image\scripts\generate_image.py" --prompt "prompt variant 3" --output "D:\00 lindahua\00 project\image\output\img_3.png"
```

## Error Handling

- **API key errors**: Guide the user to set up their key (see Setup Check)
- **Rate limits**: Wait 30 seconds and retry once
- **Content moderation**: Rephrase the prompt to be less ambiguous
- **Timeout**: Image generation can take up to 60 seconds; this is normal
- **Network errors**: Check connectivity and retry

## Technical Notes

- Uses **OpenAI Python SDK** (`pip install openai`) for all API calls
- Volcengine ARK API is OpenAI-compatible — same SDK, just different `base_url`
- Python script: `scripts/generate_image.py` (primary)
- Legacy PowerShell script: `scripts/generate-image.ps1` (backup, no Python needed)
- Config file: `config/api-config.json`

## Important Notes

- ALWAYS enhance prompts before generation — raw user prompts produce mediocre results
- Default to `doubao-seedream-5-0-260128` (即梦AI 5.0) — supports Chinese prompts natively, 2K resolution
- Size uses resolution presets: `1K`, `1.5K`, `2K` (default), `4K`
- Uses OpenAI SDK with Volcengine base_url — `OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=...)`
- Save all images to the `output/` directory
- Never expose API keys in output or conversation
- If the user wants to iterate on an image, adjust the enhanced prompt and regenerate

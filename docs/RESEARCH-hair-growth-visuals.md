# Hair Growth Visuals: Deep Research Report

**Date:** 2026-03-27
**Goal:** Determine the best approach to generate realistic "hair growth" visuals for 130 football teams x 6 hair tiers = 780 images.
**Current baseline:** DiceBear avatars (cartoon-style, functional but not compelling)

---

## The Problem Decomposition

The visual challenge has TWO independent sub-problems:

1. **Character consistency with progressive hair growth** -- Same face, 6 different hair/beard lengths
2. **Accurate team jerseys** -- 130 distinct club jerseys that must be recognizable

These are best solved independently and composited, rather than trying to generate both in a single AI pass.

---

## Approach 1: AI Image Generation (Character Consistency)

### The State of the Art in 2026

Character consistency in AI image generation has undergone a massive leap since 2024. The key techniques:

| Technique | How It Works | Best For |
|-----------|-------------|----------|
| **Flux Kontext Pro** | 12B parameter model; edit an existing image with text instructions while preserving identity | Precise single-attribute changes (like hair length) |
| **IP-Adapter + ControlNet** | Embed facial identity from a reference image into new generations | Open-source, highly customizable |
| **Midjourney --cref / Omni Reference** | Upload a reference character, generate new scenes | Quick iteration, high quality |
| **LoRA fine-tuning** | Train a model on 10-20 images of a specific face | Maximum consistency, most effort |

### Flux Kontext Pro (RECOMMENDED for this project)

**What it does:** You provide an input image + a text instruction like "Make the person's hair shoulder-length and add a medium beard." The model edits ONLY what you ask while preserving everything else.

**Why it fits:**
- Start with ONE base image per team (person in jersey)
- Apply 6 progressive edits: "freshly shaved head" -> "short hair, slight stubble" -> "medium hair, short beard" -> "long hair, full beard" -> "very long unkempt hair, wild beard" -> "extremely long hair past shoulders, massive wild beard like a castaway"
- The face, body, and jersey stay consistent because you are EDITING, not generating from scratch
- $0.04 per image via fal.ai API
- **Total cost for 780 images: approximately EUR 31.20**

**API access:** Available on fal.ai (https://fal.ai/models/fal-ai/flux-pro/kontext) and Replicate. Both offer programmatic batch generation via REST API.

**Limitations:**
- Each edit accumulates small drift. After 6 edits, the character may have drifted slightly.
- Mitigation: Always edit from the ORIGINAL base image, not from the previous edit. Run 6 parallel edits from the same source.

### IP-Adapter + ControlNet via ComfyUI

**What it does:** Extract face identity from a reference photo (IP-Adapter), lock body pose (ControlNet OpenPose), then generate new images with different hair via text prompt.

**Why it could work:**
- Fully open-source, runs on local GPU
- CSV-driven batch workflows: define 780 rows with team + hair tier, let ComfyUI process automatically
- IP-Adapter-Plus-Face model specifically designed for face preservation
- ControlNet locks pose so every image has identical framing

**Recommended setup:**
- ip-adapter-plus-face_sdxl_vit-h.safetensors for face embedding
- ControlNet OpenPose for consistent body/pose
- Flux or SDXL as base model
- ComfyUI batch node with CSV input (team, hair_tier, prompt)

**Cost:** Free (local GPU) or ~$0.02-0.04/image on RunPod/ThinkDiffusion cloud
**Hardware requirement:** NVIDIA GPU with 12GB+ VRAM (RTX 3060 minimum, RTX 4090 ideal)

**Limitations:**
- More complex setup than Flux Kontext API
- Consistency is ~85-90% (occasional drift in face shape)
- Requires familiarity with ComfyUI

### Midjourney (V8 with Omni Reference)

**What it does:** Upload a character reference image, set --cw 0 to lock face only, describe new hair/beard in prompt.

**Why it might work:**
- Highest image quality of any generator
- --cw parameter gives fine control: 0 = face only, 100 = face + clothes + hair
- For this project: --cw 0 (face only) + describe jersey + describe hair tier

**Limitations:**
- No official API (must use unofficial APIs at $0.04-0.10/image or discord bot automation)
- 780 images via Discord is painful; unofficial APIs are fragile
- Jersey accuracy is unreliable in text-to-image
- Not practical for automated batch generation

### DALL-E 3 / GPT-4o Image Generation

**What it does:** Generate images from text prompts with some seed consistency.

**Why it falls short:**
- No character reference feature (no --cref equivalent)
- Seed-based consistency is unreliable across different prompts
- GPT-4o image generation is improving but still behind Flux Kontext for identity preservation
- Cost: ~$0.04-0.08/image via API
- Could work for one-off images but not for 780 consistent images

---

## Approach 2: AI Video Generation (Hair Growing Animation)

### The Opportunity

Instead of 6 static images per team, generate a single 5-second video showing hair GROWING on the supporter's head. This could be incredibly viral for social media.

### Available Tools

| Tool | Capability | Cost | Quality |
|------|-----------|------|---------|
| **Pollo AI** | Dedicated "AI Hair Growth" effect. Upload photo, get video of hair growing. | Free tier (limited) / $15-29/month | Good for social content |
| **Deevid AI** | Similar hair growth effect template | Free trial / paid plans | Good, 1080p output |
| **Kling AI** | Image-to-video, good at human animation | ~$0.10-0.30/video | High quality |
| **Runway Gen-3** | Image-to-video with strong motion control | ~$0.25-0.50/video | High quality |
| **Google Veo 3** | Understands "timelapse" prompts natively | Varies | Highest quality |

### Pollo AI (Best fit for quick wins)

- Dedicated hair growth effect template
- Upload a photo of "supporter in jersey" -> get video of hair growing
- Could process all 130 teams relatively quickly
- Best for social media clips (Instagram Reels, TikTok)

### Morphing Approach

Generate 2 images (short hair + long hair of same person) and use AI video morphing to create a smooth transition. Tools:
- Morph Studio (morphstudio.com) -- dedicated image morphing
- Kling -- image-to-video with strong identity preservation

### Practical Assessment

- Video generation is **excellent for social media content** (one-off viral clips)
- **Not practical for the main website** (need static images for 780 team cards)
- **Best used as a complementary asset**: generate videos for featured teams or the "Bijna bij de kapper!" section

---

## Approach 3: Real Photo + AI Enhancement

### How It Works

1. Photograph a real person (or use stock photo) in a plain t-shirt
2. Use AI inpainting to modify hair length (6 variations)
3. Use AI inpainting or compositing to add team jersey

### Tools for Hair Modification

| Tool | Method | Quality | Speed |
|------|--------|---------|-------|
| **HairFastGAN** | Neural network hair transfer, <1 second per image | High realism | Very fast |
| **YouCam AI Hairstyle** | 150+ hairstyle options, face-aware | High | Instant |
| **Cutout.pro** | AI hairstyle change from photo | Good | Fast |
| **Flux Kontext** (inpainting mode) | Text-guided selective editing | Excellent | ~3s/image |

### The Workflow

```
Real photo (person in plain shirt)
    |
    +-> AI hair edit: tier 1 (fresh cut)
    +-> AI hair edit: tier 2 (short)
    +-> AI hair edit: tier 3 (medium)
    +-> AI hair edit: tier 4 (long)
    +-> AI hair edit: tier 5 (very long)
    +-> AI hair edit: tier 6 (sasquatch)
    |
Each result -> AI jersey overlay (or Photoshop composite)
```

### Pros and Cons

**Pros:**
- Most realistic results (starting from a real photo)
- Face is 100% consistent (it is literally the same photo)
- HairFastGAN is open-source and near-instant

**Cons:**
- Still need to solve the jersey problem separately
- Need a good base photo (ideally a real person who consents to being "the face")
- Real photo + AI edit can land in uncanny valley if the hair edit is too dramatic
- Scaling to 130 teams means 130 jersey composites

---

## Approach 4: 3D Avatar Approaches

### Ready Player Me

- API for generating GLB format avatars
- Programmatic control over hair, beard, clothing
- Has generated 40,000+ avatars in batch operations
- **Limitation:** Cartoon/game aesthetic, not photorealistic
- **Good fit if:** You want a stylized look (which matches DiceBear's current style but better)

### MetaHuman (Unreal Engine)

- Photorealistic digital humans
- Version 5.7+ has procedural hair grooming
- Scriptable creation for batch generation
- **Limitation:** Requires Unreal Engine, heavy setup, GPU-intensive rendering
- **Overkill for this project** unless going for cinematic quality

### Blender + Python

- Full control over 3D character with hair particle system
- Python scripting for batch rendering 780 images
- Hair length is literally a parameter you can set (particle length)
- Jersey can be a texture on the 3D model

**Workflow:**
```python
for team in teams:
    set_jersey_texture(team.jersey_image)
    for tier in range(1, 7):
        set_hair_length(tier)
        set_beard_length(tier)
        render(f"output/{team.id}_tier{tier}.png")
```

### Practical Assessment

- **Ready Player Me:** Best if you want to upgrade from DiceBear while keeping a stylized look. API-driven, scalable, but not photorealistic.
- **Blender:** Maximum control, fully deterministic, but requires 3D modeling skills and initial setup time of 2-4 weeks for a good character model + hair system.
- **MetaHuman:** Overkill. Cinema-grade quality but massive overhead.

---

## Approach 5: Hybrid Approaches (RECOMMENDED)

### Option A: Flux Kontext Pipeline (Best balance of quality + effort)

```
Step 1: Create ONE base image
  - Use Flux or Midjourney to generate a generic "football supporter"
  - Neutral pose, front-facing, plain background
  - Simple colored t-shirt (not a specific jersey yet)

Step 2: Generate 6 hair tiers from the base
  - Flux Kontext Pro API: edit hair/beard length
  - Always edit from original base (not from previous tier)
  - Cost: 6 x $0.04 = $0.24 per character

Step 3: Apply jersey per team (130 teams)
  - Option A: Flux Kontext "Change the shirt to [Team] jersey"
  - Option B: Photograph/download real jersey images, composite in code
  - Option C: Use jersey template layer in HTML/CSS canvas

Step 4: Combine
  - 1 base character x 6 hair tiers x 130 jersey swaps = 780 images
  - But smartly: generate 6 hair images, then swap jersey 130 times = 6 + (6 x 130) = 786 API calls
  - Cost at $0.04/call: approximately $31.44 / EUR 29
```

### Option B: Real Photo + Programmatic Jersey Overlay

```
Step 1: Take/source 1 real photo of a person
Step 2: Use HairFastGAN or Flux Kontext for 6 hair variations
Step 3: Use HTML Canvas / Sharp (Node.js) / Pillow (Python) to overlay jersey colors
  - Don't generate full jerseys: use a TEMPLATE
  - Template = silhouette of a jersey on the person
  - Fill with team primary + secondary colors
  - Add team logo/crest overlay

Cost: Nearly free (open source tools + compute)
Quality: Medium-high (real face, AI hair, programmatic jersey)
```

### Option C: Ready Player Me + Custom Rendering

```
Step 1: Create base avatar via Ready Player Me API
Step 2: Programmatically set hair length parameter (6 tiers)
Step 3: Apply jersey color as outfit parameter
Step 4: Render via API or Blender headless

Cost: Free tier available, paid plans for higher quality
Quality: Stylized (not photorealistic) but consistent and scalable
```

---

## Approach 6: The Jersey Problem (Deep Dive)

This is the hardest sub-problem. Here are the options ranked:

### 1. Color-Based Template (RECOMMENDED for v1)

Instead of generating photorealistic jerseys, use a TEMPLATE approach:
- Create a jersey silhouette template (SVG or PNG with transparency)
- Fill with team's primary and secondary colors from a database
- Overlay team crest/logo (downloadable from public sources)
- Result: recognizable but not pixel-perfect replica

**Pros:** 100% accurate colors, scalable, no AI needed, works with any base image
**Cons:** Simplified look, not photorealistic

### 2. Flux Kontext Jersey Swap

Prompt: "Change the person's shirt to a [Team Name] home jersey with [color description]"
- Works surprisingly well for top clubs (Ajax, Feyenoord, Barcelona)
- Struggles with lesser-known clubs or complex patterns
- Stripe patterns and sponsor logos are unreliable

### 3. Real Jersey Photo Composite

- Photograph or screenshot real jerseys from club webshops
- Use image segmentation to cut out jersey shape
- Warp/composite onto the character's body
- Highest accuracy but requires 130 jersey source images

### 4. Data-Driven SVG Generation

```javascript
// Each team has structured data
const teamJersey = {
  primary: '#C8102E',    // Feyenoord red
  secondary: '#FFFFFF',  // White
  pattern: 'halves',     // left-right split
  crest: '/logos/feyenoord.svg'
};
// Render SVG jersey programmatically
```

---

## Cost Comparison Summary

| Approach | Cost (780 images) | Setup Time | Quality | Consistency | Scalability |
|----------|-------------------|------------|---------|-------------|-------------|
| **Flux Kontext API** | ~EUR 30 | 1-2 days | High | 90-95% | Excellent (API) |
| **ComfyUI local** | ~EUR 0 (+ GPU) | 3-5 days | High | 85-90% | Good (batch) |
| **Midjourney** | ~EUR 50-80 | 2-3 days | Highest | 80-85% | Poor (no API) |
| **Real photo + AI hair** | ~EUR 10-20 | 2-3 days | Highest | 100% face | Good |
| **Ready Player Me** | ~EUR 0-50 | 1-2 days | Medium (stylized) | 100% | Excellent (API) |
| **Blender 3D** | ~EUR 0 | 2-4 weeks | High | 100% | Excellent (script) |
| **Pollo AI video** | ~EUR 30-60 | 1 day | Good | Per-video | Medium |

---

## RECOMMENDATION: Phased Approach

### Phase 1 -- Quick Win (This Week)

**Use Flux Kontext Pro via fal.ai API**

1. Generate 1 base character (use Flux 2 Pro): generic male supporter, front-facing, neutral jersey
2. Create 6 hair tier variations using Flux Kontext (edit from base each time)
3. For jerseys: use the **color template approach**
   - SVG jersey template filled with team colors
   - Team crest overlay
   - Composite programmatically (Python/Pillow or Bun/Sharp)
4. Total cost: ~EUR 30 for AI generation + a few hours of scripting
5. Result: 780 unique images, consistent face, correct team colors

### Phase 2 -- Enhancement (Later)

- Replace template jerseys with Flux Kontext jersey swaps for top clubs
- Generate AI video clips (Pollo AI) for the "Bijna bij de kapper!" featured teams
- Consider multiple character types (male/female, different ethnicities)

### Phase 3 -- Premium (If Project Grows)

- Ready Player Me or Blender 3D pipeline for full deterministic control
- Real jersey photos composited for maximum accuracy
- Video content via Kling/Runway for social media campaigns

---

## Key Technical References

### Flux Kontext Pro API (primary recommendation)
- fal.ai: https://fal.ai/models/fal-ai/flux-pro/kontext
- Replicate: https://replicate.com/collections/flux
- BFL official: https://bfl.ai/pricing
- Prompting guide: https://docs.bfl.ai/guides/prompting_guide_kontext_i2i

### ComfyUI Consistent Characters
- IPAdapter + ControlNet workflow: https://learn.runcomfy.com/create-consistent-characters-with-controlnet-ipadapter
- Flux in ComfyUI: https://learn.thinkdiffusion.com/consistent-character-creation-with-flux-comfyui/
- Batch automation: https://apatero.com/blog/automate-images-videos-comfyui-workflow-guide-2025
- CSV-driven batch: https://comfyui.org/en/character-image-creation-workflow-guide

### AI Hair Modification
- HairFastGAN: https://www.digitalocean.com/community/tutorials/change-your-hairstyle-in-minutes-hairfastgan
- AI hairstyle tools comparison: https://www.pixelbin.io/blog/best-ai-hairstyle-changer-tools

### AI Video (Hair Growth Effect)
- Pollo AI Hair Growth: https://pollo.ai/video-effects/ai-hair-growth
- Deevid AI: https://deevid.ai/template/ai-hair-growth-effect

### Character Consistency Guides
- 2026 comprehensive guide: https://www.gensgpt.com/blog/character-consistency-ai-image-generation-2026-guide
- Midjourney cref: https://docs.midjourney.com/hc/en-us/articles/32162917505293-Character-Reference
- Stable Diffusion methods: https://stable-diffusion-art.com/consistent-face/

### Jersey Generation
- AI jersey swap: https://www.pixa.com/create/jersey-swap-editor
- Puma AI jersey design: https://www.businessoffashion.com/articles/technology/puma-is-bringing-ai-generated-design-to-the-football-pitch/

---

## Implementation Script Outline (Phase 1)

```python
# generate_hair_visuals.py
import httpx
import json
from pathlib import Path

FAL_API_KEY = "your-key"
BASE_URL = "https://fal.ai/models/fal-ai/flux-pro/kontext"

HAIR_TIERS = {
    1: "freshly shaved head, clean shaven face, no facial hair",
    2: "very short buzz cut hair, light stubble on chin",
    3: "medium length messy hair covering ears, short trimmed beard",
    4: "long hair past shoulders, full thick beard",
    5: "very long unkempt wild hair, large bushy untrimmed beard",
    6: "extremely long matted hair past waist, massive wild beard like a castaway who has not cut hair in years"
}

async def generate_tier(base_image_url: str, tier: int) -> bytes:
    """Edit the base image to show a specific hair tier."""
    response = await httpx.post(
        BASE_URL,
        headers={"Authorization": f"Key {FAL_API_KEY}"},
        json={
            "image_url": base_image_url,
            "prompt": f"Change this person's hair and beard to: {HAIR_TIERS[tier]}. Keep the face, body, clothing, and background exactly the same.",
            "num_inference_steps": 28,
            "guidance_scale": 7.5
        }
    )
    return response.json()["images"][0]["url"]

# For each team: composite hair tier image + jersey template
# See separate jersey_compositor.py for the SVG template approach
```

```python
# jersey_compositor.py
from PIL import Image, ImageDraw
import json

def create_jersey_composite(hair_image_path, team_data, output_path):
    """Overlay a colored jersey template onto the hair tier image."""
    base = Image.open(hair_image_path)
    jersey_template = Image.open("templates/jersey_mask.png")  # Alpha mask

    # Create colored jersey
    jersey = Image.new("RGBA", jersey_template.size, team_data["primary_color"])
    jersey.paste(jersey_template, mask=jersey_template)

    # Add team crest
    crest = Image.open(f"logos/{team_data['id']}.png").resize((60, 60))
    jersey.paste(crest, (center_x, chest_y), mask=crest)

    # Composite onto base image
    base.paste(jersey, (body_x, body_y), mask=jersey)
    base.save(output_path)
```

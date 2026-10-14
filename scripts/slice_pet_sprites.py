"""Hatch-Pet Sprite Slice & Processing Script (Pure Pillow Implementation)

本地素材生成工具，**不属于构建链路**：输入是作者机器上的角色原图（下方 SHEET_* 的绝对路径），
输出 `frontend/src/assets/pet/` 的精灵图与 `pet.json` 已经提交进仓库。
它不参与打包、不需要在新环境运行——换机器时改 SHEET_* 即可，其余步骤无需执行。

Extracts individual poses from generated character sheets, applies outer floodfill alpha transparency,
and generates clean high-resolution assets + pet.json manifest.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import json

SHEET_1 = Path(r"C:\Users\22937\.gemini\antigravity-ide\brain\44a08ab5-773d-4120-bb55-97ddc73d4d36\cat_pet_character_sheet_1787228983006.jpg")
SHEET_2 = Path(r"C:\Users\22937\.gemini\antigravity-ide\brain\44a08ab5-773d-4120-bb55-97ddc73d4d36\cat_pet_actions_extra_1787228999235.jpg")

OUT_DIR = Path(r"d:\code\projects\BLOG\frontend\src\assets\pet")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def remove_outer_white_background(img_rgb, threshold=242):
    """
    Uses floodfill from image borders to only remove the external white background,
    preserving white details inside the character body.
    """
    w, h = img_rgb.size
    # Convert to RGBA
    img_rgba = img_rgb.convert("RGBA")
    
    # Create mask image initialized with 255 (opaque)
    mask = Image.new("L", (w + 2, h + 2), 255)
    
    # Create a padded version of the RGB image for border floodfill
    padded = Image.new("RGB", (w + 2, h + 2), (255, 255, 255))
    padded.paste(img_rgb, (1, 1))
    
    # Floodfill outer white background with 0 (transparent) on the mask
    # We flood fill from the 4 corners
    ImageDraw.floodfill(padded, (0, 0), (255, 0, 255), thresh=30)
    
    # Extract alpha from padded where (255, 0, 255) was filled
    padded_alpha = Image.new("L", (w + 2, h + 2), 255)
    for x in range(w + 2):
        for y in range(h + 2):
            if padded.getpixel((x, y)) == (255, 0, 255):
                padded_alpha.putpixel((x, y), 0)
                
    # Crop mask back to original dimensions
    alpha_channel = padded_alpha.crop((1, 1, w + 1, h + 1))
    
    # Smooth alpha slightly with min filter to remove fringe
    alpha_smooth = alpha_channel.filter(ImageFilter.BoxBlur(0.6))
    
    # Assign alpha channel to image
    img_rgba.putalpha(alpha_smooth)
    
    # Get bounding box of visible pixels
    bbox = img_rgba.getbbox()
    if bbox:
        img_rgba = img_rgba.crop(bbox)
        
    return img_rgba

def slice_grid_cell(img, row, col, grid_size=3, padding_top=48, padding_bottom=12):
    """
    Crops a single cell from 3x3 grid, removing text headers/labels.
    """
    w, h = img.size
    cell_w = w / grid_size
    cell_h = h / grid_size
    
    left = int(col * cell_w + 12)
    top = int(row * cell_h + padding_top)
    right = int((col + 1) * cell_w - 12)
    bottom = int((row + 1) * cell_h - padding_bottom)
    
    cropped = img.crop((left, top, right, bottom))
    return cropped

def fit_to_canvas(img_rgba, target_size=(360, 360)):
    """
    Pads and centers the cropped character into a uniform square canvas.
    """
    tw, th = target_size
    w, h = img_rgba.size
    
    scale = min((tw * 0.86) / w, (th * 0.86) / h)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    
    resized = img_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
    
    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    offset_x = (tw - nw) // 2
    offset_y = (th - nh) // 2 + int(th * 0.03)
    
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas

def process_all():
    img1 = Image.open(SHEET_1)
    img2 = Image.open(SHEET_2)
    
    poses = [
        # Sheet 1: Core Codex Desk Pet Poses
        ("idle_home", img1, 0, 0, 52, 12),        # 1) Cozy Idle with Tea
        ("reading_book", img1, 0, 1, 52, 12),     # 2) Academic Reading Glasses & Book
        ("archive_lens", img1, 0, 2, 52, 12),     # 3) Archive Explorer Magnifying Glass & Scrolls
        ("about_welcome", img1, 1, 0, 52, 12),    # 4) Welcome Gentleman Bowtie & Waving
        ("typing_bongo", img1, 1, 1, 52, 12),     # 5) Bongo Cat Typing Keyboard
        ("sleeping_curl", img1, 1, 2, 52, 12),    # 6) Sleepy Curl
        ("dragging_scruff", img1, 2, 1, 28, 12),  # 7) Picked Up Scruff Dangling
        ("rocket_launch", img1, 2, 2, 28, 12),    # 8) Rocket Launch Propeller & Jetpack
        
        # Sheet 2: Spontaneous Idle Variations
        ("stretch", img2, 0, 0, 12, 12),          # 1) Full Stretch
        ("grooming", img2, 0, 1, 12, 12),         # 2) Face Wash Grooming
        ("eureka", img2, 0, 2, 12, 12),           # 3) Eureka Lightbulb Star Eyes
        ("curious_look", img2, 1, 0, 12, 12),     # 4) Curious Look at Butterfly
        ("petting_hearts", img2, 2, 2, 12, 12),   # 6) Heart Eyes Petting
    ]
    
    manifest_states = {}
    
    for name, sheet_img, r, c, pad_t, pad_b in poses:
        cell_raw = slice_grid_cell(sheet_img, r, c, padding_top=pad_t, padding_bottom=pad_b)
        cell_clean = remove_outer_white_background(cell_raw)
        final_sprite = fit_to_canvas(cell_clean, target_size=(360, 360))
        
        out_path = OUT_DIR / f"{name}.png"
        final_sprite.save(out_path, "PNG", optimize=True)
        print(f"[OK] Saved {out_path.name} -> {final_sprite.size}")
        
        manifest_states[name] = {
            "image": f"{name}.png",
            "size": [360, 360]
        }
        
    pet_manifest = {
        "name": "ZhiZhi Editorial Cat Pet",
        "version": "2.0.0",
        "description": "Codex-style companion desk pet for ZhiZhi Editorial Blog",
        "specification": "hatch-pet-v2",
        "author": "Antigravity",
        "canvas": {"width": 360, "height": 360},
        "states": manifest_states
    }
    
    with open(OUT_DIR / "pet.json", "w", encoding="utf-8") as f:
        json.dump(pet_manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\n[DONE] Successfully processed all sprites into {OUT_DIR}")

if __name__ == "__main__":
    process_all()

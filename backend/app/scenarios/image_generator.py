"""
Synthetic Receiving Photo Generator.
Generates realistic 2D visual representations of inbound shipments, cartons,
shipping labels, damage patterns (crushing, water damage, tears), and product arrays.
Used for offline self-contained benchmarking and live visualization.
"""

from typing import Tuple, List, Optional
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np


class SyntheticReceivingImageGenerator:
    """
    Renders high-fidelity synthetic receiving photographs with parameterized
    cartons, labels, barcodes, damage overlays, and product counts.
    """

    WIDTH = 640
    HEIGHT = 480

    @classmethod
    def generate_image(
        cls,
        sku: str,
        po_number: str,
        quantity: int,
        variant_color: str = "Blue",
        is_crushed: bool = False,
        is_water_damaged: bool = False,
        is_torn: bool = False,
        is_blurry: bool = False,
        is_occluded: bool = False,
        missing_components: Optional[List[str]] = None,
        adversarial_text: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Image.Image:
        # 1. Base background: Warehouse concrete floor / receiving dock conveyor
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), color=(220, 222, 226))
        draw = ImageDraw.Draw(img)

        # Dock conveyor rollers or pallet slats
        for y in range(0, cls.HEIGHT, 35):
            draw.line([(0, y), (cls.WIDTH, y)], fill=(195, 198, 204), width=2)

        # 2. Master Carton Rendering (Kraft Corrugated Cardboard)
        carton_box = (120, 90, 520, 390)
        cardboard_color = (205, 160, 115)
        cardboard_shadow = (170, 125, 85)

        # Draw carton isometric body
        draw.rectangle(carton_box, fill=cardboard_color, outline=cardboard_shadow, width=3)
        # Carton top crease / tape
        tape_box = (120, 230, 520, 250)
        draw.rectangle(tape_box, fill=(225, 195, 130), outline=(190, 160, 100), width=1)
        draw.text((280, 234), "INSPECTION SEAL", fill=(110, 80, 40))

        # 3. Product Display / Window (if visible units shown)
        if quantity > 0:
            # Draw unit grid inside or beside carton
            grid_start_x, grid_start_y = 150, 110
            cols = min(quantity, 8)
            rows = math.ceil(quantity / cols) if cols > 0 else 1
            unit_w, unit_h = 24, 38

            # Color mapping
            color_map = {
                "blue": (30, 110, 220),
                "red": (220, 40, 40),
                "green": (40, 180, 60),
                "black": (35, 35, 38),
                "matte black": (30, 30, 32),
                "white": (245, 245, 250),
                "yellow": (240, 200, 30)
            }
            p_fill = color_map.get(variant_color.lower(), (60, 120, 210))

            rendered = 0
            for r in range(rows):
                for c in range(cols):
                    if rendered >= quantity:
                        break
                    ux = grid_start_x + c * (unit_w + 12)
                    uy = grid_start_y + r * (unit_h + 10)
                    if ux + unit_w < 500:
                        # Bottle / product shape
                        draw.rounded_rectangle([ux, uy, ux + unit_w, uy + unit_h], radius=4, fill=p_fill, outline=(20, 20, 20), width=1)
                        draw.rectangle([ux + 6, uy - 4, ux + unit_w - 6, uy], fill=(180, 180, 180), outline=(20, 20, 20))
                        rendered += 1

            draw.text((150, 205), f"Visible Count: {quantity} units | Variant: {variant_color}", fill=(40, 30, 20))

        # 4. Shipping Label & Barcode
        label_box = (150, 270, 490, 370)
        draw.rectangle(label_box, fill=(255, 255, 255), outline=(50, 50, 50), width=2)

        # Label Header
        draw.text((160, 275), "GLOBAL FREIGHT INBOUND MANIFEST", fill=(0, 0, 0))
        draw.line([(150, 292), (490, 292)], fill=(180, 180, 180), width=1)

        draw.text((160, 298), f"PO NUMBER: {po_number}", fill=(0, 0, 0))
        draw.text((160, 314), f"SKU: {sku}", fill=(0, 0, 0))
        draw.text((160, 330), f"QTY: {quantity} PCS | COLOR: {variant_color.upper()}", fill=(0, 0, 0))

        # Simulated Barcode stripes
        bar_x = 350
        for i in range(26):
            bw = 2 if i % 3 == 0 else (3 if i % 5 == 0 else 1)
            draw.rectangle([bar_x, 302, bar_x + bw, 345], fill=(0, 0, 0))
            bar_x += bw + 2
        draw.text((350, 350), f"*{sku}*", fill=(0, 0, 0))

        # 5. Adversarial Text Injection on Label (if present)
        if adversarial_text:
            draw.rectangle([155, 352, 485, 368], fill=(255, 230, 230), outline=(200, 0, 0))
            draw.text((160, 354), adversarial_text[:50], fill=(180, 0, 0))

        # 6. Damage Overlay: Crushed Corner / Buckling
        if is_crushed:
            # Draw crushed polygon deformation at top-right corner
            crush_poly = [(450, 90), (520, 90), (520, 170), (470, 150), (430, 110)]
            draw.polygon(crush_poly, fill=(110, 80, 50), outline=(60, 40, 20))
            draw.line([(430, 110), (480, 145)], fill=(40, 25, 10), width=3)
            draw.line([(470, 150), (510, 165)], fill=(40, 25, 10), width=3)
            draw.text((440, 160), "[CRUSHED CORNER]", fill=(240, 50, 50))

        # 7. Damage Overlay: Water Stain & Corrugated Softening
        if is_water_damaged:
            # Dark moist amoeba-like stain
            water_ellipse = (180, 310, 330, 385)
            # Create semi-transparent overlay
            overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            o_draw.ellipse(water_ellipse, fill=(70, 50, 30, 160))
            o_draw.ellipse((200, 330, 280, 370), fill=(45, 30, 15, 190))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)
            draw.text((190, 375), "[WATER DAMAGE STAIN]", fill=(220, 50, 50))

        # 8. Damage Overlay: Torn Packaging & Exposed Fluting
        if is_torn:
            # Jagged dark tear polygon
            tear_poly = [(120, 180), (165, 195), (145, 230), (115, 240), (120, 180)]
            draw.polygon(tear_poly, fill=(50, 30, 15), outline=(20, 10, 5))
            for fy in range(190, 230, 5):
                draw.line([(125, fy), (155, fy + 2)], fill=(200, 170, 120), width=2)
            draw.text((130, 242), "[TEAR / PUNCTURE]", fill=(220, 50, 50))

        # 9. Missing Component Cutouts
        if missing_components:
            draw.rectangle([440, 200, 510, 240], fill=(240, 210, 210), outline=(200, 0, 0), width=2)
            draw.text((445, 205), "MISSING:", fill=(200, 0, 0))
            draw.text((445, 218), missing_components[0][:10], fill=(200, 0, 0))

        # 10. Ambiguity: Pallet Wrap Occlusion
        if is_occluded:
            overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            # Opaque dark stretch plastic wrap obscuring 60% of carton
            for y in range(80, 400, 15):
                o_draw.line([(80, y), (560, y + 40)], fill=(230, 235, 245, 170), width=12)
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        # 11. Ambiguity: Severe Focal Blur
        if is_blurry:
            img = img.filter(ImageFilter.GaussianBlur(radius=8))

        # Save to disk if requested
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, quality=92)

        return img

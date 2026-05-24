"""Mask combination (rectangle / ellipse with feather + invert + mode)."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _apply_masks(sprite: Image.Image, masks: list[Any]) -> Image.Image:
    """Combine masks and multiply with the sprite's alpha channel."""
    w, h = sprite.size
    combined = Image.new("L", (w, h), 0)
    for m in masks:
        layer_mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(layer_mask)
        x0 = int(m.bounds[0] * w)
        y0 = int(m.bounds[1] * h)
        x1 = int(m.bounds[2] * w)
        y1 = int(m.bounds[3] * h)
        if x1 <= x0 or y1 <= y0:
            continue
        if m.shape == "rectangle":
            d.rectangle([x0, y0, x1, y1], fill=255)
        else:  # ellipse
            d.ellipse([x0, y0, x1, y1], fill=255)
        if m.feather > 0:
            layer_mask = layer_mask.filter(ImageFilter.GaussianBlur(m.feather))
        if m.inverted:
            layer_mask = Image.eval(layer_mask, lambda v: 255 - v)
        if m.mode == "add":
            combined = ImageChops.lighter(combined, layer_mask)
        elif m.mode == "subtract":
            combined = ImageChops.subtract(combined, layer_mask)
        elif m.mode == "intersect":
            combined = ImageChops.multiply(combined, layer_mask)
    # Multiply with existing alpha
    src_alpha = sprite.split()[-1]
    new_alpha = ImageChops.multiply(src_alpha, combined)
    out = sprite.copy()
    out.putalpha(new_alpha)
    return out

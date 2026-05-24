"""Pixel-level blend modes (multiply / screen / overlay / …)."""

from __future__ import annotations

from PIL import Image


def _blend(base: Image.Image, top: Image.Image, x: int, y: int, mode: str) -> None:
    """Composite ``top`` onto ``base`` at (x, y) using the given blend mode.
    Mutates ``base`` in place."""
    if mode == "normal":
        base.alpha_composite(top, (x, y))
        return
    # Crop the region of base under top
    tw, th = top.size
    bw, bh = base.size
    if x >= bw or y >= bh or x + tw <= 0 or y + th <= 0:
        return
    # Clamp
    sx = max(0, -x)
    sy = max(0, -y)
    dx = max(0, x)
    dy = max(0, y)
    cw = min(tw - sx, bw - dx)
    ch = min(th - sy, bh - dy)
    if cw <= 0 or ch <= 0:
        return
    top_crop = top.crop((sx, sy, sx + cw, sy + ch))
    base_crop = base.crop((dx, dy, dx + cw, dy + ch))
    blended = _blend_pixels(base_crop, top_crop, mode)
    base.paste(blended, (dx, dy))


def _blend_pixels(base: Image.Image, top: Image.Image, mode: str) -> Image.Image:
    """Blend ``top`` over ``base`` (same size) using ``mode``. Honours top's
    alpha as a per-pixel mix factor."""
    import numpy as np

    b = np.asarray(base.convert("RGBA"), dtype=np.float32) / 255.0
    t = np.asarray(top.convert("RGBA"), dtype=np.float32) / 255.0
    br, bg, bb, ba = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    tr, tg, tb, ta = t[..., 0], t[..., 1], t[..., 2], t[..., 3]

    if mode == "multiply":
        rr, rg, rb_ = br * tr, bg * tg, bb * tb
    elif mode == "screen":
        rr = 1 - (1 - br) * (1 - tr)
        rg = 1 - (1 - bg) * (1 - tg)
        rb_ = 1 - (1 - bb) * (1 - tb)
    elif mode == "overlay":

        def _ov(a, c):
            return np.where(a < 0.5, 2 * a * c, 1 - 2 * (1 - a) * (1 - c))

        rr, rg, rb_ = _ov(br, tr), _ov(bg, tg), _ov(bb, tb)
    elif mode == "add":
        rr = np.clip(br + tr, 0, 1)
        rg = np.clip(bg + tg, 0, 1)
        rb_ = np.clip(bb + tb, 0, 1)
    elif mode == "subtract":
        rr = np.clip(br - tr, 0, 1)
        rg = np.clip(bg - tg, 0, 1)
        rb_ = np.clip(bb - tb, 0, 1)
    elif mode == "darken":
        rr = np.minimum(br, tr)
        rg = np.minimum(bg, tg)
        rb_ = np.minimum(bb, tb)
    elif mode == "lighten":
        rr = np.maximum(br, tr)
        rg = np.maximum(bg, tg)
        rb_ = np.maximum(bb, tb)
    elif mode == "difference":
        rr = np.abs(br - tr)
        rg = np.abs(bg - tg)
        rb_ = np.abs(bb - tb)
    elif mode == "color-dodge":
        rr = np.where(tr >= 1, 1, np.clip(br / np.maximum(1 - tr, 1e-6), 0, 1))
        rg = np.where(tg >= 1, 1, np.clip(bg / np.maximum(1 - tg, 1e-6), 0, 1))
        rb_ = np.where(tb >= 1, 1, np.clip(bb / np.maximum(1 - tb, 1e-6), 0, 1))
    elif mode == "color-burn":
        rr = np.where(tr <= 0, 0, 1 - np.clip((1 - br) / np.maximum(tr, 1e-6), 0, 1))
        rg = np.where(tg <= 0, 0, 1 - np.clip((1 - bg) / np.maximum(tg, 1e-6), 0, 1))
        rb_ = np.where(tb <= 0, 0, 1 - np.clip((1 - bb) / np.maximum(tb, 1e-6), 0, 1))
    else:
        return base

    # Mix with alpha: out = mix(base, blend_result, top.alpha)
    out_r = br * (1 - ta) + rr * ta
    out_g = bg * (1 - ta) + rg * ta
    out_b = bb * (1 - ta) + rb_ * ta
    out_a = ba + ta * (1 - ba)
    out = np.stack([out_r, out_g, out_b, np.clip(out_a, 0, 1)], axis=-1)
    out = (out * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

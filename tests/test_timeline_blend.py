"""Unit tests for demodsl.effects.timeline.blend — pixel blend modes.

Locks in two things: (1) each blend mode's numeric formula, and (2) the
bbox-shrink optimization in ``_blend`` never changes the final pixels
compared to blending the full (mostly-transparent) region.
"""

from __future__ import annotations

from PIL import Image

from demodsl.effects.timeline.blend import _blend, _blend_pixels


def _solid(size, rgba):
    return Image.new("RGBA", size, rgba)


def test_blend_normal_uses_alpha_composite():
    base = _solid((4, 4), (10, 20, 30, 255))
    top = _solid((4, 4), (200, 100, 50, 128))
    expected = base.copy()
    expected.alpha_composite(top, (0, 0))

    canvas = base.copy()
    _blend(canvas, top, 0, 0, "normal")

    assert list(canvas.getdata()) == list(expected.getdata())


def test_blend_pixels_multiply_opaque_top():
    base = _solid((1, 1), (200, 100, 40, 255))
    top = _solid((1, 1), (100, 250, 10, 255))
    out = _blend_pixels(base, top, "multiply")
    r, g, b, a = out.getpixel((0, 0))
    assert (r, g, b, a) == (
        round(200 * 100 / 255),
        round(100 * 250 / 255),
        round(40 * 10 / 255),
        255,
    )


def test_blend_pixels_screen_opaque_top():
    base = _solid((1, 1), (200, 100, 40, 255))
    top = _solid((1, 1), (100, 250, 10, 255))
    out = _blend_pixels(base, top, "screen")
    r, g, b, _ = out.getpixel((0, 0))
    assert (r, g, b) == (
        255 - round((255 - 200) * (255 - 100) / 255),
        255 - round((255 - 100) * (255 - 250) / 255),
        255 - round((255 - 40) * (255 - 10) / 255),
    )


def test_blend_pixels_darken_lighten():
    base = _solid((1, 1), (200, 20, 40, 255))
    top = _solid((1, 1), (50, 220, 40, 255))
    assert _blend_pixels(base, top, "darken").getpixel((0, 0))[:3] == (50, 20, 40)
    assert _blend_pixels(base, top, "lighten").getpixel((0, 0))[:3] == (200, 220, 40)


def test_blend_pixels_add_subtract_clip():
    base = _solid((1, 1), (200, 20, 0, 255))
    top = _solid((1, 1), (100, 10, 0, 255))
    assert _blend_pixels(base, top, "add").getpixel((0, 0))[:3] == (255, 30, 0)
    assert _blend_pixels(base, top, "subtract").getpixel((0, 0))[:3] == (100, 10, 0)


def test_blend_pixels_difference():
    base = _solid((1, 1), (200, 20, 40, 255))
    top = _solid((1, 1), (50, 220, 40, 255))
    assert _blend_pixels(base, top, "difference").getpixel((0, 0))[:3] == (150, 200, 0)


def test_blend_pixels_partial_alpha_mixes_toward_base():
    base = _solid((1, 1), (200, 100, 40, 255))
    top = _solid((1, 1), (0, 0, 0, 0))  # fully transparent multiply source
    out = _blend_pixels(base, top, "multiply")
    assert out.getpixel((0, 0)) == (200, 100, 40, 255)


def test_blend_fully_transparent_top_is_a_noop():
    canvas = _solid((50, 50), (10, 20, 30, 255))
    before = list(canvas.getdata())
    top = Image.new("RGBA", (50, 50), (255, 255, 255, 0))
    _blend(canvas, top, 0, 0, "screen")
    assert list(canvas.getdata()) == before


def test_blend_bbox_shrink_matches_direct_patch_blend():
    """A large, mostly-transparent sprite (e.g. a full-canvas polyline/particle
    tile) must blend identically whether or not the bbox-shrink kicks in."""
    canvas_size = (400, 300)
    base = Image.new("RGBA", canvas_size, (30, 30, 30, 255))
    for x in range(canvas_size[0]):
        for y in range(0, canvas_size[1], 37):  # sparse texture, cheap to build
            base.putpixel((x, y), (x % 255, y % 255, 128, 255))

    sprite = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    patch_box = (120, 90, 160, 120)  # small opaque patch, offset from origin
    patch = Image.new(
        "RGBA", (patch_box[2] - patch_box[0], patch_box[3] - patch_box[1]), (255, 120, 0, 180)
    )
    sprite.paste(patch, patch_box[:2])

    # Reference: blend only the exact patch region directly (no bbox logic).
    expected = base.copy()
    base_patch_crop = expected.crop(patch_box)
    blended_patch = _blend_pixels(base_patch_crop, patch, "screen")
    expected.paste(blended_patch, patch_box[:2])

    actual = base.copy()
    _blend(actual, sprite, 0, 0, "screen")

    assert list(actual.getdata()) == list(expected.getdata())


def test_blend_bbox_shrink_respects_destination_offset():
    """Same as above but the sprite itself is placed at a non-zero (x, y)."""
    canvas_size = (200, 150)
    base = Image.new("RGBA", canvas_size, (5, 5, 5, 255))
    sprite = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    patch_box = (10, 10, 30, 25)
    patch = Image.new("RGBA", (20, 15), (10, 200, 90, 200))
    sprite.paste(patch, patch_box[:2])

    dest_x, dest_y = 40, 20
    expected = base.copy()
    dst_box = (dest_x + patch_box[0], dest_y + patch_box[1])
    base_patch_crop = expected.crop((dst_box[0], dst_box[1], dst_box[0] + 20, dst_box[1] + 15))
    blended_patch = _blend_pixels(base_patch_crop, patch, "multiply")
    expected.paste(blended_patch, dst_box)

    actual = base.copy()
    _blend(actual, sprite, dest_x, dest_y, "multiply")

    assert list(actual.getdata()) == list(expected.getdata())

"""Built-in flat-vector reviewer portrait for the DemoBro reviewer badge.

Used when no photo is configured: a warm, friendly bust with a headset mic —
reads instantly as "a human is talking you through this". Returned as an SVG
data URI so no asset file needs to exist or be copied into the render dir.
"""

from __future__ import annotations

import base64

_PORTRAIT_SVG = """\
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>
  <defs>
    <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='{accent}'/>
      <stop offset='1' stop-color='#22243a'/>
    </linearGradient>
  </defs>
  <rect width='96' height='96' fill='url(#bg)'/>
  <path d='M16 96c2-20 14-28 32-28s30 8 32 28z' fill='#e8eaf6'/>
  <path d='M16 96c2-20 14-28 32-28s30 8 32 28z' fill='{accent}' opacity='.28'/>
  <rect x='41' y='54' width='14' height='14' rx='6' fill='#eab68f'/>
  <ellipse cx='48' cy='40' rx='17' ry='19' fill='#f2c29b'/>
  <path d='M31 38c-1-14 8-22 17-22s18 8 17 22c-2-8-6-11-9-11 2 3 2 5 2 5s-5-4-10-4-12 3-15 8c-1 1-2 2-2 2z' fill='#3b2f2a'/>
  <circle cx='31.5' cy='42' r='3.4' fill='#eab68f'/>
  <circle cx='64.5' cy='42' r='3.4' fill='#eab68f'/>
  <circle cx='42' cy='41' r='1.8' fill='#2b2b33'/>
  <circle cx='54' cy='41' r='1.8' fill='#2b2b33'/>
  <path d='M39 36.5c2-1.6 4.4-1.6 6 0M51 36.5c2-1.6 4.4-1.6 6 0' stroke='#3b2f2a' stroke-width='1.6' fill='none' stroke-linecap='round'/>
  <path d='M42 50c2 2.6 10 2.6 12 0' stroke='#b06f4a' stroke-width='2' fill='none' stroke-linecap='round'/>
  <path d='M29 40c0-12 8-20 19-20s19 8 19 20' stroke='#1f2130' stroke-width='4' fill='none' stroke-linecap='round'/>
  <rect x='26' y='38' width='7' height='12' rx='3.5' fill='#1f2130'/>
  <rect x='63' y='38' width='7' height='12' rx='3.5' fill='#1f2130'/>
  <path d='M31 50c0 6 6 9 12 10' stroke='#1f2130' stroke-width='3' fill='none' stroke-linecap='round'/>
  <circle cx='45' cy='60.5' r='3' fill='{accent}'/>
</svg>
"""


def portrait_data_uri(accent: str = "#6366F1") -> str:
    """The built-in portrait, tinted with *accent*, as an SVG data URI."""
    svg = _PORTRAIT_SVG.replace("{accent}", accent)
    b64 = base64.b64encode(svg.encode("utf-8")).decode()
    return f"data:image/svg+xml;base64,{b64}"

#!/usr/bin/env python3
"""
Generate the STEP of the Ronghe RH-5015 SMD test loop (LCSC C5199798), the Keystone 5015
micro-mini format, for the footprint YannLib:TestPoint_Ronghe_RH-5015 (KiCad 9 references
TestPoint_Keystone_5015_Micro_Mini.step without shipping it).

Source: Ronghe drawing 5015 rev. C (LCSC copy, one page, mm figures):
length 2.67 (+0.05 / -0.13) along X, strip width 1.02 along Y, height 1.52, top flat 1.02
(between the inner bends), strip 0.38 thick phosphor bronze, silver plate. The loop is a
trapezoid seen from the front, both strip ends meeting under the top flat (split at the
bottom centre). Bend radii, side angle and the width of the split are not dimensioned:
read off the drawing (outer radius 0.3, split 0.2, outer top corners at +/-0.76 so the
inner top corners fall at about +/-0.51). The bottom corners of the trapezoid are pushed out
until the rounded loop spans the 2.67 length.

Origin at footprint centre, seating plane Z = 0, model Y up (symmetric part: the KiCad
Y-down / model Y-up flip does not matter).
"""

import cadquery as cq
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "YannLib.3dmodels"

SILVER_COLOR = (0.85, 0.85, 0.85)    # Silver plate

LENGTH, WIDTH, HEIGHT = 2.67, 1.02, 1.52
THICK = 0.38
TOP_OUTER = 0.76                     # half width of the outer top flat, read off the drawing
RADIUS = 0.3                         # outer bend radius, read off the drawing
SPLIT = 0.2                          # gap between the two strip ends, read off the drawing


def ring(half_bottom):
    """Closed loop of strip, outer bends rounded; trapezoid corners at +/-half_bottom (Z = 0)."""
    outline = [(-half_bottom, 0), (half_bottom, 0), (TOP_OUTER, HEIGHT), (-TOP_OUTER, HEIGHT)]
    # Workplane XZ: local x = X, local y = Z; extrude both ways = centred on Y
    outer = (cq.Workplane("XZ").polyline(outline).close()
             .offset2D(-RADIUS).offset2D(RADIUS).extrude(WIDTH / 2, both=True))
    inner = (cq.Workplane("XZ").polyline(outline).close()
             .offset2D(-RADIUS).offset2D(RADIUS - THICK).extrude(WIDTH, both=True))
    return outer.cut(inner)


def rh5015():
    lo, hi = LENGTH / 2, LENGTH                  # rounding pulls the ends in: bisect the corner
    while hi - lo > 1e-4:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ring(mid).val().BoundingBox().xmax < LENGTH / 2 else (lo, mid)
    split = cq.Workplane("XY").box(SPLIT, 2 * WIDTH, 2 * THICK)
    loop = ring(hi).cut(split)

    output_file = OUTPUT_DIR / "TestPoint_Ronghe_RH-5015.step"
    (cq.Assembly()
     .add(loop, name="loop", color=cq.Color(*SILVER_COLOR))
     .save(str(output_file), exportType="STEP"))
    print(f"STEP file saved to: {output_file}")


if __name__ == "__main__":
    rh5015()

#!/usr/bin/env python3
"""
Generate the STEP of the Ymin LKM 270 uF 100 V radial electrolytic (LKML2002A271MF, LCSC C443150),
for the stock footprint Capacitor_THT:CP_Radial_D12.5mm_P5.00mm. KiCad 9's model for that footprint
is only 12.5 mm tall although the footprint says height = 20 mm.

Source: Ymin LKM catalogue p. 2 (102), 100 V / 270 uF = D x L 12.5 x 20 mm. The catalogue has no
drawing: pitch 5.0 and lead 0.6 are the usual values for D12.5 radials, L max = L + 2.0 (L >= 20).
Body modelled at the nominal L = 20; the 22 max is for clearance checks (boitier/gabarit_redcube.py).

Origin on pad 1 (+), pad 2 (-) at x = +5.0, body centred at x = 2.5, seating plane Z = 0,
leads down to Z = -3 (1.6 mm board + 1.4 mm cut leads).
"""

import math
import cadquery as cq
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "YannLib.3dmodels"

SLEEVE_COLOR = (0.10, 0.10, 0.12)    # Black PET sleeve
STRIPE_COLOR = (0.75, 0.75, 0.78)    # Negative polarity stripe
TOP_COLOR = (0.82, 0.82, 0.80)       # Bare aluminium can top
LEAD_COLOR = (0.85, 0.85, 0.85)      # Tinned leads

DIAMETER, HEIGHT = 12.5, 20.0
PITCH = 5.0
LEAD_D, LEAD_BELOW = 0.6, 3.0
SLEEVE = 0.1                         # sleeve over the can, open on the top flat
TOP_INSET = 0.8                      # sleeve curls over the top edge
STRIPE_DEG = 50                      # stripe width, on the pad 2 side


def main():
    cx = PITCH / 2
    r = DIAMETER / 2
    can = (cq.Workplane("XY").center(cx, 0).circle(r).extrude(HEIGHT)
           .faces(">Z").edges().chamfer(0.5))
    top = cq.Workplane("XY").center(cx, 0).circle(r - TOP_INSET).extrude(SLEEVE).translate((0, 0, HEIGHT - SLEEVE))
    body = can.cut(top)
    # stripe: wedge of the outer sleeve, centred on +X (pad 2, negative)
    a = math.radians(STRIPE_DEG / 2)
    pts = [(cx, 0), (cx + 2 * r * math.cos(a), -2 * r * math.sin(a)), (cx + 2 * r, 0),
           (cx + 2 * r * math.cos(a), 2 * r * math.sin(a))]
    wedge = cq.Workplane("XY").polyline(pts).close().extrude(HEIGHT - 1.0).translate((0, 0, 0.5))
    shell = (cq.Workplane("XY").center(cx, 0).circle(r).extrude(HEIGHT)
             .cut(cq.Workplane("XY").center(cx, 0).circle(r - SLEEVE).extrude(HEIGHT)))
    stripe = shell.intersect(wedge)
    body = body.cut(stripe)
    leads = (cq.Workplane("XY").pushPoints([(0, 0), (PITCH, 0)]).circle(LEAD_D / 2)
             .extrude(LEAD_BELOW + 0.5).translate((0, 0, -LEAD_BELOW)))

    output_file = OUTPUT_DIR / "CP_Radial_Ymin_LKM_D12.5x20mm_P5.00mm.step"
    (cq.Assembly()
     .add(body, name="body", color=cq.Color(*SLEEVE_COLOR))
     .add(stripe, name="stripe", color=cq.Color(*STRIPE_COLOR))
     .add(top, name="top", color=cq.Color(*TOP_COLOR))
     .add(leads, name="leads", color=cq.Color(*LEAD_COLOR))
     .save(str(output_file), exportType="STEP"))
    print(f"STEP file saved to: {output_file}")


if __name__ == "__main__":
    main()

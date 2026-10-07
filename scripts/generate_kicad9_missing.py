#!/usr/bin/env python3
"""
Generate STEP files for KiCad 9 footprints that reference a model KiCad does not ship.
Origin at footprint centre, model Y up (footprint pin 1 at -x/-y lands at -x/+y here).

- L_Bourns_SRP1265A.step: Bourns SRP1265A, lead frame terminal (datasheet p.1), used on the
  KiCad footprint Inductor_SMD:L_Bourns_SRP1245A (same land pattern, taller part).
  Body 13.5 x 12.5 x 6.2 mm; bottom terminals 2.3 x 4.7 mm. Side tab height and corner
  radius read off the drawing (not dimensioned).
- Infineon_PG-TSDSO-14-22.step: Infineon BTG7050-2EPL datasheet rev 1.00, figure 39.
  Body 3.9 x 4.9 mm, 0.95 mm thick on 0.05 mm standoff, lead span 6.0 mm, leads 0.25 mm
  wide at 0.65 mm pitch, foot 0.67 mm, lead thickness 0.2 mm, bottom pad 2.65 x 4.0 mm.
- Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad.step: Sensirion SHT4x datasheet
  v7.3, figure 15. Body 1.5 x 1.5 x 0.54 mm, contacts 0.3 x 0.3 mm at 0.8 mm pitch,
  centre pad 0.4 x 1.0 mm, sensor opening 0.6 mm diameter on top.
"""

import cadquery as cq
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "YannLib.3dmodels"

# Colors
BODY_COLOR = (0.15, 0.15, 0.15)     # Black mould compound
FERRITE_COLOR = (0.25, 0.25, 0.25)  # Dark grey inductor body
METAL_COLOR = (0.85, 0.85, 0.85)    # Tin / NiPdAu terminals
MARK_COLOR = (0.6, 0.6, 0.6)        # Pin 1 marker
SENSOR_COLOR = (0.55, 0.45, 0.3)    # Silicon die seen through the opening


def box(x, y, z, center=(0, 0, 0)):
    """Box of size x, y, z, centred in X/Y on center, bottom at center[2]."""
    return cq.Workplane("XY").box(x, y, z, centered=(True, True, False)).translate(center)


def disc(diameter, height, center):
    return cq.Workplane("XY").circle(diameter / 2).extrude(height).translate(center)


def save(assembly, name):
    output_file = OUTPUT_DIR / name
    assembly.save(str(output_file), exportType="STEP")
    print(f"STEP file saved to: {output_file}")


def srp1265a():
    LENGTH, WIDTH, HEIGHT = 13.5, 12.5, 6.2   # terminals along X
    TERM_DEPTH, TERM_WIDTH = 2.3, 4.7         # bottom terminal, from the body end
    TERM_THICK = 0.15
    TAB_HEIGHT = 3.0                          # side tab, read off the drawing
    CORNER_RADIUS = 1.0                       # read off the drawing

    body = (cq.Workplane("XY").rect(LENGTH - 2 * TERM_THICK, WIDTH).extrude(HEIGHT - TERM_THICK)
            .edges("|Z").fillet(CORNER_RADIUS).translate((0, 0, TERM_THICK)))
    terminals = None
    for side in (-1, 1):
        x_end = side * LENGTH / 2
        bottom = box(TERM_DEPTH, TERM_WIDTH, TERM_THICK, (x_end - side * TERM_DEPTH / 2, 0, 0))
        tab = box(TERM_THICK, TERM_WIDTH, TAB_HEIGHT, (x_end - side * TERM_THICK / 2, 0, 0))
        terminal = bottom.union(tab)
        terminals = terminal if terminals is None else terminals.union(terminal)

    save(cq.Assembly()
         .add(body, name="body", color=cq.Color(*FERRITE_COLOR))
         .add(terminals, name="terminals", color=cq.Color(*METAL_COLOR)),
         "L_Bourns_SRP1265A.step")


def tsdso14():
    BODY_X, BODY_Y = 3.9, 4.9                 # pins on the X sides
    STANDOFF, BODY_THICK = 0.05, 0.95
    LEAD_SPAN, LEAD_W, LEAD_T, FOOT = 6.0, 0.25, 0.2, 0.67
    PITCH, PINS_PER_SIDE = 0.65, 7
    EP_X, EP_Y = 2.65, 4.0

    top = STANDOFF + BODY_THICK
    body = box(BODY_X, BODY_Y, BODY_THICK, (0, 0, STANDOFF))
    ep = box(EP_X, EP_Y, STANDOFF, (0, 0, 0))

    # Gull wing profile in XZ (right side), extruded along Y
    x0, x2 = BODY_X / 2, LEAD_SPAN / 2
    x1 = x2 - FOOT
    z_mid = STANDOFF + BODY_THICK / 2
    profile = [(x0 - 0.05, z_mid + LEAD_T / 2), (x1, z_mid + LEAD_T / 2), (x1 + 0.2, LEAD_T),
               (x2, LEAD_T), (x2, 0), (x1, 0), (x1 - 0.2, z_mid - LEAD_T / 2),
               (x0 - 0.05, z_mid - LEAD_T / 2)]
    lead = cq.Workplane("XZ").polyline(profile).close().extrude(LEAD_W / 2, both=True)
    leads = None
    for i in range(PINS_PER_SIDE):
        y = (PINS_PER_SIDE - 1) / 2 * PITCH - i * PITCH   # pin 1 (left) at +y
        for one in (lead.mirror("YZ").translate((0, y, 0)), lead.translate((0, -y, 0))):
            leads = one if leads is None else leads.union(one)

    marker = disc(0.4, 0.01, (-BODY_X / 2 + 0.6, BODY_Y / 2 - 0.6, top))

    save(cq.Assembly()
         .add(body, name="body", color=cq.Color(*BODY_COLOR))
         .add(leads.union(ep), name="leads", color=cq.Color(*METAL_COLOR))
         .add(marker, name="pin1_marker", color=cq.Color(*MARK_COLOR)),
         "Infineon_PG-TSDSO-14-22.step")


def sht4x():
    SIDE, HEIGHT = 1.5, 0.54
    PAD, PITCH = 0.3, 0.8                    # contacts at the X edges
    CPAD_X, CPAD_Y = 0.4, 1.0
    PAD_T = 0.02
    OPENING, OPENING_DEPTH = 0.6, 0.15

    body = (box(SIDE, SIDE, HEIGHT - PAD_T, (0, 0, PAD_T))
            .faces(">Z").workplane().hole(OPENING, OPENING_DEPTH))
    pads = box(CPAD_X, CPAD_Y, PAD_T, (0, 0, 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            pads = pads.union(box(PAD, PAD, PAD_T, (sx * (SIDE - PAD) / 2, sy * PITCH / 2, 0)))
    die = disc(OPENING, 0.01, (0, 0, HEIGHT - OPENING_DEPTH))
    marker = disc(0.2, 0.01, (-SIDE / 2 + 0.25, SIDE / 2 - 0.25, HEIGHT))

    save(cq.Assembly()
         .add(body, name="body", color=cq.Color(*BODY_COLOR))
         .add(pads, name="pads", color=cq.Color(*METAL_COLOR))
         .add(die, name="sensor", color=cq.Color(*SENSOR_COLOR))
         .add(marker, name="pin1_marker", color=cq.Color(*MARK_COLOR)),
         "Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad.step")


def main():
    srp1265a()
    tsdso14()
    sht4x()


if __name__ == "__main__":
    main()

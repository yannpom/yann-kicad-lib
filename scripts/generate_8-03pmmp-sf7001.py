#!/usr/bin/env python3
"""
Generate the STEP of the Amphenol LTW 8-03PMMP-SF7001: M8 A-coded 3-pole MALE receptacle, straight PCB pins,
M8x1 panel thread with flat nut and O-ring (LCSC C21957007), for YannLib:8-03PMMP-SF7001.

Why a generated model: on 2026-11-11 the Amphenol LTW download server (Sucuri firewall), TME and EasyEDA all
refused the manufacturer STEP. Built from drawing 8-03PMMP-SF7001 rev D (2013-01-24); replace it by the Amphenol
STEP (https://amphenolltw.com/product-info/M-Series/M-Series.M8/8-03PMMP-SF7001.html, "3D STP") when someone
downloads it from a browser. Simplified: no helical thread (rings at 1.0 pitch), no knurl, contact pins approximated.

Dimensions (mm, drawing, QC = inspected):
  overall 16.4 (QC) from the PCB seating face to the mating face; tails 3.0 (QC) below it, D0.8 (measured);
  seating face to the flange front / O-ring seat 4.40 (QC); nose D6.90 (QC); hex 10.0 (QC) across flats;
  holes 1 / 3 at 3.50, 4 offset 1.75 (contacts on a D3.5 circle around the axis); panel cut-out D8.1 with flats
  7.1 across, panel 3.0 max. Measured on the drawing (scale from the 16.4 overall, +/-0.1): rear body D8.6 x 2.56,
  hex flange 1.8, O-ring 1.47 thick D10.0, nut 2.5 thick, thread to 13.34, relief groove D6.5 to 14.44.
Orientation, read on the two side views: the thread flats (7.1 across) are normal to the 1-3 line (the view along
that line shows a 7.1 silhouette, the other view shows the flats face-on) and the hex corners lie on the 1-3 line.
No panel nut: it is a loose part that ends up outside the wall (in the drawing's position, against the O-ring, it
would cross the aluminium in boitier/ `make controle`). The O-ring is free (1.47); the plate compresses it.

KiCad frame: origin on the connector axis, X towards contact 1, Y up (footprint -Y), seating plane Z = 0,
mating face at Z = +16.4. The footprint uses this model with no offset and no rotation.
"""

from pathlib import Path

import cadquery as cq

OUTPUT = Path(__file__).parent.parent / "YannLib.3dmodels" / "Amphenol_LTW_8-03PMMP-SF7001.step"

HOUSING = (0.10, 0.10, 0.11)      # black nylon + GF
NICKEL = (0.78, 0.78, 0.76)       # zinc alloy shield and copper-alloy nut, nickel plated
ORING = (0.05, 0.05, 0.05)        # black EPDM
GOLD = (0.86, 0.70, 0.30)         # gold-plated contacts

BODY_D, BODY_H = 8.6, 2.56
HEX_AF, FLANGE_TOP = 10.0, 4.40
HEX_AC = HEX_AF / 0.8660254
THREAD_D, THREAD_TOP, FLAT = 8.0, 13.34, 3.55
GROOVE_D, NOSE_BOTTOM, NOSE_D, TOP = 6.5, 14.44, 6.9, 16.4
BORE_D, INSERT_TOP = 5.6, 12.4
ORING_T, ORING_D = 1.47, 10.0
NUT_T = 2.5
TAIL_D, TAIL_L, PIN_D, PIN_TOP = 0.8, 3.0, 1.0, 15.4
# contacts in the model frame (Y up): 1 at +X, 3 at -X, 4 below the 1-3 line in the footprint (+Y there, -Y here)
CONTACTS = {"1": (1.75, 0.0), "3": (-1.75, 0.0), "4": (0.0, -1.75)}


def cyl(d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((0, 0, z0))


def hex_prism(z0, z1):
    """Hex 10 AF, corners on the X axis (1-3 line)."""
    return cq.Workplane("XY").polygon(6, HEX_AC).extrude(z1 - z0).translate((0, 0, z0))


def housing():
    body = cyl(BODY_D, 0, BODY_H).faces("<Z").edges().chamfer(0.2)
    flange = hex_prism(BODY_H, FLANGE_TOP).edges("|Z").chamfer(0.15)
    return body.union(flange)


def shield():
    thread = cyl(THREAD_D, FLANGE_TOP, THREAD_TOP)
    flats = (cq.Workplane("XY").rect(2 * FLAT, THREAD_D + 2).extrude(THREAD_TOP - FLANGE_TOP)
             .translate((0, 0, FLANGE_TOP)))
    thread = thread.intersect(flats)
    z = FLANGE_TOP + 0.5
    while z < THREAD_TOP - 0.3:          # thread suggested by rings, 1.0 pitch
        ring = cyl(THREAD_D + 1, z, z + 0.35).cut(cyl(THREAD_D - 0.5, z, z + 0.35))
        thread = thread.cut(ring)
        z += 1.0
    groove = cyl(GROOVE_D, THREAD_TOP, NOSE_BOTTOM)
    nose = cyl(NOSE_D, NOSE_BOTTOM, TOP).faces(">Z").edges().chamfer(0.9, 0.2)
    sleeve = thread.union(groove).union(nose)
    return sleeve.cut(cyl(BORE_D, INSERT_TOP, TOP + 1))


def insert():
    return cyl(BORE_D, INSERT_TOP - 0.5, INSERT_TOP)


def oring():
    ring = cyl(ORING_D, FLANGE_TOP, FLANGE_TOP + ORING_T).cut(cyl(THREAD_D, FLANGE_TOP, FLANGE_TOP + ORING_T))
    return ring.faces(">Z or <Z").edges().fillet(0.45)


def nut():
    z0 = FLANGE_TOP + ORING_T
    prism = hex_prism(z0, z0 + NUT_T)
    crown = cyl(HEX_AC, z0, z0 + NUT_T).edges().chamfer(0.6)      # chamfered corners, both faces
    return prism.intersect(crown).cut(cyl(THREAD_D, z0, z0 + NUT_T))


def pins():
    out = None
    for x, y in CONTACTS.values():
        tail = (cq.Workplane("XY").center(x, y).circle(TAIL_D / 2).extrude(TAIL_L - TAIL_D / 2 + 0.5)
                .translate((0, 0, -TAIL_L + TAIL_D / 2))
                .union(cq.Workplane("XY").sphere(TAIL_D / 2).translate((x, y, -TAIL_L + TAIL_D / 2))))
        top = (cq.Workplane("XY").center(x, y).circle(PIN_D / 2).extrude(PIN_TOP - PIN_D / 2 - INSERT_TOP + 0.5)
               .translate((0, 0, INSERT_TOP - 0.5))
               .union(cq.Workplane("XY").sphere(PIN_D / 2).translate((x, y, PIN_TOP - PIN_D / 2))))
        both = tail.union(top)
        out = both if out is None else out.union(both)
    return out


def main():
    asm = cq.Assembly(name="8-03PMMP-SF7001")
    asm.add(housing(), name="housing", color=cq.Color(*HOUSING))
    asm.add(insert(), name="insert", color=cq.Color(*HOUSING))
    asm.add(shield(), name="shield", color=cq.Color(*NICKEL))
    asm.add(oring(), name="oring", color=cq.Color(*ORING))
    asm.add(pins(), name="contacts", color=cq.Color(*GOLD))
    OUTPUT.parent.mkdir(exist_ok=True)
    asm.save(str(OUTPUT), exportType="STEP")
    print(f"STEP file saved to: {OUTPUT}")


if __name__ == "__main__":
    main()

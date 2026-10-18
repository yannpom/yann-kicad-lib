#!/usr/bin/env python3
"""
Generate a simplified STEP model of a #4-20 x 5/16" PLASTITE 48 (48-2) thread-forming screw for plastics,
pan head Phillips, steel zinc plated. No manufacturer STEP was found (Acument / REMINC licensees, CDE,
Fastener SuperStore: none downloadable), so this is modelled from the standard dimensions:
- Pan head (ASME B18.6.3, #4): D 5.56 (0.219 in max), H 2.03 (0.080 in max), Phillips #1 recess.
- Thread: #4 major diameter 2.84 (0.112 in), 20 TPI (pitch 1.27), 48 deg flank angle,
  drawn as axisymmetric V rings (no helix, no trilobular section); tapered point over 2 pitches.
- Length under head 7.94 (5/16 in).
Used by YannLib:DT15-4P and YannLib:DTM15-12PA (screws from the far side of the PCB into the D2.79 blind holes of the body,
8.00 deep on the DT15, 11.43 on the DTM15).
Origin: centre of the head bearing surface; shank along +Z, head along -Z.
"""

import math
from pathlib import Path

import cadquery as cq

HEAD_D = 5.56
HEAD_H = 2.03
HEAD_R = 0.75          # top edge rounding
MAJOR_D = 2.84
PITCH = 1.27
FLANK = 48.0           # included thread angle (deg)
LENGTH = 7.94          # under head
POINT = 2 * PITCH      # tapered point length
RECESS_W = 0.6         # Phillips #1 slot width
RECESS_L = 2.4
RECESS_DEPTH = 1.1

STEEL = (0.72, 0.73, 0.75)


def shank():
    depth = (PITCH / 2) / math.tan(math.radians(FLANK / 2))   # sharp-V depth for the half pitch
    depth = min(depth, 0.32)                                   # truncated crest / root
    r_maj = MAJOR_D / 2
    r_min = r_maj - depth
    pts = [(0, 0), (r_min, 0)]
    z = 0.0
    n = int(LENGTH / PITCH) + 1
    for k in range(n):
        for dz, r in ((PITCH / 2, r_maj), (PITCH, r_min)):
            zz = k * PITCH + dz
            if zz > LENGTH:
                break
            taper = 1.0 if zz < LENGTH - POINT else max(0.35, (LENGTH - zz) / POINT)
            pts.append((r * taper if r == r_maj else r_min * max(0.6, taper), zz))
    pts.append((0.35, LENGTH))
    pts.append((0, LENGTH))
    return cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))


def head():
    h = (cq.Workplane("XY").circle(HEAD_D / 2).extrude(HEAD_H)
         .faces(">Z").edges().fillet(HEAD_R)
         .translate((0, 0, -HEAD_H)))
    # head is below the bearing surface (z <= 0), recess on its outer face (z = -HEAD_H)
    for ang in (0, 90):
        cut = (cq.Workplane("XY").rect(RECESS_L, RECESS_W).extrude(RECESS_DEPTH)
               .rotate((0, 0, 0), (0, 0, 1), ang).translate((0, 0, -HEAD_H)))
        h = h.cut(cut)
    return h


def main():
    screw = shank().union(head())
    assy = cq.Assembly().add(screw, name="screw", color=cq.Color(*STEEL))
    out = Path(__file__).parent.parent / "YannLib.3dmodels" / "Plastite48_4-20x5-16_PanPhillips.step"
    assy.save(str(out), "STEP")
    bb = screw.val().BoundingBox()
    print(f"{out.name}: x {bb.xmin:.3f}..{bb.xmax:.3f}  z {bb.zmin:.3f}..{bb.zmax:.3f}")


if __name__ == "__main__":
    main()

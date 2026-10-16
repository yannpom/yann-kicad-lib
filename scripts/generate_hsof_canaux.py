#!/usr/bin/env python3
"""
Generate YannLib:Infineon_PG-HSOF-8-1_ThermalVias_Canaux, the TOLL footprint of the OuiCycle traction board: the stock
Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1_ThermalVias (42 vias 0.3 / 0.6 at 1.2 mm on the drain tab) with its via field
redrawn so that the GND plane of an inner layer passes between the vias.

Run with KiCad's Python (pcbnew):

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        scripts/generate_hsof_canaux.py [--paires 4] [--canal 0.75] [--sortie YannLib.pretty] [--nom ...]
        scripts/generate_hsof_canaux.py --sources        # low-side variant: ..._Canaux_SourceVias

Via field: rows along X (tab -> source leads, the direction of the switching-loop return current once the footprint is
rotated on the board), grouped in pairs at the minimum pitch, with a wider gap between pairs that leaves a continuous
copper channel in the inner GND plane. Every via is a pad "3" (drain) with unused inner layers removed (KiCad
"remove unused layers, keep start and end"): on a layer where no copper of the drain net touches it, only the drilled
hole and its clearance remain, so the plane is not cut by 0.6 mm pads. Inner layers carrying the drain net (zone) keep
their pad.

JLCPCB limits (capabilities page, 15 October 2026): KiCad exports footprint vias as component holes, so the pad-hole rules
apply: 0.45 mm between hole edges (pitch 0.75 for 0.3 mm drills), 0.3 mm from a PTH hole to inner-layer copper. Holes
stay 0.175 mm inside the tab copper (same rule as YannLib:TDSON-8-1_ThermalVias).

--sources (low-side MOSFETs, 16 October 2026): adds 21 pads "2" (source, GND) with the same via stack in the source land,
3 at PAS along each of the 7 lead strips (finger + bar, 0.8 x 2.8 mm), for the GND current that comes from the inner and
bottom planes. Not for the high side: there the source is the switch node, above the VBUS plane of B.Cu. The vias sit
under the leads and must be filled and capped.
"""

import argparse
import math
from pathlib import Path

import pcbnew

STOCK = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Package_TO_SOT_SMD.pretty')
ICI = Path(__file__).resolve().parent.parent
DRILL, DIAM = 0.3, 0.6
PAS = 0.75                    # mm, 0.45 between holes (JLCPCB pad holes)
DEGAGEMENT = 0.3              # mm, hole edge to inner-layer copper (JLCPCB PTH; zone clearance of the GND plane)
BORD = 0.175                  # mm, hole edge to tab copper edge
COLONNES = 10                 # vias per row along X
X_CENTRE = 2.65               # middle of the tab along X (copper -1.35 .. 6.65)
X_SOURCE = (-6.0, -5.25, -4.5)                          # along each lead strip (copper -6.65 .. -3.85)
Y_SOURCE = tuple(round(0.6 + 1.2 * (k - 3), 4) for k in range(7))   # the seven source leads, pitch 1.2


def rangees(paires, canal):
    """Y of the rows: pairs at PAS, pairs PAS + 2 * clearance radius + canal apart, centred on 0."""
    ecart = DRILL + 2 * DEGAGEMENT + canal          # centre-to-centre gap between two pairs
    ys, y = [], 0.0
    for _ in range(paires):
        ys += [y, y + PAS]
        y += PAS + ecart
    milieu = (ys[0] + ys[-1]) / 2
    return [round(v - milieu, 4) for v in ys]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paires', type=int, default=4)
    ap.add_argument('--canal', type=float, default=0.75, help='width of the GND channel between two pairs (mm)')
    ap.add_argument('--sortie', default=str(ICI / 'YannLib.pretty'))
    ap.add_argument('--nom')
    ap.add_argument('--sources', action='store_true', help='add 21 vias in the source land (low-side MOSFETs)')
    a = ap.parse_args()
    a.nom = a.nom or 'Infineon_PG-HSOF-8-1_ThermalVias_Canaux' + ('_SourceVias' if a.sources else '')

    fp = pcbnew.FootprintLoad(str(STOCK), 'Infineon_PG-HSOF-8-1_ThermalVias')
    pads = list(fp.Pads())
    languette = [p for p in pads if p.GetNumber() == '3' and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
                 and p.IsOnLayer(pcbnew.F_Cu)][0]
    cuivre = languette.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)
    vias = [p for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    modele = vias[0].Duplicate()
    for p in vias:
        fp.Remove(p)
    retires = vias                          # kept alive: pcbnew frees removed items with their footprint otherwise

    xs = [round(X_CENTRE + PAS * (k - (COLONNES - 1) / 2), 4) for k in range(COLONNES)]
    ys = rangees(a.paires, a.canal)
    for y in ys:
        for x in xs:
            p = modele.Duplicate()
            p.SetFPRelativePosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            p.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(DRILL), pcbnew.FromMM(DRILL)))
            p.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(pcbnew.FromMM(DIAM), pcbnew.FromMM(DIAM)))
            p.SetUnconnectedLayerMode(pcbnew.PADSTACK.UNCONNECTED_LAYER_MODE_REMOVE_EXCEPT_START_AND_END)
            # hole entirely inside the tab copper, BORD from its edge
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071), (0.7071, -0.7071), (-0.7071, -0.7071)):
                r = DRILL / 2 + BORD
                q = pcbnew.VECTOR2I(pcbnew.FromMM(x + r * dx), pcbnew.FromMM(y + r * dy))
                assert cuivre.Contains(q), (x, y)
            fp.Add(p)

    n = len(xs) * len(ys)
    sources = ''
    if a.sources:
        source = [p for p in pads if p.GetNumber() == '2' and p.IsOnLayer(pcbnew.F_Cu)][0]
        cuivre_s = source.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)
        for y in Y_SOURCE:
            for x in X_SOURCE:
                p = modele.Duplicate()
                p.SetNumber('2')
                p.SetFPRelativePosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                p.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(DRILL), pcbnew.FromMM(DRILL)))
                p.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(pcbnew.FromMM(DIAM), pcbnew.FromMM(DIAM)))
                p.SetUnconnectedLayerMode(pcbnew.PADSTACK.UNCONNECTED_LAYER_MODE_REMOVE_EXCEPT_START_AND_END)
                for k in range(16):           # the whole 0.6 mm annulus on the 0.8 mm source copper
                    q = pcbnew.VECTOR2I(pcbnew.FromMM(x + DIAM / 2 * math.cos(k * math.pi / 8)),
                                        pcbnew.FromMM(y + DIAM / 2 * math.sin(k * math.pi / 8)))
                    assert cuivre_s.Contains(q), (x, y)
                fp.Add(p)
        ns = len(X_SOURCE) * len(Y_SOURCE)
        sources = (f'low-side variant: {ns} vias 0.3/0.6 in the source land (3 at 0.75 mm in each of the 7 lead strips, '
                   'current from the inner/bottom GND planes), ')
    canal = ys[2] - ys[1] - DRILL - 2 * DEGAGEMENT
    fp.SetFPID(pcbnew.LIB_ID('YannLib', a.nom))
    fp.SetLibDescription(
        f'HSOF-8-1 [TOLL] power MOSFET, {sources}{n} thermal vias 0.3/0.6 in the drain tab: {a.paires} pairs of rows at 0.75 mm '
        f'(JLCPCB pad holes, 0.45 between holes), {canal:.2f} mm inner-plane channels between pairs, unused inner pads '
        'removed (OuiCycle traction, switching-loop return in In1) '
        '(http://www.infineon.com/cms/en/product/packages/PG-HSOF/PG-HSOF-8-1/)')
    fp.SetKeywords('mosfet hsof toll thermal vias channels')
    fp.Value().SetText(a.nom)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(str(sortie), fp)
    print(f'{a.nom} -> {sortie}: {n} vias, rows y {ys}, columns x {xs[0]} .. {xs[-1]}, channels {canal:.3f} mm')


main()

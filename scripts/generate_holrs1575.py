#!/usr/bin/env python3
"""Build a nominal visual STEP of Milliohm HoLRS1575 in FreeCAD.

Source: HoS20260413-90 rev.A0 2026-04-13, page 3 (mm).
W=15.2, A=7.6, H=2.5, flat terminal T=4.2, D2=2.0.
Visual simplifications: constant 2mm thickness through the raised centre,
45-degree straight transitions, no optional trimming notch or undimensioned
fillets. The resulting 0.5mm nominal underside gap is NOT a guaranteed clearance.
Colours distinguish terminals/alloy; they are illustrative, not material specs.
Origin: footprint centre, terminal seating plane Z=0; X along W.
Run using FreeCAD's Python with Resources/lib on PYTHONPATH.
"""
from pathlib import Path
import re
import FreeCAD as App
import Part


def add_step_colours(path):
    """Add AP214 presentation styles to the three FreeCAD-exported solids."""
    text = path.read_text()
    solids = re.findall(r'#(\d+) = MANIFOLD_SOLID_BREP\(', text)
    contexts = re.findall(r'#(\d+) = \( GEOMETRIC_REPRESENTATION_CONTEXT', text)
    assert len(solids) == 3 and contexts
    next_id = max(map(int, re.findall(r'#(\d+)\s*=', text))) + 1
    entities = []
    styles = []
    for solid, colour in zip(solids, [(0.72, 0.48, 0.23), (0.42, 0.44, 0.46), (0.72, 0.48, 0.23)]):
        n = next_id
        entities += [
            f"#{n} = COLOUR_RGB('',{colour[0]},{colour[1]},{colour[2]});",
            f"#{n+1} = FILL_AREA_STYLE_COLOUR('',#{n});",
            f"#{n+2} = FILL_AREA_STYLE('',(#{n+1}));",
            f"#{n+3} = SURFACE_STYLE_FILL_AREA(#{n+2});",
            f"#{n+4} = SURFACE_SIDE_STYLE('',(#{n+3}));",
            f"#{n+5} = SURFACE_STYLE_USAGE(.BOTH.,#{n+4});",
            f"#{n+6} = PRESENTATION_STYLE_ASSIGNMENT((#{n+5}));",
            f"#{n+7} = STYLED_ITEM('',(#{n+6}),#{solid});",
        ]
        styles.append(f'#{n+7}')
        next_id += 8
    entities.append(f"#{next_id} = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(styles)}),#{contexts[0]});")
    marker = 'ENDSEC;\nEND-ISO-10303-21;'
    assert text.count(marker) == 1
    path.write_text(text.replace(marker, '\n'.join(entities) + '\n' + marker))


def main():
    output = Path(__file__).resolve().parents[1] / 'YannLib.3dmodels'
    doc = App.newDocument('Milliohm_HoLRS1575')
    W, A, H, T, D2 = 15.2, 7.6, 2.5, 4.2, 2.0
    rise = H - D2
    inner = -W / 2 + T
    # Transition run equals rise ONLY as a visual 45-degree approximation.
    profile = [(-W/2, 0), (inner, 0), (inner+rise, rise),
               (inner+rise, H), (inner, D2), (-W/2, D2)]
    vertices = [App.Vector(x, -A/2, z) for x, z in profile]
    left = Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(App.Vector(0, A, 0))
    centre = Part.makeBox(-2*(inner+rise), A, D2, App.Vector(inner+rise, -A/2, rise))
    right = left.copy()
    right.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 180)
    objects = []
    for name, shape in [('Terminal1', left), ('ResistiveAlloy', centre), ('Terminal2', right)]:
        assert shape.isValid() and len(shape.Solids) == 1
        obj = doc.addObject('PartDesign::Feature', name)
        obj.Shape = shape
        obj.addProperty('App::PropertyString', 'Source', 'Documentation')
        obj.Source = 'HoS20260413-90 A0 p.3; nominal visual model, simplified bends, no guaranteed underside gap'
        objects.append(obj)
    doc.recompute()
    doc.saveAs(str(output / 'Milliohm_HoLRS1575.FCStd'))
    path = output / 'Milliohm_HoLRS1575.step'
    Part.export(objects, str(path))
    add_step_colours(path)
    imported = Part.Shape()
    imported.read(str(path))
    b = imported.BoundBox
    actual = (b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax)
    expected = (-7.6, 7.6, -3.8, 3.8, 0, 2.5)
    assert imported.isValid() and len(imported.Solids) == 3
    assert all(abs(a-b) < 1e-7 for a, b in zip(actual, expected)), actual
    print('STEP reimport: 3 valid solids; bounds (mm):', actual)
    for solid in imported.Solids:
        b = solid.BoundBox
        print('Solid bounds:', b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax)
    print('Nominal visual model: centre gap 0.5mm and straight bends are approximations, NOT toleranced requirements.')
    App.closeDocument(doc.Name)


if __name__ == '__main__':
    main()

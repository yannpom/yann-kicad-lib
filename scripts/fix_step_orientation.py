#!/usr/bin/env python3
"""Rewrite STEP models whose faces point inwards, so KiCad renders them correctly.

Some vendor exports (SolidWorks via LCSC/EasyEDA, among others) write a solid
with its faces oriented inwards. OpenCASCADE compensates by marking the shell
REVERSED, but KiCad's STEP loader reads each face's orientation relative to its
shell and ignores that flag: the part is tessellated inside out, OpenGL culls the
outer surfaces and the body looks hollow or semi-transparent in the 3D viewer.

The fix rebuilds each REVERSED shell as a FORWARD shell holding the same faces
flipped. Geometry, colours and names are kept; only orientation flags change.

Usage:
    python3 scripts/fix_step_orientation.py --check YannLib.3dmodels/*.step
    python3 scripts/fix_step_orientation.py MODEL.step [...]   # rewrites in place

Needs OCP (pip install cadquery-ocp).
"""
import argparse
import sys

from OCP.BRep import BRep_Builder
from OCP.BRepTools import BRepTools_ReShape
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Iterator, TopoDS_Shell, TopoDS_Solid
from OCP.XCAFDoc import XCAFDoc_DocumentTool


def read(path):
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    if reader.ReadFile(path) != IFSelect_RetDone or not reader.Transfer(doc):
        raise RuntimeError(f"cannot read {path}")
    return doc


def reversed_shells(shape):
    """Yield (solid, [shells]) for every solid holding a REVERSED shell."""
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        shells = []
        it = TopoDS_Iterator(solid, False, False)
        while it.More():
            if it.Value().ShapeType() == TopAbs_SHELL:
                shells.append(it.Value())
            it.Next()
        if any(s.Orientation() == TopAbs_REVERSED for s in shells):
            yield solid, shells
        explorer.Next()


def forward_solid(solid, shells):
    builder = BRep_Builder()
    new_solid = TopoDS_Solid()
    builder.MakeSolid(new_solid)
    for shell in shells:
        flip = shell.Orientation() == TopAbs_REVERSED
        new_shell = TopoDS_Shell()
        builder.MakeShell(new_shell)
        it = TopoDS_Iterator(shell, False, False)
        while it.More():
            face = it.Value()
            builder.Add(new_shell, face.Reversed() if flip else face)
            it.Next()
        new_shell.Closed(shell.Closed())
        builder.Add(new_solid, new_shell)
    new_solid.Location(solid.Location())
    new_solid.Orientation(solid.Orientation())
    return new_solid


def fix(path, check_only):
    doc = read(path)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = TDF_LabelSequence()
    shape_tool.GetShapes(labels)
    count = 0
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        if shape_tool.IsAssembly_s(label) or shape_tool.IsReference_s(label):
            continue
        shape = shape_tool.GetShape_s(label)
        bad = list(reversed_shells(shape))
        if not bad:
            continue
        count += len(bad)
        if check_only:
            continue
        reshape = BRepTools_ReShape()
        for solid, shells in bad:
            reshape.Replace(solid, forward_solid(solid, shells))
        shape_tool.SetShape(label, reshape.Apply(shape))
    if count and not check_only:
        Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        writer.SetLayerMode(True)
        if not writer.Transfer(doc, STEPControl_AsIs) or writer.Write(path) != IFSelect_RetDone:
            raise RuntimeError(f"cannot write {path}")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only, do not rewrite")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    found = 0
    for path in args.files:
        try:
            n = fix(path, args.check)
        except RuntimeError as exc:
            print(f"ERROR     {exc}")
            continue
        if n:
            found += 1
            print(f"{'REVERSED' if args.check else 'FIXED':9} {n} solid(s)  {path}")
    sys.exit(1 if args.check and found else 0)


if __name__ == "__main__":
    main()

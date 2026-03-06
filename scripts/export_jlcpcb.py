#!/usr/bin/env python3
"""
Export KiCad PCB to JLCPCB fabrication files.

Generates:
- Gerber files (zipped)
- Drill files (Excellon)
- BOM (Bill of Materials)
- CPL (Component Placement List) with rotation corrections
"""

import argparse
import csv
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
KICAD_CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
ROTATIONS_DB = SCRIPT_DIR / "jlcpcb_rotations.csv"


def run_kicad_cli(*args):
    """Run kicad-cli with given arguments."""
    cmd = [KICAD_CLI] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.returncode == 0


def load_rotation_corrections() -> list[dict]:
    """Load rotation corrections database."""
    corrections = []
    if not ROTATIONS_DB.exists():
        print(f"  Warning: Rotation database not found: {ROTATIONS_DB}")
        return corrections

    with open(ROTATIONS_DB, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pattern = row.get("Footprint pattern", "")
            if pattern:
                corrections.append({
                    "pattern": pattern,
                    "rotation": float(row.get("Rotation", 0) or 0),
                    "offset_x": float(row.get("Offset X", 0) or 0),
                    "offset_y": float(row.get("Offset Y", 0) or 0),
                })
    return corrections


def get_rotation_correction(footprint: str, corrections: list[dict]) -> tuple[float, float, float]:
    """Get rotation/offset correction for a footprint."""
    for corr in corrections:
        if re.search(corr["pattern"], footprint):
            return corr["rotation"], corr["offset_x"], corr["offset_y"]
    return 0, 0, 0


def generate_gerbers(pcb_file: Path, output_dir: Path) -> bool:
    """Generate Gerber and drill files."""
    gerber_dir = output_dir / "gerber"
    gerber_dir.mkdir(parents=True, exist_ok=True)

    print("1. Generating Gerber files...")
    if not run_kicad_cli(
        "pcb", "export", "gerbers",
        "--output", str(gerber_dir) + "/",
        "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
        "--no-x2",
        "--subtract-soldermask",
        "--use-drill-file-origin",
        str(pcb_file)
    ):
        return False

    print("2. Generating Drill files...")
    if not run_kicad_cli(
        "pcb", "export", "drill",
        "--output", str(gerber_dir) + "/",
        "--format", "excellon",
        "--drill-origin", "plot",
        "--excellon-zeros-format", "decimal",
        "--excellon-units", "mm",
        "--excellon-separate-th",
        str(pcb_file)
    ):
        return False

    # Create ZIP archive
    print("5. Creating ZIP archive...")
    zip_name = pcb_file.stem + "_gerber"
    shutil.make_archive(str(output_dir / zip_name), "zip", gerber_dir)

    # Clean up gerber directory
    shutil.rmtree(gerber_dir)

    return True


def generate_cpl(pcb_file: Path, output_dir: Path) -> bool:
    """Generate Component Placement List with rotation corrections."""
    print("3. Generating Position file (CPL)...")

    # Export raw position file to temp location
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    if not run_kicad_cli(
        "pcb", "export", "pos",
        "--output", tmp_path,
        "--format", "csv",
        "--units", "mm",
        "--side", "both",
        "--use-drill-file-origin",
        "--exclude-dnp",
        str(pcb_file)
    ):
        return False

    # Load rotation corrections
    corrections = load_rotation_corrections()

    # Convert to JLCPCB format with corrections
    rows = []
    corrections_applied = 0

    with open(tmp_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row.get("Ref", row.get("Reference", ""))
            footprint = row.get("Package", row.get("Footprint", ""))
            pos_x = float(row.get("PosX", row.get("Pos X", 0)))
            pos_y = float(row.get("PosY", row.get("Pos Y", 0)))
            rot = float(row.get("Rot", row.get("Rotation", 0)))
            side = row.get("Side", "")

            # Convert side to JLCPCB format
            layer = "top" if side.lower() in ["top", "front", "f"] else "bottom"

            # Apply rotation correction
            rot_corr, off_x, off_y = get_rotation_correction(footprint, corrections)
            if rot_corr != 0 or off_x != 0 or off_y != 0:
                corrections_applied += 1

            final_rot = (rot + rot_corr) % 360
            # Apply offset in footprint's local frame, rotated by component angle
            angle_rad = math.radians(rot)
            final_x = pos_x + off_x * math.cos(angle_rad) - off_y * math.sin(angle_rad)
            final_y = pos_y + off_x * math.sin(angle_rad) + off_y * math.cos(angle_rad)

            rows.append({
                "Designator": ref,
                "Mid X": f"{final_x:.6f}",
                "Mid Y": f"{final_y:.6f}",
                "Rotation": f"{final_rot:.6f}",
                "Layer": layer,
            })

    # Write JLCPCB format CPL
    cpl_path = output_dir / f"{pcb_file.stem}_CPL.csv"
    with open(cpl_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
        writer.writeheader()
        writer.writerows(rows)

    os.unlink(tmp_path)
    print(f"   CPL: {len(rows)} components, {corrections_applied} rotation corrections applied")
    return True


def generate_bom(schematic_file: Path, output_dir: Path) -> bool:
    """Generate Bill of Materials in JLCPCB format."""
    print("4. Generating BOM file...")

    # Export raw BOM
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    if not run_kicad_cli(
        "sch", "export", "bom",
        "--output", tmp_path,
        "--fields", "Reference,Value,Footprint,LCSC,${QUANTITY}",
        "--labels", "Reference,Value,Footprint,LCSC,Quantity",
        "--group-by", "Value,Footprint,LCSC",
        "--ref-delimiter", ",",
        "--ref-range-delimiter", "",  # Disable ranges like "R1-R4", use "R1,R2,R3,R4"
        "--exclude-dnp",
        str(schematic_file)
    ):
        return False

    # Convert to JLCPCB format
    rows = []
    missing_lcsc = []

    with open(tmp_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            refs = row.get("Reference", "")
            value = row.get("Value", "")
            footprint = row.get("Footprint", "")
            lcsc = row.get("LCSC", "").strip()

            if not lcsc:
                missing_lcsc.append(f"{refs} ({value})")
                continue

            # Extract footprint name from full path
            fp_name = footprint.split(":")[-1] if ":" in footprint else footprint

            rows.append({
                "Comment": value,
                "Designator": refs,
                "Footprint": fp_name,
                "LCSC Part #": lcsc,
            })

    # Sort by designator
    rows.sort(key=lambda x: x["Designator"])

    # Write JLCPCB format BOM
    bom_path = output_dir / f"{schematic_file.stem}_BOM.csv"
    with open(bom_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
        writer.writeheader()
        writer.writerows(rows)

    os.unlink(tmp_path)

    print(f"   BOM: {len(rows)} component groups")
    if missing_lcsc:
        print(f"   Warning: {len(missing_lcsc)} groups without LCSC code:")
        for item in missing_lcsc[:5]:
            print(f"     - {item}")
        if len(missing_lcsc) > 5:
            print(f"     ... and {len(missing_lcsc) - 5} more")

    return True


def export_jlcpcb(pcb_file: Path, output_dir: Path = None):
    """Export PCB to JLCPCB fabrication files."""
    pcb_file = Path(pcb_file).resolve()

    if not pcb_file.exists():
        print(f"Error: PCB file not found: {pcb_file}")
        return False

    # Default output directory
    if output_dir is None:
        output_dir = pcb_file.parent / "jlcpcb"
    else:
        output_dir = Path(output_dir).resolve()

    # Find matching schematic
    schematic_file = pcb_file.with_suffix(".kicad_sch")
    has_schematic = schematic_file.exists()

    print("=" * 50)
    print(f"JLCPCB Export: {pcb_file.stem}")
    print("=" * 50)
    print()

    # Clean and create output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Generate files
    if not generate_gerbers(pcb_file, output_dir):
        return False

    if not generate_cpl(pcb_file, output_dir):
        return False

    if has_schematic:
        if not generate_bom(schematic_file, output_dir):
            return False
    else:
        print(f"4. Skipping BOM (schematic not found: {schematic_file.name})")

    # Summary
    print()
    print("=" * 50)
    print(f"Generated files in: {output_dir}")
    print("=" * 50)
    for f in sorted(output_dir.iterdir()):
        print(f"  {f.name} ({f.stat().st_size:,} bytes)")

    print()
    print("Ready for JLCPCB upload:")
    print(f"  - Gerbers: {pcb_file.stem}_gerber.zip")
    if has_schematic:
        print(f"  - BOM: {pcb_file.stem}_BOM.csv")
    print(f"  - CPL: {pcb_file.stem}_CPL.csv")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Export KiCad PCB to JLCPCB fabrication files"
    )
    parser.add_argument(
        "pcb_file",
        help="Input .kicad_pcb file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: <pcb_dir>/jlcpcb)"
    )

    args = parser.parse_args()

    success = export_jlcpcb(args.pcb_file, args.output)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python3
"""
Setup script for YannLib KiCAD library
Adds YannLib to project-local fp-lib-table and sym-lib-table
"""

import os
import sys
from pathlib import Path


def get_relative_path(project_dir: Path, lib_dir: Path) -> str:
    """Calculate relative path from project to library."""
    return str(lib_dir.relative_to(project_dir)).replace("\\", "/")


def add_to_table(file_path: Path, entry: str, table_type: str) -> None:
    """Add library entry to a KiCAD lib-table file."""

    if file_path.exists():
        content = file_path.read_text()

        # Check if already configured
        if '"YannLib"' in content:
            print(f"✓ {table_type}: YannLib already configured")
            return

        # Add entry before closing parenthesis
        content = content.rstrip().rstrip(")")
        content += f"\n{entry}\n)\n"
        file_path.write_text(content)
        print(f"✓ {table_type}: Added YannLib")
    else:
        # Create new file
        content = f"({table_type}_lib_table\n{entry}\n)\n"
        file_path.write_text(content)
        print(f"✓ {table_type}: Created with YannLib")


def main():
    # Get library directory (where this script is)
    lib_dir = Path(__file__).parent.resolve()

    # Find project root (parent of libs directory)
    project_dir = lib_dir.parent.parent.resolve()

    # Calculate relative path
    try:
        rel_path = get_relative_path(project_dir, lib_dir)
    except ValueError:
        print("Error: Library must be inside project directory")
        sys.exit(1)

    print("YannLib Setup")
    print("=============")
    print(f"Library path: {lib_dir}")
    print(f"Project root: {project_dir}")
    print(f"Relative path: {rel_path}")
    print()

    # Footprint library entry
    fp_entry = f'  (lib (name "YannLib")(type "KiCad")(uri "${{KIPRJMOD}}/{rel_path}/YannLib.pretty")(options "")(descr "YannLib footprints"))'

    # Symbol library entry
    sym_entry = f'  (lib (name "YannLib")(type "KiCad")(uri "${{KIPRJMOD}}/{rel_path}/YannLib.kicad_sym")(options "")(descr "YannLib symbols"))'

    # Add to tables
    add_to_table(project_dir / "fp-lib-table", fp_entry, "fp")
    add_to_table(project_dir / "sym-lib-table", sym_entry, "sym")

    print()
    print("Done! Restart KiCAD to use YannLib.")


if __name__ == "__main__":
    main()

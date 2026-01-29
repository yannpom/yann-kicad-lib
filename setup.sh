#!/bin/bash
#
# Setup script for YannLib KiCAD library
# Adds YannLib to project-local fp-lib-table and sym-lib-table
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find project root (parent of libs directory)
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Calculate relative path from project to library
REL_PATH="${SCRIPT_DIR#$PROJECT_DIR/}"

echo "YannLib Setup"
echo "============="
echo "Library path: $SCRIPT_DIR"
echo "Project root: $PROJECT_DIR"
echo "Relative path: $REL_PATH"
echo ""

# Footprint library table entry
FP_ENTRY="  (lib (name \"YannLib\")(type \"KiCad\")(uri \"\${KIPRJMOD}/${REL_PATH}/YannLib.pretty\")(options \"\")(descr \"YannLib footprints\"))"

# Symbol library table entry
SYM_ENTRY="  (lib (name \"YannLib\")(type \"KiCad\")(uri \"\${KIPRJMOD}/${REL_PATH}/YannLib.kicad_sym\")(options \"\")(descr \"YannLib symbols\"))"

# Function to add entry to lib-table file
add_to_table() {
    local file="$1"
    local entry="$2"
    local type="$3"

    if [ -f "$file" ]; then
        # Check if YannLib already exists
        if grep -q "\"YannLib\"" "$file"; then
            echo "✓ $type: YannLib already configured"
            return
        fi
        # Add entry before the closing parenthesis
        sed -i.bak 's/)$//' "$file"
        echo "$entry" >> "$file"
        echo ")" >> "$file"
        rm -f "$file.bak"
        echo "✓ $type: Added YannLib"
    else
        # Create new file
        echo "(${type}_lib_table" > "$file"
        echo "$entry" >> "$file"
        echo ")" >> "$file"
        echo "✓ $type: Created with YannLib"
    fi
}

# Add to footprint library table
add_to_table "$PROJECT_DIR/fp-lib-table" "$FP_ENTRY" "fp"

# Add to symbol library table
add_to_table "$PROJECT_DIR/sym-lib-table" "$SYM_ENTRY" "sym"

echo ""
echo "Done! Restart KiCAD to use YannLib."

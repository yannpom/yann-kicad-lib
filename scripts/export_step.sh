#!/bin/bash
# Export KiCad PCB to STEP format
set -e

KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <input.kicad_pcb> [output.step]"
    exit 1
fi

INPUT="$1"
OUTPUT="${2:-${INPUT%.kicad_pcb}.step}"

if [ ! -f "$INPUT" ]; then
    echo "Error: Input file not found: $INPUT"
    exit 1
fi

echo "Exporting $INPUT -> $OUTPUT"
"$KICAD_CLI" pcb export step \
    --force \
    --subst-models \
    --drill-origin \
    --include-tracks \
    --include-zones \
    --include-pads \
    -o "$OUTPUT" "$INPUT"
echo "Done: $OUTPUT"

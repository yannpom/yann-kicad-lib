#!/usr/bin/env python3
"""
Generate STEP file for BCOHL1041 SMD Coupled Inductor
Dimensions from Bao Cheng datasheet:
- Body: 10.0 x 10.0 x 4.1 mm
- Corner radius: ~0.5mm
"""

import cadquery as cq
from pathlib import Path

# Component dimensions (mm)
BODY_WIDTH = 10.0    # A dimension
BODY_LENGTH = 10.0   # B dimension
BODY_HEIGHT = 4.1    # C dimension (max)
CORNER_RADIUS = 0.5  # Estimated corner radius

# Pad dimensions
PAD_WIDTH = 2.0      # D dimension (swap for correct orientation after rotation)
PAD_LENGTH = 2.5     # E dimension
PAD_HEIGHT = 1.4
PAD_X_OFFSET = 2.5   # Distance from center to pad center (X)
PAD_Y_OFFSET = 4.0   # Distance from center to pad center (Y)

# Colors
BODY_COLOR = (0.23, 0.2, 0.2)  # Dark gray
PAD_COLOR = (0.8, 0.8, 0.8)   # Silver

def create_body():
    """Create the main inductor body with rounded corners"""
    body = (
        cq.Workplane("XY")
        .box(BODY_WIDTH, BODY_LENGTH, BODY_HEIGHT)
        .translate((0, 0, BODY_HEIGHT / 2))
        .edges("|Z")
        .fillet(CORNER_RADIUS)
    )
    return body

def create_pad(x, y):
    """Create a single pad at position (x, y)"""
    pad = (
        cq.Workplane("XY")
        .box(PAD_WIDTH, PAD_LENGTH, PAD_HEIGHT)
        .translate((x, y, PAD_HEIGHT / 2))
    )
    return pad

def create_pads():
    """Create all 4 pads"""
    # Pad positions: (x, y)
    # Pin 1: bottom-left (-X, +Y in KiCad = -X, -Y in CAD with Y-up)
    # Pin 2: bottom-right (+X, +Y in KiCad)
    # Pin 3: top-right (+X, -Y in KiCad)
    # Pin 4: top-left (-X, -Y in KiCad)

    # Note: In this script Y is the same as KiCad (positive = bottom of footprint view)
    pad_positions = [
        (-PAD_X_OFFSET, PAD_Y_OFFSET),   # Pad 1
        (PAD_X_OFFSET, PAD_Y_OFFSET),    # Pad 2
        (PAD_X_OFFSET, -PAD_Y_OFFSET),   # Pad 3
        (-PAD_X_OFFSET, -PAD_Y_OFFSET),  # Pad 4
    ]

    pads = None
    for x, y in pad_positions:
        pad = create_pad(x, y)
        if pads is None:
            pads = pad
        else:
            pads = pads.union(pad)

    return pads

def create_pin1_marker():
    """Create pin 1 marker dot on top of body"""
    marker = (
        cq.Workplane("XY")
        .cylinder(0.05, 0.4)
        .translate((-3.5, 3.5, BODY_HEIGHT + 0.025))
    )
    return marker

def main():
    # Create components
    body = create_body()
    pads = create_pads()
    marker = create_pin1_marker()

    # Combine all parts
    assembly = (
        cq.Assembly()
        .add(body, name="body", color=cq.Color(*BODY_COLOR))
        .add(pads, name="pads", color=cq.Color(*PAD_COLOR))
        .add(marker, name="marker", color=cq.Color(1, 1, 1))
    )

    # Export to STEP
    output_dir = Path(__file__).parent.parent / "YannLib.3dmodels"
    output_file = output_dir / "BCOHL1041.step"

    assembly.save(str(output_file))
    print(f"STEP file saved to: {output_file}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate STEP file for XRRF1280 SMD Coupled Inductor
Dimensions from XiangRu Electronics datasheet:
- Body: 12.50 x 12.50 x 8.00 mm (max)
- Pad size: 5.0 x 1.8 mm
- Rounded cube shape with shallow circular marking on top
"""

import cadquery as cq
from pathlib import Path

# Component dimensions (mm) - from datasheet
BODY_WIDTH = 12.5       # Max dimension
BODY_LENGTH = 12.5      # Max dimension
BODY_HEIGHT = 8.0       # Max height
CORNER_RADIUS = 0.8     # Corner radius for vertical edges
TOP_FILLET = 0.5        # Fillet for top edges

# Marking on top (shallow circular indent)
MARKING_RADIUS = 5.0    # Radius of circular marking
MARKING_DEPTH = 0.2     # Depth of marking indent

# Pad dimensions from datasheet (5.0 x 1.8 mm)
PAD_LENGTH = 5.0        # Length along edge
PAD_WIDTH = 1.8         # Width perpendicular to edge
PAD_HEIGHT = 0.5        # Thickness of terminals

# Pad positions - matching footprint
PAD_X_OFFSET = 1.715    # X distance from center
PAD_Y_OFFSET = 4.25     # Y distance from center

# Colors
BODY_COLOR = (0.2, 0.18, 0.18)    # Dark gray/black (shielded body)
PAD_COLOR = (0.85, 0.85, 0.85)    # Bright silver (tin plating)
MARKING_COLOR = (0.15, 0.13, 0.13)  # Slightly darker for marking indent


def create_body():
    """Create the main inductor body - rounded cube"""
    # Create box with rounded vertical edges
    body = (
        cq.Workplane("XY")
        .box(BODY_WIDTH, BODY_LENGTH, BODY_HEIGHT)
        .translate((0, 0, BODY_HEIGHT / 2))
        .edges("|Z")
        .fillet(CORNER_RADIUS)
        .faces(">Z")
        .fillet(TOP_FILLET)
    )

    # Create shallow circular indent on top for marking
    marking_cut = (
        cq.Workplane("XY")
        .cylinder(MARKING_DEPTH + 0.1, MARKING_RADIUS)
        .translate((0, 0, BODY_HEIGHT - MARKING_DEPTH / 2))
    )

    body = body.cut(marking_cut)

    return body


def create_pad(x, y, rotate=False):
    """Create a single pad at position (x, y)

    Args:
        x: X position of pad center
        y: Y position of pad center
        rotate: If True, rotate pad 90 degrees (for top/bottom pads)
    """
    if rotate:
        # Pads on top/bottom edges (horizontal orientation)
        pad = (
            cq.Workplane("XY")
            .box(PAD_LENGTH, PAD_WIDTH, PAD_HEIGHT)
            .translate((x, y, PAD_HEIGHT / 2))
        )
    else:
        # Pads on left/right edges (vertical orientation)
        pad = (
            cq.Workplane("XY")
            .box(PAD_WIDTH, PAD_LENGTH, PAD_HEIGHT)
            .translate((x, y, PAD_HEIGHT / 2))
        )
    return pad


def create_pads():
    """Create all 4 pads matching the footprint positions"""
    # From footprint: pads are elongated in Y direction (4.5mm) but narrower in X (2.15mm)
    # This means pads 1&4 are on the left, pads 2&3 are on the right
    # The pads extend toward the outer edge

    # Looking at footprint pad positions and the datasheet pin diagram:
    # Pins 1,2 are at Y=-4.25 (top in standard view)
    # Pins 3,4 are at Y=+4.25 (bottom in standard view)

    # In 3D model coordinate system (looking down at board):
    # Pin 1: left-top
    # Pin 2: right-top
    # Pin 3: right-bottom
    # Pin 4: left-bottom

    pad_positions = [
        (-PAD_X_OFFSET, -PAD_Y_OFFSET, False),  # Pad 1 - vertical orientation
        (PAD_X_OFFSET, -PAD_Y_OFFSET, False),   # Pad 2 - vertical orientation
        (PAD_X_OFFSET, PAD_Y_OFFSET, False),    # Pad 3 - vertical orientation
        (-PAD_X_OFFSET, PAD_Y_OFFSET, False),   # Pad 4 - vertical orientation
    ]

    pads = None
    for x, y, rotate in pad_positions:
        pad = create_pad(x, y, rotate)
        if pads is None:
            pads = pad
        else:
            pads = pads.union(pad)

    return pads


def create_pin1_marker():
    """Create pin 1 marker - small dot near pin 1"""
    marker = (
        cq.Workplane("XY")
        .cylinder(0.05, 0.4)
        .translate((-4.5, -4.5, BODY_HEIGHT + 0.01))
    )
    return marker


def main():
    # Create components
    body = create_body()
    pads = create_pads()
    pin1_marker = create_pin1_marker()

    # Combine all parts using assembly
    assembly = (
        cq.Assembly()
        .add(body, name="body", color=cq.Color(*BODY_COLOR))
        .add(pads, name="pads", color=cq.Color(*PAD_COLOR))
        .add(pin1_marker, name="pin1_marker", color=cq.Color(1, 1, 1))
    )

    # Export to STEP
    output_dir = Path(__file__).parent.parent / "YannLib.3dmodels"
    output_file = output_dir / "XRRF1280.step"

    assembly.save(str(output_file))
    print(f"STEP file saved to: {output_file}")


if __name__ == "__main__":
    main()

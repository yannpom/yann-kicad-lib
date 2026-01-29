# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a KiCAD component library repository containing custom components and the official KiCAD footprint libraries (KiCAD 9 compatible).

## Structure

- **A_YANN.kicad_sym** - Custom symbol library (~100 components including ESP32 modules, USB connectors, power components)
- **A_YANN.pretty/** - Custom footprint library (100 footprints in `.kicad_mod` format)
- **A_YANN.3dmodels/** - 3D STEP models for custom components
- **kicad-footprints/** - Official KiCAD footprint libraries (146 `.pretty` directories)
- **3d/** - Additional 3D models

## KiCAD MCP Server

This repository has the KiCAD MCP server enabled. Use the `mcp__kicad__*` tools for:
- Creating/opening KiCAD projects
- Placing and editing components
- Managing footprints and symbols
- Exporting Gerbers, BOM, 3D models
- Running DRC checks
- Searching JLCPCB parts database

## File Formats

- `.kicad_sym` - Symbol library (S-expression format)
- `.kicad_mod` - Footprint files (S-expression format inside `.pretty` directories)
- `.step` / `.STEP` - 3D models

## Library Conventions

When modifying or adding components, follow the [KiCad Library Conventions (KLC)](https://klc.kicad.org/). Key points:
- Contribution guidelines: http://kicad.org/libraries/contribute
- Symbol naming, pin assignments, and graphical conventions are standardized

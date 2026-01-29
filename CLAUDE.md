# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal KiCAD component library (A_YANN) meant to be shared across machines and collaborators via Git.

## Structure

- **A_YANN.kicad_sym** - Custom symbol library (~100 components including ESP32 modules, USB connectors, power components)
- **A_YANN.pretty/** - Custom footprint library (100 footprints in `.kicad_mod` format)
- **A_YANN.3dmodels/** - 3D STEP models for custom components

## Usage in KiCAD Projects

Configure a path variable in KiCAD (Preferences → Configure Paths):
- Variable: `YANN_LIB` → `/path/to/this/repo`

Then reference libraries as:
- Symbols: `${YANN_LIB}/A_YANN.kicad_sym`
- Footprints: `${YANN_LIB}/A_YANN.pretty`
- 3D models: `${YANN_LIB}/A_YANN.3dmodels`

## KiCAD MCP Server

This repository has the KiCAD MCP server enabled. Use the `mcp__kicad__*` tools for component and project management.

## File Formats

- `.kicad_sym` - Symbol library (S-expression format)
- `.kicad_mod` - Footprint files (S-expression format inside `.pretty` directories)
- `.step` / `.STEP` - 3D models

## Library Conventions

When modifying or adding components, follow the [KiCad Library Conventions (KLC)](https://klc.kicad.org/).

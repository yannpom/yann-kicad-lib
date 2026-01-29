# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal KiCAD component library (YannLib) meant to be shared across machines and collaborators via Git. Can be used as a Git submodule in other projects.

## Structure

- **YannLib.kicad_sym** - Custom symbol library (~100 components including ESP32 modules, USB connectors, power components)
- **YannLib.pretty/** - Custom footprint library (115 footprints in `.kicad_mod` format)
- **YannLib.3dmodels/** - 3D STEP models for custom components

## Usage in KiCAD Projects

Configure a path variable in KiCAD (Preferences → Configure Paths):
- Variable: `YANN_LIB` → `/path/to/this/repo`

Then reference libraries as:
- Symbols: `${YANN_LIB}/YannLib.kicad_sym`
- Footprints: `${YANN_LIB}/YannLib.pretty`
- 3D models: `${YANN_LIB}/YannLib.3dmodels`

## As Git Submodule

```bash
git submodule add git@github.com:USERNAME/yann-kicad-lib.git libs/yann-kicad-lib
```

## KiCAD MCP Server

This repository has the KiCAD MCP server enabled. Use the `mcp__kicad__*` tools for component and project management.

## File Formats

- `.kicad_sym` - Symbol library (S-expression format)
- `.kicad_mod` - Footprint files (S-expression format inside `.pretty` directories)
- `.step` / `.STEP` - 3D models

## Library Conventions

When modifying or adding components, follow the [KiCad Library Conventions (KLC)](https://klc.kicad.org/).

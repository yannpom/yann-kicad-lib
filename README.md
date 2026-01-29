# YannLib - KiCAD Library

Personal KiCAD component library with symbols, footprints, and 3D models.

## Quick Setup (as Git Submodule)

```bash
# Add to your project
git submodule add git@github.com:USERNAME/yann-kicad-lib.git libs/yann-kicad-lib

# Run setup script to configure KiCAD project
./libs/yann-kicad-lib/setup.sh
```

## Manual Setup

If you prefer manual configuration, add these entries:

**In `fp-lib-table`:**
```
(lib (name "YannLib")(type "KiCad")(uri "${KIPRJMOD}/libs/yann-kicad-lib/YannLib.pretty")(options "")(descr ""))
```

**In `sym-lib-table`:**
```
(lib (name "YannLib")(type "KiCad")(uri "${KIPRJMOD}/libs/yann-kicad-lib/YannLib.kicad_sym")(options "")(descr ""))
```

## Contents

- **YannLib.kicad_sym** - Symbol library
- **YannLib.pretty/** - Footprint library (115 footprints)
- **YannLib.3dmodels/** - 3D STEP models (87 models)

## Update Submodule

```bash
git submodule update --remote libs/yann-kicad-lib
```

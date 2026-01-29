# Rapport des modèles 3D - YannLib Library

Date: 2025-01-29 (mise à jour finale)

## Résumé

| Catégorie | Nombre |
|-----------|--------|
| Footprints dans `YannLib.pretty/` | 115 |
| Fichiers 3D dans `YannLib.3dmodels/` | 87 |
| Fichiers 3D non utilisés | 0 |
| Modèles STEP manquants | 2 |
| Références .wrl (librairies officielles) | 22 |

---

## Modèles STEP manquants (2)

| Footprint | Modèle manquant |
|-----------|-----------------|
| MODULE_ESP32-WROOM-32D | ESP32-WROOM-32.step |
| OLED_SSD1306_1.3_128x64_ANGLED_SIDE | PinHeader_1x04_P2.54mm_Horizontal.step |

---

## Références .wrl (22)

Ces fichiers VRML sont référencés mais font partie des **librairies officielles KiCAD**. Pas besoin de les ajouter.

| Fichier .wrl |
|--------------|
| BARREL_JACK.wrl |
| Bosch_LGA-14_3x2.5mm_P0.5mm.wrl |
| Buzzer_15x7.5RM7.6.wrl |
| CR2013-MI2120.wrl |
| DFN-8-1EP_3x3mm_P0.65mm_EP1.55x2.4mm.wrl |
| DFN-8-1EP_6x5mm_Pitch1.27mm.wrl |
| ESP32-WROOM-32.wrl |
| HTSSOP-32-1EP_6.1x11mm_P0.65mm_EP5.2x11mm.wrl |
| LED_SK6812_PLCC4_5.0x5.0mm_P3.2mm.wrl |
| LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y.wrl |
| L_Bourns_SRP7028A_7.3x6.6mm.wrl |
| L_Bourns_SRR1208_12.7x12.7mm.wrl |
| PinHeader_2x04_P2.54mm_Vertical_SMD.wrl |
| SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm.wrl |
| SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.35x2.35mm.wrl |
| SW_SPST_EVPBF.wrl |
| TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm.wrl |
| TSOP-6_1.65x3.05mm_P0.95mm.wrl |
| TerminalBlock_Phoenix_MPT-0,5-5-2.54_1x05_P2.54mm_Horizontal.wrl |
| TerminalBlock_Phoenix_PTSM-0,5-2-2,5-V-SMD_1x02_P2.50mm_Vertical.wrl |
| Transformer_Murata_78250JC.wrl |
| USB_C_Receptacle_G-Switch_GT-USB-7051x.wrl |

---

## Corrections effectuées

- [x] `CUI_PJ-102B.kicad_mod` : chemin corrigé vers `${YANN_LIB}/YannLib.3dmodels/CUI_DEVICES_PJ-102B.step`
- [x] `KYCON_KPJX-4S-S.kicad_mod` : chemin corrigé vers `${YANN_LIB}/YannLib.3dmodels/KPJX-4S-S.step`
- [x] Suppression de 7 fichiers 3D non utilisés (~4.8 MB récupérés)

---

## Actions restantes

1. **Trouver les 2 fichiers STEP manquants** (optionnel) :
   - `ESP32-WROOM-32.step`
   - `PinHeader_1x04_P2.54mm_Horizontal.step`

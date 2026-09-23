# ESP32-S3-WROOM-1U

Empreinte utilisable dans KiCad : `YannLib:ESP32-S3-WROOM-1U`.

## Sources

- Empreinte copiée de `RF_Module:ESP32-S3-WROOM-1U`, bibliothèque installée avec KiCad 9.0.7. Géométrie, numérotation, pastilles et vias thermiques conservés à l'identique.
- [Modèle STEP officiel Espressif](https://www.espressif.com/sites/default/files/3dmodel/ESP32-S3-WROOM-1U%203D%20Model.STEP), téléchargé le 18 septembre 2026 depuis la [page du module](https://www.espressif.com/en/taxonomy/term/896).
- Fichier STEP conservé sans modification : `YannLib.3dmodels/ESP32-S3-WROOM-1U.step`.
- SHA-256 : `7be82bdafece2891b297546eb0643ff254e3d8161074ebdc972e0d78e79a4bdb`.

## Placement 3D

Référence : `${YANN_LIB}/YannLib.3dmodels/ESP32-S3-WROOM-1U.step`.
Configurer `YANN_LIB` vers le dossier de cette bibliothèque dans les chemins KiCad.

- Échelle : `(1, 1, 1)`.
- Rotation : `(0, 0, 0)` degrés.
- Décalage : `(-9, -9.6, 0)` mm.

Le modèle constructeur occupe X = 0…18 mm, Y = 0…19,2 mm et Z = 0…3,2 mm.
Le décalage le centre sur l'empreinte et conserve la face de soudure à Z = 0.
Le connecteur d'antenne se trouve du côté supérieur droit de l'empreinte.

## Vérifications

- Chargement de l'empreinte avec l'API KiCad 9.0.7 ; les 62 objets pastilles (dont ouvertures de pâte et vias thermiques) sont identiques à l'original.
- Import STEP dans FreeCAD : géométrie valide, dimensions 18 × 19,2 × 3,2 mm.
- Rendu 3D d'une carte temporaire avec `kicad-cli pcb render` : modèle chargé, orientation et alignement des contacts vérifiés visuellement.

Pour un composant existant, affecter `YannLib:ESP32-S3-WROOM-1U` au champ Empreinte, puis mettre à jour le PCB depuis le schéma.

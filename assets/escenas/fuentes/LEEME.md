# Fuentes de las escenas

Viajan con la skill porque el motor bloquea la red (`escena.py`, `_bloquear_red`): una
fuente que no está acá no existe para Chrome, que usa otra en silencio. Se cargan con
`@font-face` local en `base.css` y las plantillas esperan `document.fonts.ready` antes de
construir (el contrato de `base.js`).

| Familia | Uso | Pesos | Origen | Versión | Licencia |
|---|---|---|---|---|---|
| Barlow | títulos, números, cuerpo | 500–900 | npm `@fontsource/barlow` (subconjunto `latin`) | 5.3.0 | SIL OFL 1.1 (`OFL-Barlow.txt`) |
| IBM Plex Mono | etiquetas (kicker, notas, rótulos de flecha, numeración) | 500, 600 | npm `@fontsource/ibm-plex-mono` (subconjunto `latin`) | 5.3.0 | SIL OFL 1.1 (`OFL-IBM-Plex-Mono.txt`) |

Elegidas igual que la prueba con HyperFrames (HITO3.md). IBM Plex Mono no tiene ligaduras
(su GSUB sólo trae `ccmp`, `dnom`, `frac`, `numr`; medido con fontTools): `==`, `<=`, `!=` y
`->` se ven como dos caracteres. El subconjunto `latin` cubre español (á é í ó ú ñ ü ¿ ¡).

Bajadas el 06/10/2026 con `npm pack @fontsource/barlow @fontsource/ibm-plex-mono`.

## sha256

- `cd759df8ef9efc98fee14307b4eb5ba27f08b1f8f2f3ad2872432e25c89907a8` `barlow-latin-500-normal.woff2`
- `4b52ddd4836b592df0e4832b8286956883cdc651b015126bdd18f184b7f90cc3` `barlow-latin-600-normal.woff2`
- `2d797dd8b35dcb3413e1af9d7052b3f4f8c341a147cdcb01f4f06af80db53289` `barlow-latin-700-normal.woff2`
- `231d487a993e28bc5567c2be8da48acd8e0a209891c11448491eab45db0f8d7c` `barlow-latin-800-normal.woff2`
- `6f5d995ccc4d8ffd9e8cb4c303fc1f3646d6c62d40269ef59463332f12d5b897` `barlow-latin-900-normal.woff2`
- `01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22` `ibm-plex-mono-latin-500-normal.woff2`
- `0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83` `ibm-plex-mono-latin-600-normal.woff2`

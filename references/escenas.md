## Escenas: segmentos que no son pantalla grabada

Un segmento con `"escena"` en vez de `inicio`/`fin` no se corta del crudo: se renderiza desde
una plantilla HTML (`assets/escenas/`) y dura su slot de voz, igual que cualquier tramo. Se
pueden mezclar con segmentos de pantalla en el mismo guion. Ejemplo completo, sin crudo:
`assets/guion-ejemplo/explicador-interes-compuesto.json`.

| `tipo` | Qué muestra | Elementos con `cue` |
|---|---|---|
| `presentacion` | título cinético + puntos (sin puntos: portada con `subtitulo`; con `numero`: el dato gigante) | `puntos[]`, `subtitulo`, `numero`, `contra` |
| `diagrama` | nodos en fila y flechas que se dibujan | `nodos[]` (`id`, `texto`, `detalle`), `flechas[]` (`de`, `a`, `texto`) |
| `datos` | barras que crecen hasta su valor, con el número contando | `barras[]` (`etiqueta`, `valor`, `destacar`), `prefijo`, `nota` |
| `imagen` | metáforas dibujadas (SVG local), una fila, cada una con su rótulo | `dibujos[]` (`id`, `svg`, posición `x`/`y`? opcional), `rotulos[]` (`texto`, `de`) |
| `codigo` | editor con el código real de un archivo: tipeo, resaltado, diff y la salida real | `pasos[]` (`modo`: `tipeo`, `resaltar`, `diff`, `salida`) |
| `contador` | número protagonista gigante que cuenta hasta su valor | la escena entera (`cue` arriba, junto a `valor`) |

- **`cue` es la frase que nombra al elemento**, tal cual la dice el `texto` del segmento
  (`"cue": "tres décadas"`), o un número de segundos. El elemento entra en esa palabra.
  Se resuelve transcribiendo la voz con faster-whisper. Lo que Whisper oye mal se
  tolera así: una palabra de 6+ letras admite 1 error ("tembrano"). Si la cue tiene
  además un **ancla** (otra palabra suya de 4+ letras oída exacta, que no sea artículo),
  se admite 1 error en una palabra de 5 letras o menos ("más que poner" ← "las que
  poner") y hasta 2 en una de 6+ ("Hagamos números" ← "Hablamos números"). Una cue
  de una sola palabra corta y los números van exactos ("sí"≠"sin", "10"≠"100"). Los
  números se comparan en dígitos: "17 .000", "17.000", "17000" y "diecisiete mil" son
  el mismo ("por ciento" no se convierte). Sólo se unen los miles con punto y
  exactamente tres dígitos detrás: "100, 200" y "3 100" son dos números, y una coma
  entre dígitos es decimal ("2,500" es dos coma cinco y no matchea "2500"). **Costo**: dos errores sin ancla no se
  resuelven ("pesa más" ← "pesan las"). **Nunca anclan** (`NO_ANCLAN` en `palabras.py`):
  los artículos (el, la, los, las, lo, un, una, unos, unas), las contracciones al y del,
  y los demostrativos (este, ese, aquel y sus formas). Van delante de cualquier
  sustantivo, así que oírlos exactos no dice nada de la palabra que sigue: "unas tasas"
  no es "unas casas", igual que "la tasa" no es "la casa". "esta" también es "está" sin
  tilde y pierde el ancla: es más estricto, no más laxo. Si una cue no se encuentra, el error muestra
  qué se oyó: corregí la cue, no el guion.
- **Hoja de contacto antes del render**: `editar.py escenas vNN VOZ` genera las voces y deja
  cada spec resuelto en `videos/vNN/escenas/`; imprime el comando de `escena.py contacto`.
  Mirá el PNG (10/50/90 % de cada escena) y recién ahí `editar.py imagen`.
- **Título largo**: el contenido de las tres plantillas arranca debajo de la cabecera
  medida (kicker + título, con 40 px de aire), así que un título de 4 renglones baja
  los nodos, los puntos o las barras en vez de quedar tapado. Si desde ahí no queda
  lugar (un nodo al piso de 24 px, un renglón de 28, o 200 px de gráfico), la escena falla
  nombrando el título.
- **Estilo**: `brand.json` en `TUT_ROOT` pisa lo que declare de `assets/escenas/brand.json`
  (colores, `fuente`, `fuente_titulos`, `fuente_mono`, movimiento). Un solo color de acento.
  Tipografía propia embebida (`assets/escenas/fuentes/`, OFL, origen y sha256 en su
  `LEEME.md`): Barlow para títulos, números y cuerpo, IBM Plex Mono (sin ligaduras) para
  etiquetas. Otra familia se suma con su `@font-face` local en `base.css`: el motor bloquea
  la red, y una fuente que no está avisa con `AVISO` en vez de cambiarse en silencio.
- **Escena `imagen`**: metáforas dibujadas, no fotos (decidido por Juani, Q8). El `svg` de cada
  dibujo es una ruta a un archivo en `assets/escenas/dibujos/` (o al de la serie): SVG local
  escrito a mano para esta skill, o de un set de licencia MIT/ISC recoloreado, nunca una foto
  ni una referencia de red. Falta o `href` externo (`http://`/`https://` en `href`/`xlink:href`)
  → error antes de abrir Chrome, sin `.mp4` ni `.parcial.mp4`.
  - **Recoloreado**: el SVG se escribe con el trazo en `stroke="currentColor"` y, si tiene
    relleno secundario, `class="lleno" fill="currentColor"`. Nunca un color fijo (`#fff`, `red`)
    adentro del SVG: la escena fija la propiedad CSS `color` del contenedor al acento del brand
    si el dibujo es el foco (el que entró más recientemente, igual que nodos y flechas de
    `diagrama.html`) o a `--tenue` en caso contrario. Así cambiar `colores.acento` sólo mueve
    los píxeles del dibujo en foco.
  - **Que se dibuje, no que aparezca**: el trazo avanza con `stroke-dasharray`/`stroke-dashoffset`
    en función de `t` (ease-out, sin overshoot: los píxeles no-fondo del recuadro nunca bajan de
    un cuadro al siguiente, R-4.2) y el relleno `.lleno` entra después, en el último 15 % de
    `movimiento.entrada` del brand (cuando el trazo ya está prácticamente completo, no a mitad
    de camino). Si tiene o hereda `stroke` (el caso de los sets tipo Lucide/Tabler/Font Awesome,
    que lo ponen en el `<svg>` raíz, no en cada `<path>`) se dibuja por trazo igual: la detección
    mira el estilo COMPUTADO, no el atributo propio del elemento. Un SVG externo fuera de esta
    convención (forma sólo con relleno, `<text>`) se revela con la MISMA curva ease-out (escala
    0→1, sin overshoot) en vez de aparecer de golpe — no con resorte: el resorte tiene un ~4 % de
    overshoot que hace bajar los píxeles al asentarse, y R-4.2 exige que nunca bajen. Sin
    `viewBox` se calcula desde el bbox del contenido, o falla claro si no hay nada medible; un
    color fijo (`#fff`, `rgb()`, nombres) en `fill`/`stroke` falla claro en vez de quedar pegado
    para siempre.
  - Sin posición (`x`/`y`) van en una sola fila, cuadrados, espaciados (como máximo 8 a 160 px de
    lado); con muchos dibujos, textos de rótulo largos, `x`/`y` puesto en sólo algunos dibujos, o
    dos posiciones que se pisan, igual que las otras plantillas, falla claro en vez de pisar.
- **Escena `codigo`** (H4: tutoriales de código sin grabar VS Code). El código sale de un
  **archivo real**, nunca tipeado en el spec; rutas relativas a `TUT_ROOT` (en `escena.py render`,
  al directorio del spec). Ejemplo: `assets/guion-ejemplo/tutorial-memoizacion.json`.
  ```json
  {"tipo": "codigo", "archivo": "codigo/fibonacci_memo.py", "desde": 4, "hasta": 11,
   "pasos": [{"modo": "tipeo", "cue": "guardamos cada resultado"},
             {"modo": "resaltar", "lineas": "5-6", "cue": "si n ya está en memo"},
             {"modo": "diff", "archivo": "codigo/otra.py", "cue": "cambiamos"},
             {"modo": "salida", "ejecutar": "codigo/fibonacci_llamadas.py", "contar": true, "cue": "lo corremos"}]}
  ```
  `"lineas": "4-11"` equivale a `desde`/`hasta`; sin rango, el archivo entero. `"pseudocodigo": "..."`
  en vez de `archivo` sólo para pseudocódigo explícito (va sin resaltar). Los pasos van en el orden
  en que suenan, con un solo `tipeo` (antes del `diff`), un `diff` y una `salida`.
  - `tipeo` (`"por": "renglon"` opcional): carácter a carácter desde su cue, y **termina antes
    de la cue siguiente** (el ritmo se apura si hace falta). `resaltar`: recuadro en acento sobre
    las líneas (los números que se ven en ese momento), el resto en tenue. `diff`: lo que se va
    se pone rojo y se cierra, lo nuevo entra en verde (LCS por líneas). `salida`: terminal debajo
    con la salida **real** (se ejecuta con `python3` al armar el spec, desde una carpeta neutra,
    sin rutas del home); con `contar`, el último número de cada renglón cuenta hasta su valor.
  - Se resuelve en Python antes de abrir Chrome (`codigo.py`: Pygments, diff, ejecución): los
    comandos de escenas llevan `--with pygments`. La paleta de tokens sale del acento del brand.
  - Letra tan grande como entre (46 a 28 px, IBM Plex Mono sin ligaduras). Si la línea más larga
    o el total de líneas (código + terminal) no entra a 28 px, falla nombrándola: mostrá menos
    líneas. Con título, código de 8 líneas + 5 de terminal no entra: sacá el título.
- **Escena `contador`**: `{"tipo": "contador", "valor": 2692537, "unidad": "llamadas",
  "cue": "dos millones"}` (+ `prefijo`/`sufijo` pegados al número, `desde`, `conteo` en s,
  `kicker`/`titulo`). Cuenta en formato argentino (2.692.537) y frena exacto en el valor; de 360 a
  300 px o falla. Ideas de `count-up`/`number-pop-in`/`code-diff` de HyperFrames (Apache 2.0);
  el código es propio, no se copió nada.
- **Cero WebGL**: el motor bloquea `getContext('webgl'|'webgl2'|'experimental-webgl')` en
  cualquier plantilla (la GPU integrada de Juani la arrastra, PLAN.md); si una lo llama, sale
  como `ContratoError`, igual que cualquier otro error de JavaScript de la página.
- **Plantilla propia**: un HTML con `window.DURATION` y `async window.seek(t)` donde todo es
  función pura de `t` (sin `Date.now`, timers, `requestAnimationFrame` ni transiciones CSS).
  `escena.py render` falla claro si falta el contrato o si el JS tira un error.
- **La puerta antes del render** (contraste, superposición, elementos fuera de cue) corre en
  `verificar.py`: ver `references/verificacion.md`.
- **Plantilla con GSAP** (3.15.0 vendorizado en `assets/escenas/vendor/gsap/`, licencia en su
  `LEEME.md`): cargá `vendor/gsap/gsap.min.js` y los plugins que uses (`DrawSVGPlugin`,
  `MorphSVGPlugin`, `SplitText`, `CustomEase`) ANTES de `base.js`, registralos con
  `gsap.registerPlugin(...)` y llamá `E.lineaDeTiempo(() => { ...; return tl; })`. El DOM y la
  timeline se arman ADENTRO de esa función: corre una vez, con las fuentes ya cargadas (SplitText
  y DrawSVG miden). `DURATION` es la de la timeline (o la del slot, si el motor la pisa) y
  `seek(t)` es `tl.totalTime(t)`; el puente pausa la timeline global, así que el reloj real no
  mueve nada. Ejemplo: `assets/scripts/tests/fixtures/gsap/prueba-gsap.html`. Prohibido:
  `gsap.ticker`, `repeat: -1` (duración infinita), `onUpdate` con azar, tweens que no cuelgan de
  la timeline devuelta (quedan congelados en su inicio).
- **Forzar relayout del `body` después de cada `seek` hace determinista el render**
  (medido: sin él 14/27 y 11/27 cuadros dependen del orden; con él 0). La causa exacta
  en Chrome no está identificada: en la portada la diferencia cae en el borde de un
  elemento redondeado, en `datos` en una fila horizontal de ~242 px.
- Chrome a escala fraccionaria tampoco es determinista: el motor captura siempre a
  1920x1080 y achica con ffmpeg.
- **`av<19`**: la faster-whisper actual rompe con `av` 19 (`metadata_errors`). Va pineado en
  los comandos de abajo.

## Comandos de escenas

```bash
export TUT_ROOT=~/Proyectos/tutorial-X
S=~/.claude/skills/tutorial-video-agente/assets/scripts

# escenas (Chrome instalado, no baja navegadores)
E="uv run --with playwright --with pygments --with faster-whisper --with av<19 python"
$E $S/editar.py escenas v01 argentina          # voces + specs resueltos, sin renderizar
uv run --with playwright --with pygments python $S/escena.py contacto videos/v01/escenas/*.json -o videos/v01/contacto.png
$E $S/editar.py imagen v01 argentina && $S/editar.py voz v01 argentina
uv run --with playwright --with pygments python $S/escena.py render datos spec.json -o prueba.mp4 --ancho 960 --fps 12   # prueba suelta
uv run --with playwright --with pygments python $S/verificar.py videos/v01/escenas/*.json   # la puerta sola, sin renderizar
```

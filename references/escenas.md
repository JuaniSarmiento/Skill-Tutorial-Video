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
| `pila` | la pila de llamadas de una recursión LINEAL (una sola rama, como `factorial`): un marco se apila en su llamada y se desapila mostrando su valor de retorno | `pasos[]`, uno por cada llamada Y retorno de la traza real (H5) |
| `arbol` | el árbol de llamadas de una recursión que SE RAMIFICA (como `fibonacci`): crece de a un nodo, y una llamada que repite argumentos entra resaltada en el acento | `pasos[]`, uno por cada LLAMADA de la traza real (el árbol no se achica) |
| `curva` | una curva que se dibuja (DrawSVG) con un contador que la acompaña y puntos marcados con su valor | `puntos[]` (`x`, `y`, `etiqueta`) |
| `linea-de-vida` | un eje de años/edades con tramos que se dibujan (DrawSVG), uno por fila | `tramos[]` (`nombre`, `desde`, `hasta`) |

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
- **Paletas (H10, HITO3.md)**: `assets/escenas/paletas/{noche,utn,navy,papel}.json` traen cada
  una el set completo de `colores` (`fondo`, `superficie`, `borde`, `texto`, `tenue`, `acento`).
  `noche` es la de siempre (fondo oscuro, acento ámbar); `utn` es la institucional de TUPaD
  (fondo blanco, acento naranja `NARANJA` de `presentaciones/references/estilo.md`); `navy` es
  la misma paleta UTN en oscuro (fondo navy, texto claro, acento celeste); `papel` es un claro
  neutro cálido (fondo crema, acento terracota). El guion elige con `"paleta": "utn"` arriba del
  todo (`guion/vNN.json`); precedencia default `noche` < paleta elegida < `brand.json` del
  proyecto (cada capa pisa sólo lo que declara, `escena.cargar_brand(ruta, paleta=...)`). Una
  paleta que no existe aborta `editar.py imagen` listando las que hay, antes de generar nada.
  Las paletas de fondo claro pasan la misma puerta de contraste (WCAG) que `noche`: el
  resaltado de código (derivado del acento por rotación oklch, `codigo.html`), las transiciones
  (`color_de` de `transiciones.py` ya sale del brand, no de un negro fijo) y el recoloreado de
  SVG por `currentColor` se verificaron en las 4 (`tests/test_tipografia.py`,
  `tests/test_escena_codigo_render.py`).
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
    con la salida **real** (se ejecuta al armar el spec, desde una carpeta neutra, sin rutas del
    home); con `contar`, el último número de cada renglón cuenta hasta su valor. El intérprete
    sale de la extensión y la terminal muestra ese comando: `.py` → `$ python3 x.py`, `.js`/
    `.mjs`/`.cjs` → `$ node x.js`, `.ts`/`.mts` → `$ npx tsx x.ts` (usa el `tsx` del
    `node_modules` del proyecto, nunca baja nada de la red: sin él, falla diciendo
    `npm i -D tsx`). `node_modules` no se copia a la carpeta neutra, se enlaza. Otra extensión
    falla nombrándola.
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
- **Escenas `pila` y `arbol`** (H4: recursión que se ve). No se inventa qué pasos tiene la
  recursión: se EJECUTA la función de verdad con `presentaciones/scripts/diagramas.trazar`
  (reusado, `recursion.py` arma el spec final en Python antes de abrir Chrome) y el dibujo sale
  de ese registro. Los comandos de escenas que los usan llevan `--with matplotlib` (lo pide
  `diagramas.py`, aunque la escena nunca abre una figura).
  ```json
  {"tipo": "pila", "archivo": "codigo/factorial.py", "llamada": "factorial(4)",
   "titulo": {"texto": "Cómo se desarma factorial(4)"},
   "pasos": [{"cue": "factorial de cuatro"}, {"cue": "factorial de tres"}, {"cue": "factorial de dos"},
             {"cue": "factorial de uno"}, {"cue": "y de cero"}, {"cue": "que es uno"},
             {"cue": "listo, vuelve"}, {"cue": "y vuelve"}, {"cue": "y vuelve"}, {"cue": "y llega a veinticuatro"}]}
  ```
  ```json
  {"tipo": "arbol", "archivo": "codigo/fibonacci.py", "llamada": "fibonacci(5)", "formato": "fib({n})",
   "titulo": {"texto": "Cuánto se repite fibonacci(5)"},
   "pasos": [{"cue": "fibonacci de cinco"}, {"cue": "necesita fibonacci de cuatro"}, {"cue": "y de tres"}]}
  ```
  (`fibonacci(5)` llama 15 veces: `pasos` necesita 15 elementos, uno por llamada; el ejemplo
  recorta las últimas 12 por espacio)
  - `pila`: un `paso` por cada evento de la traza, EN EL ORDEN EN QUE OCURREN (llamada y
    retorno intercalados: ver `diagramas.trazar`); pensada para recursión LINEAL, de una sola
    rama (si dos llamadas conviven a la misma profundidad se pisan: no es su caso de uso). Cada
    marco se apila en la cue de su llamada y, poco después de la cue de su retorno, se desapila
    mostrando "vuelve con `<valor>`"; el más profundo siempre sale primero (LIFO real, no
    forzado). Más de 16 llamadas falla nombrando la cantidad. El marco ocupa casi todo el ancho
    del cuadro (no un ancho fijo chico) y su texto es tan grande como entra en la fila que le
    toca (H5 ronda 2). Al desapilar el último marco no queda en blanco: entra grande, centrado,
    el resultado de la raíz (`"<llamada> = <valor>"`, p.ej. `"factorial(4) = 24"`).
  - `arbol`: un `paso` por cada LLAMADA (no por retorno: el árbol nunca se achica). Las
    posiciones (profundidad, orden entre hermanos) salen del árbol completo, pero cada nodo sólo
    se ve desde SU cue. Una llamada con los mismos argumentos que una anterior ("trabajo que se
    recalcula") entra directo resaltada en el acento, sin paso extra. Más de 60 llamadas falla
    nombrando la cantidad; un texto que no entra en los nodos, también. El nodo usa todo el ancho
    de su columna (sin tope fijo chico) y su texto es tan grande como entra: con pocas hojas
    (árboles chicos) se ve bastante más grande que con muchas (H5 ronda 2).
  - `formato` (ambas, opcional): mismo mini-lenguaje que `diagramas.py` (`"fib({n})"`); sin él,
    `"n = 4"` (los argumentos tal cual, repr de Python).
  - El `archivo` es relativo a `TUT_ROOT` desde un guion (`editar.py` lo resuelve igual que el de
    `codigo`); desde una prueba suelta, relativo al directorio del spec.
- **Escena `curva`**: una curva que SE DIBUJA (GSAP DrawSVG) con un contador que la acompaña
  (`contador.js`, H4) y puntos marcados con su valor. El trazo avanza (ease-out) entre la cue del
  primer punto y la del último; el número grande cuenta del valor del primero al del último en
  esa misma ventana. Caso de referencia (la comparativa con HyperFrames, HITO3.md):
  ```json
  {"tipo": "curva", "titulo": {"texto": "US$ 1.000 a treinta años"}, "prefijo": "US$ ",
   "puntos": [{"x": 0, "y": 1000, "etiqueta": "Año 0", "cue": "mil dólares"},
              {"x": 10, "y": 2594, "etiqueta": "Año 10", "cue": "a los diez años"},
              {"x": 30, "y": 17449, "etiqueta": "Año 30", "cue": "treinta años después"}]}
  ```
  Cada punto entra (con su etiqueta y su valor) en SU PROPIA cue, no cuando el trazo lo alcanza
  píxel a píxel: una cue que no es proporcional a la posición en `x` hace que la etiqueta
  aparezca un poco antes o después del trazo real. Menos de dos puntos falla claro.
  - **Curva suave con pocos puntos** (H5 ronda 2, HITO3.md): con sólo 2-3 `puntos` el trazo entre
    ellos es una recta (el interés compuesto se ve como "dos rectas", no una curva). Si el spec
    trae `"crecimiento": {"inicial": 1000, "tasa": 0.10, "periodos": 30}` (interés compuesto:
    `inicial * (1 + tasa) ^ x`), el TRAZO se arma con muchos segmentos interpolados de la fórmula
    (12 por período); `puntos` sigue siendo sólo lo que se marca (etiqueta, cue, el valor que
    cuenta) — nunca entra una marca por segmento de la curva, sólo las nombradas. Sin
    `crecimiento`, el trazo sigue uniendo los `puntos` con rectas (si ya vienen muchos puntos, el
    resultado ya se ve suave sin hacer nada extra).
- **Escena `linea-de-vida`**: un eje de años/edades con un tramo por fila que SE DIBUJA (GSAP
  DrawSVG) en su propia cue, con marcas en cada edad que aparece en algún tramo.
  ```json
  {"tipo": "linea-de-vida", "titulo": {"texto": "Diez años de diferencia"},
   "tramos": [{"nombre": "Ana", "desde": 25, "hasta": 35, "cue": "ana ahorra diez años"},
              {"nombre": "Sofía", "desde": 35, "hasta": 65, "cue": "sofía treinta años"}]}
  ```
  `eje` (opcional: `{"desde": ..., "hasta": ..., "unidad": "años"}`) fuerza el rango; sin él, sale
  del mínimo/máximo de los tramos. `hasta <= desde` (en el eje o en un tramo) falla claro, igual
  que más tramos de los que entran legibles en una columna. La fila de cada tramo llena el alto
  disponible entre tramos (con pocos tramos, mucho más alta que con muchos): el trazo es grueso,
  mínimo 24 px, y el nombre al lado va grande; las marcas del eje, en mono, nunca por debajo de
  24 px (H5 ronda 2).
- **`presentacion`: "marcar" resalta una palabra** (H6, HITO3.md). `"marcar":
  [{"texto": "memoización", "como": "subrayado|circulo|resaltado", "cue": "..."}]` busca esa
  palabra (completa, sin mirar mayúsculas) en el texto YA armado de la escena (título, un
  punto o el subtítulo) y dibuja la marca sobre su caja real en su cue: `subrayado` (una
  curva bajo la palabra), `circulo` (una elipse alrededor) o `resaltado` (una pasada gruesa
  y translúcida por el medio, como un marcador). Se dibuja con `stroke-dasharray`/
  `stroke-dashoffset` en función de `t` (la misma técnica de la escena `imagen`, nunca
  GSAP). `como` inválido o la palabra no encontrada falla claro, antes de renderizar.
  Idea (no código) de `hw-underline`/`hw-callout-circle`/`mk-callout-highlight` de
  HyperFrames (Apache 2.0).
  ```json
  {"tipo": "presentacion", "titulo": {"texto": "Programación dinámica", "cue": 0},
   "puntos": [{"texto": "Guardamos cada resultado en memoización", "cue": "guardamos"}],
   "marcar": [{"texto": "memoización", "como": "subrayado", "cue": "memoización"}]}
  ```
- **`presentacion`: texto cinético con `"entrada": "palabras"`** en `titulo` (H6, HITO3.md).
  `{"titulo": {"texto": "...", "cue": 0, "entrada": "palabras"}}` parte el título con GSAP
  SplitText (no el split manual de `cabecera()` de `base.js`) y cada palabra sube con
  resorte (`back.out`), de a una, en vez de la entrada default. Sin `"entrada"`, sigue el
  camino actual sin cambios. La timeline de GSAP corre en pausa (`gsap.globalTimeline.pause()`)
  y se scrubea a mano en `dibujar(t)`, igual de determinista que el resto de la escena.
- **Rótulo (lower-third), capa sobre CUALQUIER tramo** (H6, HITO3.md): no es un `tipo` de
  escena ni un segmento aparte. `"rotulo": {"titulo": "Memoización", "subtitulo": "Unidad
  10 · Programación I", "cue": "...", "dura": 4}` va en el segmento, junto a su contenido
  normal (pantalla grabada, diapositiva o escena). Entra con el título subiendo con resorte
  y una barra de acento que se dibuja (GSAP, `scaleX`); sale limpio antes de que termine
  `dura`. Va arriba de la banda de subtítulos, alineado a la izquierda (x=140px, el mismo
  margen que `.cabecera`), para no chocar nunca con los subtítulos. Se renderiza aparte con
  canal alfa real (`escena.render(..., alpha=True)`: qtrle, sin pix_fmt forzado) y se compone
  con `overlay` de ffmpeg ENCIMA del tramo ya armado del segmento (ver
  `references/guion-y-edicion.md` → "Rótulo"): G1 (cuadros) y G4 (códec) quedan intactos, y
  sin `"rotulo"` en el segmento no se toca nada (G3). Idea (no código) de
  `lt-kicker-name`/`lt-accent-underline` de HyperFrames (Apache 2.0).
  ```json
  {"inicio": 12.0, "fin": 28.0, "rotulo": {"titulo": "Memoización",
   "subtitulo": "Unidad 10 · Programación I", "cue": "memoización", "dura": 4}}
  ```
- **Cero WebGL**: el motor bloquea `getContext('webgl'|'webgl2'|'experimental-webgl')` en
  cualquier plantilla (la GPU integrada de Juani la arrastra, PLAN.md); si una lo llama, sale
  como `ContratoError`, igual que cualquier otro error de JavaScript de la página.
- **Plantilla propia**: un HTML con `window.DURATION` y `async window.seek(t)` donde todo es
  función pura de `t` (sin `Date.now`, timers, `requestAnimationFrame` ni transiciones CSS).
  `escena.py render` falla claro si falta el contrato o si el JS tira un error.
- **La puerta antes del render** (contraste, superposición, texto chico, elementos fuera de cue)
  corre en `verificar.py`: ver `references/verificacion.md`.
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

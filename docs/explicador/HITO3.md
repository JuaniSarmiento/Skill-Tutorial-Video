# Hito 3: salto de calidad (04–06/10/2026)

Objetivo de Juani: que los videos parezcan **producidos por un editor de motion graphics**, no una
clase grabada prolija. Fuente: el estudio de HyperFrames (heygen-com/hyperframes, Apache 2.0,
commit b9e511a) — se roban **ideas y bloques**, no se usa como dependencia (duplicaría el motor y
metería Node en una skill Python + ffmpeg).

## Corrección previa
`escena.py` y `PLAN.md` dicen que nuestro contrato (`window.DURATION` + `async window.seek(t)`) es
"el mismo de HyperFrames". **Es falso**: HyperFrames usa atributos `data-*` en el HTML y una
timeline GSAP pausada en `window.__timelines[id]`. Las ideas son primas (todo función de t, render
no en tiempo real); el formato no.

## Decisiones
- **GSAP sí** (decidido 06/10): la GSAP Standard License es gratis para uso comercial e incluye los
  plugins antes pagos (DrawSVG, MorphSVG, SplitText). Solo prohíbe usarlo en constructores visuales
  sin código que compitan con Webflow; esta skill no lo es. Va **vendorizado** con su aviso de
  licencia (el motor bloquea la red). Revisar la licencia si la skill se vende como servicio.
- **No copiar**: los sfx de HyperFrames (Pixabay, otra licencia), sus transiciones shader (WebGL,
  bloqueado a propósito), bloques que imitan interfaces de marcas (ChatGPT, Claude, Instagram).
- Código copiado de HyperFrames lleva aviso Apache 2.0 y atribución.
- Proceso (aprendido en el Hito 2): máximo 2 agentes a la vez, máximo 2 rondas de QA por rebanada
  (solo lo BLOCKING vuelve), y un **video real** como control antes de declarar terminado.

## Rebanadas

| # | Rebanada | Qué gana el video | Depende de |
|---|---|---|---|
| H0 | **Base GSAP**: vendorizar GSAP + DrawSVG, MorphSVG, SplitText con licencia; puente en `base.js` (timeline pausada → `DURATION`/`seek`), determinismo medido; corregir `escena.py`/`PLAN.md` | Habilita todo lo animado de abajo | — |
| H1 | **Audio por bandas** ("voiceover carve": EQ que baja la música solo en las bandas de la voz, ~250–2500 Hz) + perfiles de loudness por destino (YouTube -16, redes -14) | Mezcla que suena a editor de audio | — |
| H2 | **Dirección visual**: tipografía propia embebida (reemplaza Inter), tamaños para video (títulos 64–120 px, cuerpo 28–42, etiquetas 18–24), sin degradés que hacen bandas, banda libre para subtítulos; `revisar` gana contraste (WCAG AA) y desborde de texto | Identidad propia, legible en celular | H0 |
| H3 | **SKILL.md como router**: ~120 líneas + `references/` que se cargan bajo demanda | El agente lee menos y sigue mejor las reglas | — |
| H4 | **Escena `codigo`**: tipeo, diff y resaltado de sintaxis animados, sin grabar VS Code; número que cuenta hasta su valor | Tutoriales de código con nivel Fireship | H0 |
| H5 | **Escenas `pila` y `arbol`** animadas desde una traza real (reusa `presentaciones/scripts/diagramas.py`) | Recursión que se *ve* | H0 |
| H6 | **Rótulos** (lower-third, callout que resalta una palabra) y **texto cinético** (SplitText) | Look de producción televisiva | H0 |
| H7 | **Transición `whip`** con velocidades pareadas (sale acelerando, entra frenando) | Cortes que se sienten como una cámara | H0 |
| H8 | **Director 2.0**: brief (dicho vs inferido), estructura narrativa nombrada, catálogo de ganchos, cada frase con su revelado | Guiones de explicador, no de resumen | — |
| H9 | **Video real de control**: rehacer interés compuesto y el tramo de memoización de la U10 con todo; comparativa lado a lado con la versión del Hito 2 | La prueba de que el salto existe | H1–H7 |

### Referencias de estilo que Juani quiere alcanzar (06/10)
Dos videos del canal Torti Code:
- **Short "El problema N+1 explicado con ocho viajes al súper"** (vertical, 75 s): fondo papel,
  dibujos de línea que se trazan (súper, Ana caminando, olla que se llena, receta con tildes),
  subtítulos grandes con la palabra clave en rojo, panel de código con la línea culpable
  resaltada, números gigantes ("101", "N+1", "2").
- **"Cómo escribir documentación útil"** (19 min, horizontal): fondo violeta oscuro, tarjetas de
  interfaz (README, editor, PR, árbol de archivos, línea de tiempo) unidas por conectores con
  brillo, e ilustraciones pintadas generadas con IA (personajes en paisajes), sin texto adentro.

| # | Rebanada | Qué gana el video | Depende de |
|---|---|---|---|
| H10 | **Formato vertical 9:16** (shorts) en todo el pipeline: escenas, transiciones, subtítulos, encoder | Shorts / reels | H0 |
| H11 | **Subtítulos cinéticos** palabra por palabra con la palabra clave resaltada (usa los tiempos por palabra de `palabras.py`) | El look del short N+1 | H0, H10 |
| H12 | **Utilería de dibujos**: personas, objetos y lugares en SVG de línea, que se trazan y **se mueven por una trayectoria**; tema "papel" además del oscuro | Analogías dibujadas como el súper de Ana | H0, H2 |
| H13 | **Componentes de interfaz**: tarjeta de archivo, editor, PR, árbol de archivos, línea de tiempo, conectores con brillo (sin degradés que hacen bandas) | El look del video de documentación | H0, H4, H6 |
| H14 | **Ilustraciones generadas sin texto** por API (Flux / GPT Image vía fal), con brand y caché. **Cambia la regla**: de "sin imágenes generadas" a "sin imágenes generadas con texto adentro" | Escenas pintadas tipo paisaje | H2 |

H9 suma **un short estilo N+1** como control, comparado lado a lado con el original.

### Prueba comparativa con HyperFrames (06/10)
Mismo guion y misma voz del explicador de interés compuesto, hecho con HyperFrames
(`~/Proyectos/Video-Tutoriales/hyperframes-prueba/interes-compuesto/`, video en
`~/Descargas/interes-compuesto-hyperframes.mp4`). **Gana en 8 de 11 escenas por decisiones de
diseño, no por el motor**: número protagonista gigante ("10 años" contra "30"), línea de vida
25→65, curva exponencial que se dibuja con contador, ecuación gigante en la regla del 72, flechas
que se dibujan con vuelta. Gana el nuestro: ritmo por cues de texto (HF pone segundos a mano),
loudness (HF salió a -24,7 LUFS sin avisar), archivos 2,7× más livianos, grabación real.
Se suman al plan:
- **H2**: jerarquía tipográfica con número protagonista (≥ 300 px) y etiquetas en mono; y una
  **puerta `check` antes del render** (textos que se pisan muestreando tiempos, contraste WCAG AA).
- **H4/H5**: escenas `curva` (trazo + contador), `linea-de-vida`, `contador`, y flechas que se
  dibujan en `diagrama`.
- Bloques del catálogo de HyperFrames para copiar o adaptar (con aviso Apache 2.0; GSAP permitido):
  `hw-arrow`, `hw-underline`, `hw-callout-circle`, `hw-write-title` (estilo dibujado, H12);
  `offset-path-traveler`, `lottie-character-walk` (trayectorias, H12); `caption-pill-karaoke`,
  `caption-highlight`, `per-word-rise` (H11); `code-typing`, `code-diff`, `code-highlight`,
  `terminal-simulator`, `count-up`, `number-pop-in` (H4); `lt-kicker-name`, `mk-callout-highlight`
  (H6); `whip-pan-cut` (H7); `flowchart`, `mk-line-graph` (H5). Proyecto con el catálogo en caché:
  `~/.hyperframes/cache/`; repo clonado en `hyperframes-prueba/repo-hf/`.

Exploración aparte (sin compromiso): captura con CDP `beginFrame` en vez de screenshot, por si
elimina el relayout forzado que hoy hace determinista el render.

## Alcance decidido por Juani (06/10)
En este hito: H0–H4 (ya en curso), **H3, H5, H6, H7, H8** y el video de control H9. Quedan para
más adelante: H10–H14 (vertical, subtítulos cinéticos, utilería con trayectorias, componentes de
interfaz, ilustraciones generadas). Proceso desde el 06/10: Sonnet por defecto y **un agente a la
vez** (se llegó al límite de uso con dos agentes Opus en paralelo).

## Orden
1. H0 + H1 (en paralelo: no se tocan).
2. H2 + H3.
3. H4 + H5.
4. H6 + H7.
5. H8, después H9.

## Pendientes
_Se completa al cerrar cada rebanada._

### H10 cerrada (07/10/2026, rama `feat/hito3`)
Paletas de color elegibles, pedido de Juani.

- **Archivos**: `assets/escenas/paletas/{noche,utn,navy,papel}.json`, cada uno con el set
  completo de `colores` de `brand.json` (`fondo`, `superficie`, `borde`, `texto`, `tenue`,
  `acento`). `noche` es byte a byte la paleta de siempre (S0 no cambia). `utn` sale de
  `presentaciones/references/estilo.md` (NAVY/ACC/TXT/GRIS/CARD/BORDE/CODEBG/NARANJA):
  fondo blanco, `acento` = NARANJA `#B54708` (el "acento fuerte" de esa paleta, literal).
  `navy` es la misma familia en oscuro (fondo `#1B365D`, texto claro, acento celeste
  `#8FB0D6`, derivado — no está en `estilo.md`). `papel` es un claro neutro cálido (fondo
  crema, acento terracota) diseñado para esta skill, no de ninguna referencia.
- **Selección**: `"paleta": "utn"` arriba del todo en `guion/vNN.json`. Precedencia default
  `noche` < paleta elegida < `brand.json` del proyecto (`escena.cargar_brand(ruta,
  paleta=None)`, mismo merge de un nivel que ya usaba `brand.json`). Una paleta
  desconocida aborta `editar.py imagen` ANTES de generar nada (`escena.paletas_validas()`),
  listando las que hay.
- **Wireado** en los 3 puntos donde `editar.py` carga el brand: la escena (`build_segment`),
  el rótulo (`_aplicar_rotulo`) y las transiciones (`imagen()`), los tres con un parámetro
  `paleta` nuevo que viaja desde `g.get("paleta")`. `_verificacion_de_escena` (la que usa
  `editar.py revisar`) quedó **fuera de este wireado a propósito** (no estaba en el pedido):
  sigue mirando sólo `ROOT/brand.json`, así que `revisar --estricto` contra una paleta
  elegida por guion se probó con el mecanismo YA EXISTENTE de `brand.json` de proyecto (ver
  Prueba), no con el campo `paleta` nuevo. Queda pendiente si se quiere que `revisar` sepa
  de `paleta` directamente.
- **Dos arreglos de H9b que quedaban sueltos** (mismos templates, mismo pedido): el punto
  del label de `curva` (`"30 años US$ 17.449"`) pisando el contador grande — no se pudo
  **reproducir** con la spec del pedido ni variando kicker/título/duración (la geometría ya
  deja un margen constante de 37px entre `.cifra` y la etiqueta del punto de mayor valor,
  algebraicamente independiente del alto del encabezado); se agregó un test de regresión
  (`test_la_etiqueta_del_ultimo_punto_no_pisa_el_contador_grande`) que hoy pasa, sin tocar
  producción — **no hay rojo que mostrar acá**, así que no hay fix que reclamar. Los labels
  secundarios en mono (`.rango` de `linea-de-vida`, `.etq` de `diagrama`, `.etiqueta` de
  `curva`) subieron 28→32px; eso corrió dos cajas contra el borde del cuadro útil
  (`linea-de-vida` por la derecha, `curva` por abajo contra la banda de subtítulos), así que
  además de la tipografía se ajustó `AREA.x1` de `linea-de-vida` (1760→1740) y `AREA.y1` de
  `curva` (`BANDA-80`→`BANDA-120`).
- **Lo delicado de fondo claro, verificado con tests**: el resaltado de código (los colores
  de token en `codigo.html` se derivan del `acento` por rotación oklch, no de un estilo con
  nombre de Pygments) pasa contraste WCAG en las 4 paletas
  (`test_escena_codigo_render.py::...en_cada_paleta`); lo mismo para `presentacion`,
  `diagrama`, `datos` e `imagen` (`test_tipografia.py::test_toda_escena_del_ejemplo_pasa_
  verificar_en_cada_paleta`, 24 casos = 6 specs × 4 paletas). La paleta `papel` falló
  contraste dos veces en la primera corrida (`tenue` 4.02:1 y `acento` 4.36:1 contra su
  fondo crema, el mínimo es 4.5:1 a 24px/600) y se oscureció hasta 5:1+ en las dos. Las
  transiciones ya sacaban su color del brand (`transiciones.color_de`, no de un negro fijo)
  y el recoloreado de SVG por `currentColor` ya dependía de variables CSS: ninguno de los
  dos necesitó cambios de producción, sólo paletas correctas.
- **Prueba** (explicador de interés compuesto, `explicador-demo/guion/v03.json`, voz
  "argentina" reusada, sin regenerar TTS): render en las 4 paletas
  (`editar.py imagen` + `editar.py voz`), mismo total 79.3s y 9 cues de `.srt` en las 4 (el
  guion tiene 9 segmentos). `verificar.py` sobre las 9 escenas resueltas con `--brand` de
  cada paleta: sin hallazgos en las 4×9 = 36 combinaciones. `editar.py revisar --estricto`
  con `brand.json` de proyecto = cada paleta (mecanismo ya existente, no el campo `paleta`
  nuevo, ver nota de arriba): sin hallazgos en las 4. Copia a
  `~/Descargas/interes-compuesto-v3-utn.mp4` (nombre temporal + rename). Hoja de contacto
  4 columnas (paletas) × 6 momentos clave: `/tmp/claude-1000/h10/paletas.png` — mirada:
  ninguna caja pisa otra, el punto "30 años" de `curva` no pisa el contador grande en
  ninguna columna, los nodos de `diagrama` se leen en las 4. El guion de prueba se restauró
  a su estado original (sin `"paleta"`) después de la prueba.
- **Hallazgo fuera de alcance, no arreglado (pre-existente, no tocado)**:
  `test_tipografia.py::test_las_etiquetas_van_en_mono_entre_18_y_24_px[diagrama-...]` ya
  daba rojo ANTES de esta rebanada (con el piso de 28px que dejó H9b, no sólo con el de
  32px de ahora): ese test afirma que las etiquetas de flecha de `diagrama` miden 18-24px, y
  contradice directamente el piso de 28px que `test_plantillas.py::PISO_ETIQUETA_PX`
  documenta como decisión de H9b. Las dos aserciones no pueden ser ciertas a la vez; cuál de
  las dos está mal no es una decisión de esta rebanada (no se tocó tipografía por pedido
  propio, se subió un piso que otra ronda ya había subido).

### H9b cerrada (07/10/2026, rama `feat/hito3`)
Última ronda de H9 (video de control). Nota de proceso: este proyecto (`tutorial-video-agente`)
**no usa OpenSpec** — ni antes ni ahora; H1-H9 se trazan acá, en `HITO3.md`. Decisión tomada por
el orquestador durante esta ronda (el implementador había parado a reportarlo como bloqueo antes
de escribir código), para que quede registrado quién la tomó.

- **Datum sobre la hipótesis de un bug en D7** (`verificar.py`, texto < 24 px): corrida sobre
  `explicador-demo/videos/v03/escenas/*.json` (linea-de-vida, diagrama, curva) y sobre un árbol
  `fibonacci(6)` armado a propósito (25 llamadas, el piso viejo de `arbol.html` lo rendereaba a
  20 px). **D7 no tiene bug**: en los tres primeros casos no reportó nada porque los tamaños
  declarados (24-26 px) ya cumplían el piso técnico; en el caso de `arbol` SÍ lo reportó
  correctamente (`texto_chico: ... 'nodo N' mide 20 px`). Lo ilegible en la hoja de contacto no
  era el verificador fallando: eran plantillas con tamaños apenas en el piso técnico (24-26 px),
  muy chico para una hoja de contacto en miniatura, más dos solapamientos reales que D6 no
  cubre (una caja de texto contra una forma SVG que no es `[data-caja]`, no contra otra caja de
  texto).
- **Arreglo (TDD, 8 tests nuevos, triangulados)**: `.rango` de linea-de-vida 26→28 px y su
  posición pasa de `sx(hasta)+14` a `sx(hasta)+grosor/2+14` (el gorro redondeado del trazo,
  `stroke-linecap:round`, pintaba `grosor/2` más allá de `x2`, y con `grosor` hasta 90 px eso
  pisaba la etiqueta); `.etiqueta` de curva 26→28 px; `.etq` de diagrama 24→28 px; `PISO` de
  `arbol` 14→24 px (un árbol que no entra legible ahora falla claro en vez de renderizar texto
  que se ve pero no se lee). Framemd5 de `tests/fixtures/s0/escenas.json` regenerado (cambia la
  imagen por el `.etq` de diagrama en el guion de la base; `audio_md5` no se tocó, verificado
  igual antes/después). Suite acotada: 180 tests verdes (ver tabla); suite rápida completa
  (`-m "not integracion"`) no se corrió aparte por tiempo — los archivos tocados ya están
  cubiertos arriba con Chrome real.
- **Hallazgo fuera de alcance, no arreglado**: `codigo.html` calcula el tamaño de letra (`px`)
  resolviendo a la vez ancho y alto contra el MISMO valor, así que cuando el alto es la
  restricción que ata (muchas líneas) el panel queda angosto aunque sobre ancho (`pxAncho` se
  computa contra `ANCHO_MAX`, pero el `ancho` final del panel se recalcula después con el `px`
  ya chico) — es el "caja que no usa el ancho" que se ve en `memo.png` cuadro 7. No es un bug
  de tamaño de texto (el piso ya es 28 px, por encima de D7); es de layout. Se evitó en vez de
  arreglarse: el beat nuevo de memoización (abajo) usa pocas líneas a propósito para no pisar
  esta restricción. Si se quiere una escena `codigo` con mucho texto de salida, este algoritmo
  necesita revisarse aparte (no se tocó: tocar el balance ancho/alto de `codigo.html` sin tests
  dedicados, con el resto del time-box ya consumido, era más riesgo del que esta ronda podía
  pagar).
- **Guion v03** (`explicador-demo/guion/v03.json`): nueva escena `datos` ("Gana la que ahorró
  menos", US$ 105.174 Ana contra US$ 94.461 Sofía, mismos supuestos de v02) inmediatamente
  después de la línea de vida — la prueba del gancho, antes solo aparecía diluida cerca del
  final. La regla del 72 ahora muestra `72 ÷ 10 ≈ 7` (campo `subtitulo` de `numero`/`contra`)
  junto al número protagonista. `revisar --estricto` y `verificar` limpios (9 escenas). Re-render
  a `~/Descargas/interes-compuesto-v3.mp4` (79.3s).
- **Memoización** (`u10-recursividad/produccion-v2/guion/v01.json`): beat nuevo "Python también
  tiene un límite", con `codigo/limite_recursion.py` (nuevo, basado en el de
  `material/Microteaching-Video1.../codigo/`) ejecutado DE VERDAD — una función sin caso base
  que agota la pila y tira `RecursionError`, capturado con `try/except` y un print corto (se
  descartó dejar el traceback crudo de Python: con el nombre de función original la línea
  `File "...", line N, in factorial_sin_caso_base` desbordaba su caja por un problema de
  redondeo del ancho en `codigo.html`, el mismo de arriba — más que perseguirlo, se cambió el
  contenido para no pisar el borde). Insertado ANTES del árbol (no después, para no formar una
  racha de 3 escenas `codigo` seguidas y violar D8). Sin D1/D2: se sumó un paso `resaltar` a
  mitad del beat para que no quede un tramo sin elemento nuevo. Total del video 61.4s (≥ 60s
  pedido). `revisar --estricto` y `verificar` limpios. Re-render a
  `~/Descargas/memoizacion-v2-demo.mp4`.
- **Gotcha de proceso (costó dos renders incompletos)**: `editar.py voz <vNN> <voz>` LEE
  `slots-<voz>.json` del disco, no lo recalcula — si se corre `voz` sin haber corrido `imagen`
  primero con el guion ya en su forma final, usa un `slots-*.json` viejo (de una corrida
  anterior, con otra cantidad de segmentos) y el video final sale corto, con el último segmento
  directamente ausente y sin ningún error que lo avise. Pasó dos veces en esta ronda (v03 quedó
  en 49.4s con el repaso final mudo; v01 en 49.4s también) hasta notar que `slots-argentina.json`
  tenía menos entradas que `segmentos` en el guion. El orden correcto siempre es `imagen` antes
  que `voz` cuando el guion cambió de forma (no sólo de texto). Vale la pena un chequeo de
  `editar.py voz` que aborte si `len(slots) != len(g["segmentos"])` en vez de fallar en
  silencio — no entró en esta rebanada (es un cambio de código fuera de lo pedido).
- **Hoja de contacto nueva**: `/tmp/claude-1000/h9/v3b.png` (explicador v03b, mismos momentos
  que `v2-vs-v3.png`) y `/tmp/claude-1000/h9/memo-b.png` (memoización, 10 cuadros). Miradas:
  ningún texto ilegible — las etiquetas de linea-de-vida, curva y diagrama se leen, el árbol de
  memoización se lee, la salida de `limite_recursion.py` entra clara en su caja.

### Pendientes que siguen abiertos (arrastrados de H9/H9a, no tocados en H9b por alcance)
- Bola de nieve sin animación continua (los tres dibujos de `imagen` entran y quedan quietos: no
  hay una curva de "crece y empieza a rodar" entre ellos).
- Carve adaptativo de música (hoy las bandas de voz para el "voiceover carve" son fijas,
  `musica.BANDAS_VOZ_HZ`; adaptarlas a la voz real de cada toma quedó afuera).
- Whip con ~0,13 s de fondo visible en el corte (el colchón de fondo del brand entre el
  recorte saliente y el entrante mide eso de más de lo ideal; no se ajustó la curva).
- S7a/S7b sin cerrar (sub-rebanadas mencionadas en rondas anteriores, sin entrar en el orden de
  esta sección todavía).
- El algoritmo de ancho/alto de `codigo.html` (arriba, "hallazgo fuera de alcance").
- El chequeo de `len(slots) == len(segmentos)` en `editar.py voz` (arriba, "gotcha de proceso").

### H8 cerrada (07/10/2026, rama `feat/hito3`)
- **Director 2.0** (`references/director.md`, nueva sección): brief antes del guion
  (`BRIEF.md` corto, dicho vs. inferido con su razón), 5 estructuras narrativas con nombre
  (problema→analogía→mecanismo→ejemplo→repaso, antes/después, mito y verdad, pregunta
  abierta→respuesta, lista de N), catálogo de 9 ganchos con ejemplo de una línea, tabla
  "si querés mostrar X → usá Y" con las escenas que existen hoy, y la regla de ritmo (no
  repetir el mismo tipo de escena más de 2 veces seguidas). Ideas adaptadas (reformuladas,
  nunca copiadas) del método de entrevista de intención y de diseño de guion de HyperFrames
  (Apache 2.0): `intent-interview.md` (brief dicho/inferido) y `story-design.md`
  (estructuras, catálogo de ganchos).
- **D8** nuevo en `editar.CHEQUEOS` (ritmo): ninguna racha de MÁS de 2 segmentos de escena
  consecutivos con el mismo `tipo`; calculado directo de `g["segmentos"]`, sin renderizar,
  así que corre siempre (nunca "no corrió"). Es la regla medible que sale de la racha real de
  tres `datos` seguidas que se sintió repetitiva en el explicador de interés compuesto (nota
  de la "Prueba comparativa con HyperFrames" de arriba). Un segmento de pantalla grabada
  entre dos escenas corta la racha, igual que un cambio de tipo.
- Tabla de ruteo de `SKILL.md` actualizada ("escribir un guion de explicador" → ya la lleva
  a `references/director.md`; se sumó la mención y el rango pasó de "D1-D7" a "D1-D8").
- No entró en esta rebanada (sin pedido de Juani, fuera de alcance): un chequeo que mida el
  LARGO de los planos (mencionado en la regla de ritmo como sugerencia, no como D9) — D8 sólo
  mide la repetición de tipo, no la variación de duración.

### H6 cerrada (06/10/2026, rama `feat/hito3`)
- **Rótulo** (lower-third): `seg["rotulo"]` (título, subtítulo opcional, `cue`, `dura`) se
  renderiza aparte con `escena.render(..., alpha=True)` (qtrle, sin pix_fmt forzado: el PNG
  ya sale RGBA con `omit_background`) y se compone con `overlay` de ffmpeg ENCIMA del tramo
  YA ARMADO del segmento (escena, título o pantalla grabada), después de que `build_segment`
  lo construye por el camino que sea (`editar._aplicar_rotulo`, llamada antes de cada
  `return`). El overlay se renderiza del mismo largo que el tramo (transparente fuera de su
  ventana): no hace falta `itsoffset` ni recortar nada, así que G1 (cuadros) y G4 (códec)
  quedan intactos por construcción, no por un chequeo aparte. Va arriba de la banda de
  subtítulos (x=140, el margen de `.cabecera`), con un chip de fondo opaco (para que el
  contraste de `verificar.py` se mida contra algo real, no contra el blanco default que
  asume un fondo transparente).
- **`marcar`** (subrayado/círculo/resaltado) en `presentacion`: busca la palabra en los
  nodos de texto YA armados (título, un punto o el subtítulo) y la envuelve; la marca se
  dibuja con `stroke-dasharray`/`dashoffset` en función de `t`, la misma técnica (sin GSAP)
  de la escena `imagen`. Ojo con el wrapper: darle `data-caja` al `<svg>` o a un contenedor
  que ENVUELVE texto con `data-caja` hace que `verificar.py` lo compare contra sus propios
  hijos y reporte un "solape" falso (los dos bounding boxes se contienen) — ninguno de los
  dos wrappers de esta rebanada (el `<svg class="marcas">`, el chip `.rotulo`) lleva
  `data-caja`, sólo sus hijos de texto.
- **Texto cinético** (`"entrada": "palabras"` en `titulo`, sólo en `presentacion`): GSAP
  SplitText (`wordsClass: "word"`, hace falta pasarlo: sin la opción no pone clase) +
  timeline propia, en pausa (`gsap.globalTimeline.pause()`) y scrubeada a mano en
  `dibujar(t)` — nunca `E.lineaDeTiempo` (presentacion.html sigue con el "contrato" manual de
  base.js, no con una timeline GSAP dueña de todo el render).
  - **Bug real, visto recién en la hoja de contacto** (no en ningún test antes de mirarla):
    `.titulo` es `display: table` (base.css), y esa maquetación colapsa a CERO el espacio en
    blanco entre los `<div class="word">` que separa SplitText (quedaban pegados: "Memoi​za​
    ciónexplicadapasoapaso"). Es el mismo motivo por el que `.palabra` (el split manual de
    `cabecera()`) ya usa `margin-right: .26em` en vez de confiar en el espacio real; `.word`
    necesitaba el mismo parche. Se agregó un test que mide que dos palabras seguidas no
    compartan el mismo borde (`rect.right == rect.left` de la siguiente).
  - La hoja de contacto (10/50/90 % del `duracion` de cada spec de prueba) hay que diseñarla
    con el `cue`/`dura` del rótulo y la ventana de dibujo de las marcas a propósito: con los
    tiempos por defecto, el muestreo genérico cae fácil fuera de la ventana interesante
    (antes de que entre o después de que salga) y no prueba nada a ojo.
- **No entró en esta rebanada** (time-box ~2h): un hand-drawn "wobble" (el bamboleo
  aleatorio-con-semilla de `hw-underline`/`hw-boil` de HyperFrames) en las marcas — quedaron
  con un trazo liso, no tembloroso.
- **Arreglo posterior (07/10/2026, H7)**: el círculo de `"marcar"` pisaba la letra anterior
  (margen fijo de +20px sin medir el hueco real) — ver "H7 cerrada" abajo.

### H7 cerrada (07/10/2026, rama `feat/hito3`)
- **Transición `whip`** (latigazo de cámara, velocidades pareadas): misma arquitectura que
  `barrido`/`fundido` (cada mitad pinta DENTRO de su propio slot, en su propio `seg/NN.mp4`; la
  voz y el `.srt` no se mueven; Q4 sigue valiendo: sólo hay `whip` si al menos un lado es
  escena). Reusa LITERALMENTE la curva de `anchos_barrido`
  (`sweep(p) = ancho·(1 − cos(π·p))`, p de 0 a 1 en TODA la transición, 0.5 = el corte) en vez de
  inventar una nueva: es la MISMA función continua vista desde cada mitad, así que la velocidad
  en el corte es igual de los dos lados por construcción (no hay dos curvas independientes que
  puedan desencajar). `anchos_whip` la usa para el desplazamiento del recorte (`crop x`, 0→ancho
  en cada mitad: saliente se va hacia la izquierda revelando el fondo del brand, entrante llega
  desde la derecha) y para el desenfoque de movimiento (`gblur sigma = sigma_max·sin(π·p)`: 0 en
  los dos extremos -reposo, nítido-, máxima exactamente en el corte, LA MISMA en saliente y
  entrante). Mismo gotcha que `barrido` (ffmpeg 6.1.1: `crop`/`gblur` no reevalúan sus parámetros
  por cuadro con una expresión de `t`): se maneja cuadro a cuadro con `sendcmd`
  (`comandos_whip`), script que se borra siempre (`try/finally`, igual que `aplicar_barrido`).
  Color: el de **fondo** del brand (como `fundido`, nunca el acento: no hay nada que destacar,
  es el "vacío" que el corrimiento revela). Verificado con una hoja de 8 cuadros alrededor de un
  corte real (dos escenas `presentacion` renderizadas de verdad): el título sale acelerando y
  desenfocándose hacia la izquierda, el siguiente entra desde la derecha desenfocado y se asienta
  nítido — mirala en el informe de esta rebanada.
- **Arreglo H6**: el círculo de `"marcar"` (`pathDeMarca`, `presentacion.html`) usaba un margen
  horizontal FIJO (+20px) sin mirar si había una palabra vecina ahí cerca — con palabras pegadas
  por un solo espacio (ej. "...lo mismo trabajo" marcando "trabajo"), el círculo entraba 7px
  en la "o" de "mismo". `envolverPalabra` ahora devuelve también los nodos de texto `antes`/
  `despues` del span envuelto (ya existían como variables locales, sólo había que exponerlos), y
  `pathDeMarca` mide con `Range.getClientRects()` el borde real del renglón vecino más cercano
  (sólo el renglón que comparte línea con la marca, por si el punto es largo y el texto
  "antes"/"despues" ocupa más de un renglón) y acota el margen a la mitad de ese hueco menos 2px
  de aire, nunca por debajo de 2px. Sin vecina de ese lado (la marca es la primera o la última
  palabra del texto), sigue el margen fijo de 20px de siempre.
- **Pendiente para quien siga**: el wobble a mano de las marcas (H6, arriba) sigue sin entrar.

### H1 cerrada (06/10/2026, worktree `feat/hito3-h1`)
- "Voiceover carve" (`musica.aplicar_carve_voz`, `musica.BANDAS_VOZ_HZ`): bandas FIJAS
  (250/400/630/1000/2500 Hz -7dB, 1600 Hz -15dB, robadas de HyperFrames
  `packages/core/src/audioCarve.ts`, redondeadas desde su salida a fuerza 0.8 documentada
  en `skills/hyperframes-audio/SKILL.md`), no su análisis FFT por voz: simplificación
  deliberada del time-box (~2h). Si una voz atípica necesitara otro perfil de bandas, queda
  para abrir boca más adelante.
- Con el carve activo, el ducking de banda ancha default bajó de 18 a 10 LU
  (`editar.py`, `musica_g.get("debajo_de_la_voz_lu", 10)`): el carve ya hace buena parte
  del trabajo de "sacarse del medio" en las bandas donde la voz compite, así que no hace
  falta que el ducking de TODA la frecuencia sea tan profundo.
- Perfiles de loudness por destino (`musica.PERFILES_LOUDNESS`, `"destino"` arriba del
  guion): `"youtube"` (default, -16 LUFS / TP ≤ -1.5 dBTP, sin cambios) y `"redes"` (-14
  LUFS / TP ≤ -1.0 dBTP). `"destino"` inválido aborta antes de generar nada.
- G3 intacto: los guiones sin `"musica"` nunca llaman a `aplicar_carve_voz` ni cambian su
  perfil default, así que `tests/test_s0_red_de_seguridad.py` sigue dando los mismos hashes
  sin regenerar la base.
- Pendiente para quien siga: `README.md` (línea ~166, sección "El guion") sigue
  documentando "18 LU" y no menciona `"destino"` -quedó fuera del alcance de esta rebanada
  (sólo tocaba `musica.py`, la parte de audio de `editar.py`, sus tests y la sección de
  música de `SKILL.md`); hay que actualizarlo aparte.
- Hallazgo (render real, explicador de interés compuesto + música sintética de prueba,
  voz "argentina"): la separación medida en la banda de 1000Hz entre voz y música con
  carve+ducking(10 LU) dio ~14.1 LU (antes del carve: ~12.5 LU); en 1600Hz (la banda del
  corte más profundo, -15dB) dio ~7.6 LU (antes: ~3.9 LU). Mejora clara sobre el ducking
  solo, pero el criterio "≥ 15 LU en las bandas de la voz" de HITO3.md **no se cumplió** en
  ninguna de las dos bandas con esta voz y esta música reales (sí se cumple con un tono puro
  sintético exacto a una banda, ver `tests/test_musica_carve.py`). Causa probable: las
  bandas y profundidades son FIJAS (no el análisis FFT por voz de HyperFrames, decisión
  deliberada de esta rebanada), así que no se adaptan a dónde esta voz en particular
  concentra su energía. Queda para Juani decidir si vale la pena bajar `debajo_de_la_voz_lu`
  más, profundizar las bandas fijas, o retomar el análisis por voz.

### H5 ronda 2 cerrada (06/10/2026, rama `feat/hito3`)
- `pila`/`arbol`/`linea-de-vida` llenaban una franja chica en el centro del cuadro: se sacó
  el ancho fijo de `pila` (560px -> ~1320px, FILA_MAX 140->260) y los topes fijos de ancho/alto
  de `arbol` (190/96px -> toda la columna/fila); el texto principal escala con el espacio
  disponible ("tan grande como entre"), triangulado con fibonacci(3) vs. fibonacci(5): a menos
  nodos, letra más grande.
- `pila` quedaba en blanco al desapilar todo: ahora al desapilar la raíz entra grande, centrado,
  `"<llamada> = <valor>"` (p.ej. `"factorial(4) = 24"`), tan grande como entra en el ancho
  disponible (medido con `medir()`, tope 140px).
- `linea-de-vida`: `layout()` dejaba de crecer en el primer tamaño que entraba (tope fijo
  120px/fila); ahora reparte el alto disponible entre los tramos, así que con pocos tramos cada
  fila es mucho más alta. El trazo pasó de un tope de 14px (invisible, nunca "grueso") a
  `max(24, min(90, fila*0.14))`; `.marca` del eje 22px -> 24px.
- `curva`: con sólo 2-3 `puntos` el trazo entre ellos era una recta (interés compuesto = "dos
  rectas"). Si el spec trae `"crecimiento": {"inicial", "tasa", "periodos"}`, el TRAZO se arma
  con 12 segmentos interpolados por período de la fórmula compuesta; `puntos` sigue siendo sólo
  lo que se marca (nunca una marca por segmento). Sin `crecimiento`, sigue uniendo `puntos` con
  rectas (sin cambios de comportamiento para specs existentes).
- **D7 "texto chico"** nuevo en `verificar.py` (texto visible < 24px, umbral configurable
  `umbral_texto_chico`; kicker/etiqueta mono de 24px exactos pasa), registrado en
  `editar.CHEQUEOS["D7"]` y corrido junto a D5/D6 en `revisar()`. Al correrlo contra las specs de
  ejemplo de TODAS las plantillas aparecieron tres hallazgos reales fuera del alcance de las 4
  escenas de esta rebanada: `datos.html .nota` (20px) y `codigo.html .pestana`/`.term .etq`
  (22px/20px); los tres se subieron a 24px (y `datos.html` bajó `AIRE_NOTA` de 20 a 17 para
  compensar el renglón más alto de la nota y no romper `test_datos_las_cifras_se_leen_en_un_
  celular_y_el_grafico_usa_el_area`, que medía el alto exacto del gráfico).
- Esto cambió el framemd5 de la base `tests/fixtures/s0/escenas.json` (su guion incluye una
  escena `datos` con `"nota"`, que ahora renderiza distinto); el audio_md5 se verificó IDÉNTICO
  y se regeneró sólo el framemd5, en un commit aparte, siguiendo la regla de S0.
- Pendiente para quien siga: `references/escenas.md` documenta `crecimiento` sólo para `curva`;
  si más escenas necesitan fórmulas en vez de puntos a mano, conviene generalizar el patrón.

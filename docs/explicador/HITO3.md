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

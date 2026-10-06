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

Exploración aparte (sin compromiso): captura con CDP `beginFrame` en vez de screenshot, por si
elimina el relayout forzado que hoy hace determinista el render.

## Orden
1. H0 + H1 (en paralelo: no se tocan).
2. H2 + H3.
3. H4 + H5.
4. H6 + H7.
5. H8, después H9.

## Pendientes
_Se completa al cerrar cada rebanada._

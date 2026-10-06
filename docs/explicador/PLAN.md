# Explicador: de skill de tutoriales a explicador de cualquier tema

Rama: `feat/explicador`. Decidido por Juani el 01/10/2026: se amplía esta skill, no se crea otra.

## El objetivo

Darle un tema y que devuelva un video con edición profesional, fluido, como si lo hubiera
editado una persona: diagramas, presentaciones, datos, pantalla grabada e imágenes, elegidos
por tramo del guion. La grabación de pantalla pasa a ser **un tipo de escena más**.

El listón son los videos de Opus 5.5 que se viralizaron en septiembre de 2026 ("Prometheus",
12 M de vistas; el film de la historia de la IA; el showreel de motion design) y el pipeline
de Hasan Aboul Hasan (`hassancs91/claude-youtube-editor`).

## Lo que ya resuelve la skill y NO se rehace

- La voz manda el ritmo: el slot de imagen = duración de la voz + margen (`editar.py`).
- Proveedores de voz intercambiables; Fish Audio es el que Juani quiere. Nada de clones.
- Verificación con Whisper + `silencedetect`, censura por OCR, publicación.

## Decisiones

| Decisión | Alternativa rechazada | Por qué |
|---|---|---|
| Escenas en **HTML con el contrato `window.DURATION` + `async window.seek(t)`**: cada pixel es función pura de `t` (sin `Date.now`, `requestAnimationFrame`, timers, transiciones CSS ni `Math.random` sin semilla) | Remotion (React + build) | La skill es Python + ffmpeg. La idea es prima de la de HyperFrames (todo es función de `t`, render no en tiempo real), pero el formato **no** es el mismo: HyperFrames usa atributos `data-*` en el HTML y una timeline GSAP pausada en `window.__timelines[id]`, así que migrar no sería barato (corregido en el Hito 3, ver `HITO3.md`). Desde H0 una plantilla puede armar una timeline GSAP y entregarla al contrato con `E.lineaDeTiempo` |
| Render con **Playwright de Python** usando el Chrome instalado (`channel="chrome"`), un screenshot por cuadro, pipe a ffmpeg | Bajar Chromium de Playwright; capturar en tiempo real | No baja 150 MB; render no-realtime y determinista, se puede repetir y paralelizar |
| **Tiempos por palabra** con faster-whisper (`word_timestamps=True`) sobre el audio de la voz ya generado | Pedirle tiempos al proveedor de TTS | Funciona con cualquier voz, y faster-whisper ya es dependencia (`verificar_voz.py`) |
| **`brand.json`** por serie (paleta, una tipografía, un color de acento, reglas de movimiento) inyectado en cada escena | Estilo libre por escena | La continuidad visual es lo que hace que parezca una sola persona |
| **Canvas 2D / SVG**, no WebGL | WebGL | La máquina de Juani tiene GPU integrada (AMD Barcelo): WebGL y acuarelas se arrastran |

## Hitos

### Hito 1: el motor de escenas (este change)

1. `palabras.py`: audio → `palabras.json` (`[{palabra, inicio, fin}]`), y una función para
   resolver una "cue" (`"cuando dice 'base de datos'"`) a un tiempo en segundos.
2. `escena.py render`: HTML de escena + spec JSON + brand + cues → `.mp4` de duración exacta.
   Contrato verificado: falla claro si la página no expone `DURATION`/`seek`.
3. Plantillas en `assets/escenas/`, cada una un HTML que lee su spec y es función pura de `t`:
   - `diagrama`: nodos y flechas que se dibujan de a uno, cada uno en su cue.
   - `presentacion`: título cinético + puntos que entran de a uno en su cue.
   - `datos`: barras que crecen hasta su valor en su cue.
4. Integración en `editar.py`: un segmento del guion con `"escena": {"tipo": ..., ...}` se
   renderiza con el motor en vez de cortarse del crudo, con la misma duración de slot. Los
   segmentos de pantalla siguen exactamente igual.
5. `escena.py contacto`: hoja de contacto (cuadros a 10/50/90 % de cada escena) para revisar
   antes del render completo.
6. Ejemplo de punta a punta en `assets/guion-ejemplo/` con un tema que NO sea programación.

### Hito 2: que parezca editado por una persona

Transiciones que comparten forma/color/movimiento, zoom suave automático en los momentos
clave (la skill ya sabe dónde tipea y clickea), música de fondo + efectos de sonido sobre
palabras con normalización de loudness, escenas `imagen` (metáforas dibujadas), encode por
VAAPI, y el **director** en `SKILL.md`: guion de profe (gancho, analogía, ejemplo, repaso)
y reglas de edición (sin tiempo muerto, cambio visual cada pocos segundos).

## Reglas de diseño (de la investigación)

- Un solo color de acento, una tipografía sans-serif, paleta acotada.
- Movimiento con resortes y overshoot contenido; nada de neón, partículas, sacudones de cámara.
- Cada elemento entra en la palabra que lo nombra, no cerca.
- Los labels se leen en todo momento; nada se superpone.
- Storyboard antes que código; hoja de contacto antes que render completo.

## Equipo

Un agente codea (TDD estricto), uno testea (independiente, intenta romperlo) y uno audita
(lee los informes y el diff, reporta directo a Juani). Máximo 3 sub-agentes por change.

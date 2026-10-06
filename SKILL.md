---
name: tutorial-video-agente
description: >
  Produce videos educativos con edición profesional: tutoriales de pantalla grabada (un agente de IA o
  código en VS Code), explicadores de cualquier tema con escenas animadas, y videos de cátedra con
  diapositivas. Narración TTS intercambiable o voz grabada propia, música, efectos, transiciones y
  revisión automática; publica en YouTube o Google Drive. Incluye `presentaciones/`, que arma
  diapositivas .pptx/.pdf con el estilo institucional de UTN TUPaD desde un YAML (código y salidas
  reales, pila y árbol de recursión desde una traza).
  Trigger: "grabá un tutorial", "video de opencode haciendo X", "narrá con voz", "armá la playlist",
  "subí los videos a YouTube/Drive", "cambiá la voz de los videos", "video explicando X", "grabá el
  video de la unidad N", "armá diapositivas para el video/la clase/la microteaching", "slides estilo
  UTN/TUPaD", "pasá este guion a diapositivas".
license: Apache-2.0
metadata:
  author: juanisarmiento
  version: "1.0"
---

# tutorial-video-agente

Produce series de video-tutoriales sin editor de video: graba la pantalla o controla un agente,
corta por segmentos, narra con TTS (o voz propia), y entrega `.mp4` con subtítulos. La idea que la
hace distinta está en el README: **la imagen se mide con la voz**, no al revés — ver README.md.

Este archivo es un router: lee lo de abajo para decidir el flujo y después abrí **sólo** el
`references/*.md` de la tabla que corresponda a lo que vas a hacer. No leas el resto por las
dudas — cada referencia está pensada para leerse sola.

## Cuándo se usa

- Grabar a un agente (opencode + Active Stack, u otro) resolviendo algo de punta a punta.
- Convertir grabaciones largas (horas) en videos cortos (≤5 min) con voz de profe.
- Cambiar la voz de videos ya editados sin regrabar.
- Publicar la serie en YouTube (playlist) o en una carpeta pública de Drive.
- Explicar un tema que no es de pantalla (finanzas, biología, historia) con escenas animadas: ver Escenas.
- Armar diapositivas y el video de una clase de UTN TUPaD.

## Los cuatro flujos

| Flujo | En pocas palabras | Por dónde empezar |
|---|---|---|
| **1. Tutorial de pantalla grabada** | `entorno.sh`/`rec.py` graban; se escribe el guion mirando frames (no marcas); `editar.py imagen` + `editar.py voz` arman el entregable | `references/grabacion.md` → `references/guion-y-edicion.md` |
| **2. Explicador con escenas** | Sin crudo: segmentos `"escena"` (`presentacion`, `diagrama`, `datos`, `imagen`, `codigo`, `contador`) que se renderizan desde plantillas HTML y entran en la palabra que los nombra | `references/escenas.md` |
| **3. Video de cátedra con diapositivas** | El módulo `presentaciones/` arma el `.pptx`/`.pdf` institucional desde un YAML; el video sale de pasar esas páginas a imagen fija sincronizada con la voz | `references/catedra.md` |
| **4. Cambiar la voz / publicar** | Mismo guion, otra voz en `editar.py imagen VOZ` + `editar.py voz VOZ` (re-arma porque los tiempos cambian); publicar es un paso aparte, con OK explícito | `references/voces.md` → `references/publicacion.md` |

Cualquier flujo puede llevar música, efectos, transiciones y la revisión del Director: son
transversales, no un flujo propio (ver la tabla de abajo).

## Flujo (en orden)

| Fase | Qué se hace | Scripts |
|---|---|---|
| 0. Preparar | agente instalado y logueado, carpeta del proyecto con `git init`, terminal opaca y con letra grande. **Bajo Wayland: `entorno.sh start` primero** | `entorno.sh` |
| 1. Grabar | un `.mkv` por fase/capítulo + marcas de tiempo | `rec.sh` |
| 2. Manejar el agente | tipear prompts, aprobar permisos seguros, responder preguntas | `ty.py`, `drive.sh`, `cmd.sh`, `answer.sh`, `lastq.py`, `oclog.py` |
| 3. Guion | `guion/vNN.json`: segmentos `{inicio, fin, texto}` + tarjeta de título | ver `assets/guion-ejemplo/` |
| 4. Editar | `editar.py imagen vNN VOZ` → `editar.py voz vNN VOZ` | `editar.py` |
| 5. Verificar | Whisper sobre cada tramo (repeticiones) + `silencedetect` | `verificar_voz.py` |
| 6. Publicar | comprimir <10 MB, subir con Claude in Chrome, playlist/carpeta pública | ver Publicación |

## Reglas duras (valen siempre, en cualquier flujo)

- **Privacidad: lo que se filma no se puede despublicar.** Un barrido con `tesseract` (OCR, no a
  ojo) sobre el video TERMINADO, y de vuelta sobre el video YA censurado. Ninguna ruta personal en
  pantalla (home, usuario, ids de cuenta reales): ver `references/verificacion.md`.
- **El código y las salidas son reales.** Nunca tipeado a mano en un spec de escena ni en una
  diapositiva: se lee de archivos reales y se ejecuta de verdad (`references/escenas.md`,
  `references/catedra.md`).
- **La voz manda el ritmo.** La imagen se estira o se acelera a la duración de la voz, nunca al
  revés — por eso cambiar de voz re-arma el video entero (`references/voces.md`).
- **`editar.py revisar` antes de entregar.** Mide tiempo muerto, silencios, roles y contraste; sólo
  lee, nunca modifica nada (`references/director.md`).
- Nunca voces de famosos ni clones de personas reales sin consentimiento, aunque sea "en joda".
- API keys en `~/.config/<proveedor>/api_key` con `chmod 600`; nunca en guiones ni scripts. Si el usuario las pega en el chat, recomendar rotarlas.
- Publicar (YouTube/Drive público) requiere OK explícito del usuario; avisar si el contenido es una solución de TP antes del cierre (`references/publicacion.md`).
- **Nunca `pgrep -f`/`pkill -f <patrón>` en un loop de espera dentro de un script que contiene ese
  patrón**: compara contra la cmdline completa y el proceso se mata o se confunde a sí mismo.
  Esperar por **ausencia de proceso**, no por un pid (`references/grabacion.md`,
  `references/guion-y-edicion.md` → "Un render por vez").

## Tabla de ruteo

| Si vas a... | Leé |
|---|---|
| Grabar bajo Wayland (Xephyr), manejar una app Electron por CDP, tipear en VS Code o una terminal, o portar a Windows | `references/grabacion.md` |
| Escribir o editar el guion, usar `editar.py imagen`/`voz`/`zonas`, slots, velocidad de voz, zoom, o elegir el encoder de video | `references/guion-y-edicion.md` |
| Armar o tocar una escena animada (`presentacion`, `diagrama`, `datos`, `imagen`, `codigo`, `contador`), cues, o la plantilla HTML | `references/escenas.md` |
| Música de fondo, voiceover carve, perfiles de loudness, o efectos de sonido (sfx) | `references/audio.md` |
| Elegir, agregar, o calibrar la velocidad de una voz TTS | `references/voces.md` |
| Agregar o tocar una transición entre tramos (`corte`, `fundido`, `barrido`) | `references/transiciones.md` |
| Escribir el guion como lo haría quien edita de profesión, o entender qué mide `editar.py revisar` (D1-D6) | `references/director.md` |
| Correr la puerta de escenas (`verificar.py`), `editar.py revisar`, censurar con OCR, o verificar la voz con Whisper | `references/verificacion.md` |
| Armar diapositivas de cátedra UTN/TUPaD (`presentaciones/`) | `references/catedra.md` |
| Publicar en YouTube o en una carpeta de Drive | `references/publicacion.md` |

## Resources

- **Scripts**: [assets/scripts/](assets/scripts/) — grabación, control de opencode, edición y verificación.
- **Entorno bajo Wayland**: [assets/scripts/entorno.sh](assets/scripts/entorno.sh) — `start|chrome|status|stop`.
- **Guiones de ejemplo**: [assets/guion-ejemplo/](assets/guion-ejemplo/) — video de navegador (v01), ciclo OPSX (v07) y explicador con escenas (interés compuesto).
- **Escenas**: [assets/escenas/](assets/escenas/) — plantillas, `base.js` (contrato y resortes) y `brand.json`. Motor: `escena.py`, tiempos por palabra: `palabras.py`.
- **Voces y proveedores**: [references/voces.md](references/voces.md) — IDs, costos, licencias y cómo agregar una voz a `editar.py`.
- **Caso real completo**: `~/Proyectos/tutorial-active-stack/` (TP2 Java con Active Stack + opencode + Muse Spark).

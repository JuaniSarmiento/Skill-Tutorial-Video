---
name: tutorial-video-agente
description: >
  Arma una playlist de video-tutoriales donde un agente de IA (opencode/Claude Code) resuelve un proyecto
  en la terminal: graba la pantalla, maneja el agente con xdotool, edita por segmentos con narración TTS
  intercambiable (Piper, ElevenLabs, Fish Audio) y publica en YouTube o Google Drive.
  Trigger: "grabá un tutorial", "video de opencode haciendo X", "narrá con voz", "armá la playlist",
  "subí los videos a YouTube/Drive", "cambiá la voz de los videos".
license: Apache-2.0
metadata:
  author: juanisarmiento
  version: "1.0"
---

## When to Use

- Grabar a un agente (opencode + Active Stack, u otro) resolviendo algo de punta a punta.
- Convertir grabaciones largas (horas) en videos cortos (≤5 min) con voz de profe.
- Cambiar la voz de videos ya editados sin regrabar.
- Publicar la serie en YouTube (playlist) o en una carpeta pública de Drive.

## Flujo (en orden)

| Fase | Qué se hace | Scripts |
|---|---|---|
| 0. Preparar | agente instalado y logueado, carpeta del proyecto con `git init`, terminal opaca y con letra grande | — |
| 1. Grabar | un `.mkv` por fase/capítulo + marcas de tiempo | `rec.sh` |
| 2. Manejar el agente | tipear prompts, aprobar permisos seguros, responder preguntas | `ty.py`, `drive.sh`, `cmd.sh`, `answer.sh`, `lastq.py`, `oclog.py` |
| 3. Guion | `guion/vNN.json`: segmentos `{inicio, fin, texto}` + tarjeta de título | ver `assets/guion-ejemplo/` |
| 4. Editar | `editar.py imagen vNN VOZ` → `editar.py voz vNN VOZ` | `editar.py` |
| 5. Verificar | Whisper sobre cada tramo (repeticiones) + `silencedetect` | `verificar_voz.py` |
| 6. Publicar | comprimir <10 MB, subir con Claude in Chrome, playlist/carpeta pública | ver Publicación |

## Critical Patterns

**Antes de grabar**
- **Layout de teclado único**: con `us,latam,us` xdotool escribe `@` en vez de `"`. Forzar `setxkbmap -layout latam` y restaurar al final.
- `ty.py` tipea no-ASCII de a un carácter: xdotool pierde tildes si van en ráfaga.
- La terminal COSMIC es transparente por defecto: poner `opacity` en 100 y restaurar.
- **Nadie toca la PC mientras xdotool escribe** (las teclas van a la ventana con foco).
- Los slash-commands que crea `openspec init` NO aparecen hasta reiniciar opencode (`/exit` + relanzar).
- `ctrl+a` en COSMIC abre la vista de escritorios: no usarlo para limpiar el input; usar BackSpace.

**Manejar opencode**
- Seguir el agente leyendo SQLite (`~/.local/share/opencode/opencode.db`) y el log, NO con capturas: `oclog.py`, `ocwatch.py`.
- El log dice `message=asking permission=…` ANTES de que se dibuje el diálogo → esperar ~2.5 s.
- Diálogo de permiso: `Right` = "Allow always", `Enter`, `Enter` (Confirm). Left/Right hacen wrap: nunca navegar con Left.
- `drive.sh` aprueba solo permisos seguros y frena ante `external_directory` (salvo `/tmp`), `rm -r`, `sudo`, `git push/reset`.
- Una `question` pendiente también dispara "asking" (sin `permission=`): responder con `answer.sh IDX…` o multi-select con `Enter` por opción + `Tab` a Confirm.
- Revisar la propuesta (propose) como profe ANTES de apply: ahí se atajan errores baratos (ej. paquetes anidados del UML).
- Sesión nueva por cada change (`/new`): el contexto vive en archivos, no en el chat.

**Editar**
- Idea central: la **imagen** se arma por voz con slots = duración de esa voz + margen corto; así no hay silencios de relleno y cambiar de voz = regenerar audio.
- Remuxear los `.mkv` a `.mp4` (`-c copy -movflags +faststart`) antes de cortar: `-ss` sobre mkv cortado por kill es impreciso.
- `mpdecimate` en tramos de terminal (salta frames quietos); `decimar: false` en tramos de navegador (las pausas son intencionales).
- Voz educativa: speed 0.8 y pausas internas hasta 0.8 s (≈135 palabras/min). Recortar pausas a 0.35 s suena apurado.
- Términos en inglés: con Fish escribirlos tal cual; siglas fonéticas (`opsx` → "o pe ese equis", `.md` → "punto eme de"). Piper necesita fonética ("esquils").
- Chequear el guion por repeticiones propias ("modelo, modelo actividades…") antes de culpar a la voz.

**Publicar**
- `file_upload` de la extensión acepta ≤10 MB por llamada → comprimir con `-crf 29–34 -tune stillimage`.
- YouTube Studio: el primer tipeo en título/descripción tras subir se pierde → repetir en otro tool call y verificar con zoom. "No es para niños": click por coordenada + zoom.
- YouTube tiene **límite diario de cargas** para canales sin verificar (~10): verificar teléfono en `youtube.com/verify` o esperar 24 h.
- YouTube no reemplaza archivos: subir nuevos y pasar los viejos a **Privado** (nunca borrar: lo hace el usuario).
- Drive: crear carpetas con el MCP de Drive (`create_file` con mimeType folder), subir con Chrome (Nuevo → Subir archivo → `find input type=file` → `file_upload`), compartir "Cualquier persona con el vínculo: Lector" desde la UI y verificar con `get_file_permissions`.

**Límites duros**
- Nunca voces de famosos ni clones de personas reales sin consentimiento, aunque sea "en joda".
- API keys en `~/.config/<proveedor>/api_key` con `chmod 600`; nunca en guiones ni scripts. Si el usuario las pega en el chat, recomendar rotarlas.
- Publicar (YouTube/Drive público) requiere OK explícito del usuario; avisar si el contenido es una solución de TP antes del cierre.

## Commands

```bash
# variables comunes
export TUT_ROOT=~/Proyectos/tutorial-X   # raíz: raw/, guion/, videos/
export OC_DIR=~/Proyectos/proyecto-X      # directorio donde corre opencode
export OC_WIN=0x06a00005                  # id de ventana de la terminal (wmctrl -l)
S=~/.claude/skills/tutorial-video-agente/assets/scripts

# grabar
$S/rec.sh start v04-discovery ; $S/rec.sh mark v04-discovery "discovery confirmado" ; $S/rec.sh stop v04-discovery

# manejar opencode
$S/ty.py 'Texto del prompt con tildes' --enter
$S/drive.sh 1800            # aprueba permisos seguros hasta pregunta/fin de turno
$S/lastq.py ; $S/answer.sh 1 2
$S/cmd.sh v07-ej1 /opsx-apply c-01-nombre "opsx-apply C-01"

# remux + editar + verificar
for f in raw/*.mkv; do ffmpeg -y -i "$f" -c copy -movflags +faststart "${f%.mkv}.mp4"; done
$S/editar.py imagen v01 profe && $S/editar.py voz v01 profe
uv run --with faster-whisper python $S/verificar_voz.py profe v01
ffmpeg -i videos/v01/final-profe.mp4 -af silencedetect=noise=-40dB:d=0.9 -f null - 2>&1 | grep -c silence_end

# comprimir para subir
ffmpeg -y -i videos/v01/final-profe.mp4 -c:v libx264 -preset slow -crf 30 -tune stillimage -c:a aac -b:a 128k "drive/1 - Titulo.mp4"
```

## Resources

- **Scripts**: [assets/scripts/](assets/scripts/) — grabación, control de opencode, edición y verificación.
- **Guiones de ejemplo**: [assets/guion-ejemplo/](assets/guion-ejemplo/) — video de navegador (v01) y ciclo OPSX (v07).
- **Voces y proveedores**: [references/voces.md](references/voces.md) — IDs, costos, licencias y cómo agregar una voz a `editar.py`.
- **Caso real completo**: `~/Proyectos/tutorial-active-stack/` (TP2 Java con Active Stack + opencode + Muse Spark).

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
| 0. Preparar | agente instalado y logueado, carpeta del proyecto con `git init`, terminal opaca y con letra grande. **Bajo Wayland: `entorno.sh start` primero** | `entorno.sh` |
| 1. Grabar | un `.mkv` por fase/capítulo + marcas de tiempo | `rec.sh` |
| 2. Manejar el agente | tipear prompts, aprobar permisos seguros, responder preguntas | `ty.py`, `drive.sh`, `cmd.sh`, `answer.sh`, `lastq.py`, `oclog.py` |
| 3. Guion | `guion/vNN.json`: segmentos `{inicio, fin, texto}` + tarjeta de título | ver `assets/guion-ejemplo/` |
| 4. Editar | `editar.py imagen vNN VOZ` → `editar.py voz vNN VOZ` | `editar.py` |
| 5. Verificar | Whisper sobre cada tramo (repeticiones) + `silencedetect` | `verificar_voz.py` |
| 6. Publicar | comprimir <10 MB, subir con Claude in Chrome, playlist/carpeta pública | ver Publicación |

## Critical Patterns

**Bajo Wayland (COSMIC, GNOME moderno): la skill NO funciona directo**

Esta skill es X11. En una sesión Wayland falla en silencio, produciendo archivos que parecen válidos:
`x11grab` graba un rectángulo **negro** (brillo 0.0/255, 1 color) y `xdotool`/`wmctrl` sólo ven
ventanas Xwayland, no las nativas. Comprobar con `echo $XDG_SESSION_TYPE`.

- **La salida es `entorno.sh start`**: levanta un X11 real (Xephyr) dentro de una ventana, en `:2`.
  Ahí adentro todo corre sin cambios. Render por software, pero probado a **30 fps sostenidos**
  con GitHub scrolleando y opencode: alcanza de sobra.
- **`kitty` y `alacritty` NO sirven adentro**: exigen OpenGL 3.3 y Xephyr no da GPU. El proceso
  vive y nunca crea ventana, sin escribir un error. Usar **`xterm`**, que no toca la GPU.
- **Chrome ignora `DISPLAY` bajo Wayland** y abre en Ozone/Wayland, o sea en el escritorio real
  en vez de Xephyr. Hay que forzar `--ozone-platform=x11` **y** limpiar `WAYLAND_DISPLAY`
  (`env -u WAYLAND_DISPLAY`). Sin las dos cosas la ventana aparece donde no se está grabando.
- **El popup de Google Translate no se apaga con `--disable-features=Translate`** (cambió de
  nombre): hay que poner `translate.enabled=false` en `<perfil>/Default/Preferences` antes de
  lanzar. `entorno.sh chrome` ya lo hace.
- **Nunca `pkill -f <patrón>` en un script que contiene ese patrón**: pkill compara contra la
  cmdline completa y el script **se mata a sí mismo** (exit 144). Matar por `pkill -x <exe>` o
  verificando `/proc/<pid>/exe`.
- Los scripts de captura leen `$DISPLAY` (antes tenían `-i :1` hardcodeado).

**Apps Electron: xdotool NO sirve, va por CDP**

La app de escritorio de OpenCode (y cualquier Electron) **ignora los eventos sintéticos de
XTEST**. X11 reporta que la ventana tiene el foco y `xdotool type` no entrega un solo carácter,
sin error ninguno. Verificado con foco forzado (`windowactivate --sync` + `windowfocus --sync`)
y a cuatro velocidades distintas.

- **La salida es el Chrome DevTools Protocol**: lanzar la app con `--remote-debugging-port=9222`
  y tipear con `ty-cdp.py`. Entra por dentro de la app, así que **no depende del foco** de
  ninguna ventana: no hay que activar nada ni cuidar que nadie toque el teclado.
- `click-cdp.py 'Permitir siempre'` aprieta botones por su texto, para los diálogos de permiso.
- `ty-cdp.py` acepta `--limpiar` (vacía el input), `--enter` y `--delay MS` para que el tipeo se
  vea natural en cámara.
- **ydotool se descartó**: la versión de Ubuntu 24.04 (0.1.8) no trae daemon, y además inyecta al
  foco del SISTEMA, así que si el foco se mueve le escribe a otra ventana.
- En una terminal de verdad (xterm) `ty.py` sigue siendo lo correcto: ahí XTEST funciona bien.

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
- Voz educativa: speed **0.90** y pausas de 0.55 s (≈170 palabras/min). A 0.8 suena arrastrada:
  quien mira pone el video a 1.25 y entonces la voz ya no es la que elegiste. Por debajo de
  0.35 s de pausa suena apurado.
- Términos en inglés: con Fish escribirlos tal cual; siglas fonéticas (`opsx` → "o pe ese equis", `.md` → "punto eme de"). Piper necesita fonética ("esquils").
- Chequear el guion por repeticiones propias ("modelo, modelo actividades…") antes de culpar a la voz.

**Publicar**
- `file_upload` de la extensión acepta ≤10 MB por llamada → comprimir con `-crf 29–34 -tune stillimage`.
- YouTube Studio: el primer tipeo en título/descripción tras subir se pierde → repetir en otro tool call y verificar con zoom. "No es para niños": click por coordenada + zoom.
- YouTube tiene **límite diario de cargas** para canales sin verificar (~10): verificar teléfono en `youtube.com/verify` o esperar 24 h.
- YouTube no reemplaza archivos: subir nuevos y pasar los viejos a **Privado** (nunca borrar: lo hace el usuario).
- Drive: crear carpetas con el MCP de Drive (`create_file` con mimeType folder), subir con Chrome (Nuevo → Subir archivo → `find input type=file` → `file_upload`), compartir "Cualquier persona con el vínculo: Lector" desde la UI y verificar con `get_file_permissions`.

**Privacidad: lo que se filma no se puede despublicar**

Tres cosas se colaron en videos ya renderizados y sólo aparecieron al buscarlas con OCR.
Ninguna se habría visto mirando el material por encima.

- **El token no está donde lo buscás.** Aparece en el mensaje del chat donde se lo pegaste
  al agente, que queda scrolleado y visible durante medio video, no sólo en el
  `wrangler secret put`. En una tanda apareció en **75 frames de 4 videos**.
- **Telegram Web muestra la lista de contactos** con nombres reales en la barra izquierda.
  Abrilo **directo en la conversación del bot** (`web.telegram.org/a/#<chat_id>`) y con la
  lista colapsada. Taparla después es un parche de 75 segundos de caja negra.
- **Verificar con OCR, no a ojo.** Un barrido con `tesseract` cada 2 s sobre el video
  terminado, buscando el token, el mail y el id de cuenta. Es la única forma de saberlo:
  a ojo se pasan.
- **Para tapar, una caja por tramo, nunca una sola.** El texto se mueve con el scroll: unir
  todas las posiciones detectadas en un rectángulo terminó tapando el 60% de la pantalla.
  Agrupar por cercanía temporal Y espacial, y emitir un `drawbox` con
  `enable='between(t,..)'` por grupo. Cada caja debe quedar en 1-2% de pantalla.
- **Caja negra sólida, no desenfoque**: un blur suave deja legible un número grande.
- **Y volvé a barrer el video YA censurado.** Dar por buena la censura sin verificarla es
  el mismo error que dar por buena la grabación sin mirarla.

**Sincronía: escribir el guion mirando frames, no marcas**

Las marcas de `rec.sh` dicen cuándo pasó algo, no qué se ve. Entre dos marcas puede haber
diez minutos de pantalla congelada esperando un permiso. Un guion escrito desde las marcas
narra cosas que en pantalla no ocurren.

Antes de escribir cada segmento: `ffmpeg -ss <t> -i raw.mp4 -frames:v 1` y mirar el frame.
Si tres frames distintos del mismo tramo son idénticos, ahí no pasa nada y no sirve.

**VS Code: crear archivos, y las tres formas que NO sirven**

`Ctrl+P` **no crea archivos**: si el archivo no existe, el foco se queda donde
estaba y el código termina escrito en el archivo anterior, sin un solo error.
De las cuatro formas de crear un archivo, sólo una funciona para automatizar:

| Forma | Qué pasa |
|---|---|
| `Ctrl+N` / "File: New File" del Command Palette | escribe el texto **"New File" dentro del código** |
| `code archivo.py` | abre un editor, pero el archivo **no existe hasta que guardás** |
| click derecho en el explorador | necesita coordenadas, y el explorador está oculto |
| **`touch archivo.py` en la terminal integrada** | **crea el archivo en disco, verificable** |

`touch` además **es didáctico**: el alumno ve cómo se crea un archivo desde la
terminal, que es lo que va a hacer siempre. Está en `codigo-vscode.py --crear`.

**`Ctrl+grave` no abre la terminal con teclado latinoamericano.** El comando
termina tipeado adentro del archivo de código. Todo lo que toque la terminal va
por el Command Palette (`term-vscode.py`), que no depende del layout.

**VS Code: el buffer sucio sobrevive a matar el proceso**

Si la ventana muestra `●` en el título, hay cambios sin guardar. En ese estado
el Command Palette **se come los comandos**: el diálogo de guardado se queda con
el foco y lo que tipeás va al archivo. Se ve clarísimo después — quedan líneas
como `KAll Terminals` en medio del código.

Relanzar VS Code **no alcanza**: `hotExit` guarda el buffer en
`<user-data-dir>/Backups` y lo resucita idéntico. Hay que borrar ese directorio
y dejar `"files.hotExit": "off"` en los settings del perfil de grabación.

Y `"The content of the file is newer"`: VS Code **se niega a guardar** si el
archivo cambió por fuera mientras lo tenía abierto. Nunca restaures archivos
desde bash con el editor abierto; `codigo-vscode.py` hace `File: Revert File`
antes de escribir por exactamente esto.

**Zoom: el recorte encaja, no fuerza el ancho**

`scale=1920:-2` sobre un recorte apenas más alto que 16:9 (1150x650 da 1085 de
alto) se pasa por un pixel y `pad` muere con *"Padded dimensions cannot be
smaller than input dimensions"*. Va
`scale=1920:1080:force_original_aspect_ratio=decrease` y listo, sea la región
más ancha o más alta que la pantalla.

Para tapar el ruido de automatización (el Command Palette abriéndose entre
comando y comando) alcanza con **encuadrar la terminal**: la paleta vive arriba
al centro y queda fuera del recorte.

**Un render por vez**

Dos `editar.py imagen` sobre el mismo video **se borran los `.tmp.mp4` entre
ellos** y el segundo muere con un `FileNotFoundError` en `tmp.unlink()` que no
dice nada del verdadero problema. Pasa fácil con `nohup ... &`: `$!` y el pid
que devuelve `pgrep` **no son el mismo proceso**, así que esperás a uno que ya
murió y arrancás el segundo encima. Esperá por **ausencia de proceso**, no por
un pid.

**Windows: anda, y ahi el problema de Wayland no existe**

La skill se apoya en tres verbos que dependen del sistema, y viven aislados en
`plataforma.py`. Todo lo demas — `editar.py`, `censurar.py`, `verificar_voz.py`,
los scripts de CDP — es ffmpeg y Python puro y corre igual en los dos lados.

| verbo | Linux | Windows |
|---|---|---|
| capturar | `x11grab` | `gdigrab -i desktop` |
| tipear | `xdotool type` | `SendInput` con `KEYEVENTF_UNICODE` |
| enfocar | `wmctrl -a` | `SetForegroundWindow` |

- **En Windows no hace falta instalar nada mas que ffmpeg.** La entrada va por
  `ctypes` contra `user32`, que es libreria estandar: no hay pyautogui ni pywin32.
- **`entorno.sh` no se usa en Windows**, y con el se va el gotcha mas caro de la
  skill: `gdigrab` captura el escritorio real, no hay Wayland que lo rompa.
- **Las tildes salen mejor que en Linux.** `KEYEVENTF_UNICODE` manda el codepoint
  en vez de una tecla, asi que no depende del layout. En Linux hay que forzar
  `setxkbmap -layout latam` o xdotool escribe `@` en vez de `"`.
- **La terminal integrada de VS Code es PowerShell**: `touch` no existe, va `ni`.
  `codigo-vscode.py` ya lo distingue.
- **Los scripts `.sh` son solo de Linux.** El reemplazo multiplataforma de
  `rec.sh` es `rec.py`, con los mismos tres verbos. Los que manejan opencode por
  terminal (`allow.sh`, `answer.sh`, `cmd.sh`, `drive.sh`) no tienen equivalente:
  en Windows se maneja por CDP, que ya es portable.
- Diagnostico antes de grabar: `plataforma.py info` dice que detecto, que
  herramientas faltan y con que comando va a capturar.

**ASSUMPTION (no verificado):** la rama Windows esta escrita contra la API de
Win32 pero **no se probo en una maquina Windows**. La rama Linux si esta probada
de punta a punta. Antes de confiar en ella, correr `plataforma.py info` y despues
una grabacion corta con `rec.py`.

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

# entorno (SOLO si estás en Wayland: echo $XDG_SESSION_TYPE)
$S/entorno.sh start                  # Xephyr :2 + openbox + xterm; imprime DISPLAY y OC_WIN
$S/entorno.sh chrome https://...     # Chrome adentro, forzado a X11 y sin popup de Translate
$S/entorno.sh status ; $S/entorno.sh stop

# grabar
$S/rec.sh start v04-discovery ; $S/rec.sh mark v04-discovery "discovery confirmado" ; $S/rec.sh stop v04-discovery

# manejar opencode
$S/ty.py 'Texto del prompt con tildes' --enter
$S/drive.sh 1800            # aprueba permisos seguros hasta pregunta/fin de turno
$S/lastq.py ; $S/answer.sh 1 2
$S/cmd.sh v07-ej1 /opsx-apply c-01-nombre "opsx-apply C-01"

# remux + editar + verificar
for f in raw/*.mkv; do ffmpeg -y -i "$f" -c copy -movflags +faststart "${f%.mkv}.mp4"; done
$S/editar.py imagen v01 joven && $S/editar.py voz v01 joven   # joven = voz principal (default)
uv run --with faster-whisper python $S/verificar_voz.py joven v01
ffmpeg -i videos/v01/final-joven.mp4 -af silencedetect=noise=-40dB:d=0.9 -f null - 2>&1 | grep -c silence_end

# comprimir para subir
ffmpeg -y -i videos/v01/final-joven.mp4 -c:v libx264 -preset slow -crf 30 -tune stillimage -c:a aac -b:a 128k "drive/1 - Titulo.mp4"
```

## Resources

- **Scripts**: [assets/scripts/](assets/scripts/) — grabación, control de opencode, edición y verificación.
- **Entorno bajo Wayland**: [assets/scripts/entorno.sh](assets/scripts/entorno.sh) — `start|chrome|status|stop`.
- **Guiones de ejemplo**: [assets/guion-ejemplo/](assets/guion-ejemplo/) — video de navegador (v01) y ciclo OPSX (v07).
- **Voces y proveedores**: [references/voces.md](references/voces.md) — IDs, costos, licencias y cómo agregar una voz a `editar.py`.
- **Caso real completo**: `~/Proyectos/tutorial-active-stack/` (TP2 Java con Active Stack + opencode + Muse Spark).

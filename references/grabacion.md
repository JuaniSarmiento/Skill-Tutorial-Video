## Grabación: Wayland, Electron, VS Code, terminal y Windows

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

**Reproducir un video de YouTube en cámara mete anuncios**

Un corte de Amazon Prime, con subtítulos en alemán, en medio de un video institucional.
Y las recomendaciones de la barra lateral traen lo que traigan — en una toma apareció
contenido político. Saltar el anuncio, cerrar el popup de Premium, y encuadrar con
`zoom` para dejar fuera la franja de recomendaciones. Después revisar los frames: el
anuncio puede entrar a mitad de la toma, no sólo al principio.

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

**Las dos asistencias de VS Code que corrompen el código tipeado, sin error**

Las dos se apagan por configuración ANTES de tipear una letra —`codigo-vscode.py`
mergea diez claves en `<proyecto>/.vscode/settings.json`—, no peleando con teclas.

- **`acceptSuggestionOnCommitCharacter`**: tipear un espacio mientras IntelliSense
  tiene una sugerencia resaltada la **acepta** en lugar de escribir el espacio.
  `FROM pedidos p` salió como **`FROM clientes CASCADE`** en una grabación real.
  Mandar `Escape` antes de cada `Return` **no alcanza**, y es el arreglo que sale
  primero: el commit character se come el espacio de la palabra que se está
  escribiendo, no el separador entre líneas.
- **`autoClosingBrackets`**: al tipear `(` inserta el `)` solo. El `Return` cae
  **dentro** del par, y el `)` que viene después en el código fuente se suma al
  que ya estaba. Una subconsulta con los paréntesis en líneas separadas termina
  con un `)` de más, sin un error durante el tipeo.

Se mergea y no se pisa: el proyecto puede tener su propia configuración ahí.

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

**Windows: anda, y ahi el problema de Wayland no existe**

La skill se apoya en tres verbos que dependen del sistema, y viven aislados en
`plataforma.py`. Todo lo demas — `editar.py`, `censurar.py`, `verificar_voz.py`,
los scripts de CDP — es ffmpeg y Python puro y corre igual en los dos lados.

| verbo | Linux | Windows |
|---|---|---|
| capturar | `x11grab` | `gdigrab -i desktop` |
| tipear | `xdotool type` | `SendInput` con `KEYEVENTF_UNICODE` |
| enfocar | `wmctrl -a` | `SetForegroundWindow` |

- **En Windows hace falta instalar ffmpeg y tesseract con winget**, antes de
  usar la skill (`winget install Gyan.FFmpeg` y `winget install
  UB-Mannheim.TesseractOCR` — ver Requisitos en README.md). La entrada va por
  `ctypes` contra `user32`, que es libreria estandar: no hace falta pyautogui
  ni pywin32 ni ninguna libreria de Python.
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

## Grabar una app web: `grabar_web.py`

Para una app web real (ej. Plataforma N4, `tutor.active-ia.com`) que tiene que verse
como un humano usándola: clicks suaves con curva, cursor dibujado (los clicks de CDP
no mueven el puntero del SO), diálogos nativos (`alert`/`confirm`/`prompt`/`print`)
neutralizados ANTES de que el navegador los abra, y tipeo con ritmo humano que
funciona en editores CodeMirror-like. Corre **adentro** del Xephyr de `entorno.sh
start` (DISPLAY `:2`): Chrome bajo Wayland ignora `DISPLAY` igual que en
`entorno.sh chrome` (forzar `--ozone-platform=x11` y limpiar `WAYLAND_DISPLAY`).

**Loguear una vez, a mano**

```bash
$S/entorno.sh start                                   # si no está arriba ya
uv run --with playwright python $S/grabar_web.py login docente-n4 https://tutor.active-ia.com/login
```

Abre Chrome VISIBLE con un perfil persistente en
`~/.config/tutorial-video/perfiles/docente-n4/`. El humano loguea a mano en esa
ventana (el script **no toca ningún formulario**, nunca tipea ni lee una
contraseña) y la cierra cuando termina: el comando vuelve recién ahí. La próxima
vez que se abra ese mismo perfil (`Toma(perfil="docente-n4", ...)`), la sesión ya
está.

**Un script de toma**

```python
from grabar_web import Toma

t = Toma("docente-n4", "https://tutor.active-ia.com/comisiones", display=":2")
t.grabar_iniciar("v01-comisiones")
t.click("Mis comisiones")                    # locator por texto visible; nunca coordenadas
t.marca("abrio comisiones")
t.escribir("#buscar", "sección 4")            # ritmo humano, seedeado
t.entradas(["28"])                            # próxima respuesta de window.prompt()
t.click("Calcular promedio")                  # usa el prompt encolado arriba
t.pausa(1.5)
t.grabar_detener()
t.cerrar()
```

`Toma` lanza su propio Chrome (el instalado, nunca el de Playwright) con
`--app=<url>` (sin pestañas ni barra), ventana 1920×1080 en el origen,
`--force-device-scale-factor=1.5` por defecto (texto ≥24px en el cuadro, ver
§4.2/§4.6 del CLAUDE.md del repo), `--kiosk` y `--hide-scrollbars` (ver gotcha
de abajo), y `--remote-debugging-port`; Playwright se conecta por
`connect_over_cdp`. `grabar_iniciar`/`grabar_detener` reusan `rec.py` (mismo
`.mkv`, mismas marcas en `raw/<nombre>.marcas.json`, formato
`{"t": seg, "nombre": "..."}` por línea).

**Gotchas**

- **`--app` sólo saca la UI de Chrome; la barra de título es del WINDOW
  MANAGER.** Adentro de `entorno.sh start`, openbox dibuja una barra de
  título ("Fixture grabar_web", etc.) sobre CUALQUIER ventana normal, `--app`
  o no. `--kiosk` la saca pidiendo el estado fullscreen sin decoración.
  **`--start-fullscreen` también la saca, pero de paso Chrome muestra 3-4s el
  cartel "Para salir de pantalla completa, mantené presionado Esc" ENCIMA de
  la página** (grabado en cámara si `grabar_iniciar` arranca mientras el
  cartel sigue arriba): `--kiosk` no lo muestra. `--hide-scrollbars` saca la
  scrollbar (ya usado en `escena.py` para los renders de escena).
- **Probar el scale factor sobre un frame x11grab REAL, no sobre el DOM.**
  `page.evaluate(() => window.devicePixelRatio)` confirma que Chrome aplicó el
  flag, pero no prueba que la GRABACIÓN salga agrandada: x11grab captura el
  framebuffer de Xephyr tal como lo compone el window manager, un paso que
  Playwright no ve. La prueba real es medir en PÍXELES FÍSICOS del frame
  capturado: un texto de `font-size: 16px` midió 25px de tinta (esperado
  ≈16×1.5=24px) en una grabación de `tests/fixtures/web/pagina.html`
  (`#medida-escala`), contra 16-17px sin el flag. Ver
  `test_el_texto_mide_mas_grande_que_1_a_1_por_el_scale_factor` en
  `tests/test_grabar_web_integracion.py`.
- **`context.add_init_script` no corre sobre la página que Chrome YA cargó**: el
  `--app=<url>` navega ANTES de que Playwright se conecte por CDP, así que el
  script que neutraliza diálogos y dibuja el cursor sólo se aplica a
  navegaciones futuras. `Toma.__init__` hace un `page.reload()` después de
  registrarlo, a propósito: sin eso, el primer click revienta con
  `window.__tomaCursor is undefined`.
- **El click real nunca usa una coordenada capturada antes.** `click(objetivo)`
  anima el cursor dibujado hacia el centro calculado al principio (para que se
  vea bien en cámara), pero el click EN SÍ va por `Locator.click()`, que vuelve
  a resolver el elemento y espera a que esté "estable" recién al momento de
  clickear. Un modal que crece 145px entre el cálculo del centro y el click
  real desalineó así todos los clicks siguientes en una toma anterior
  (CLAUDE.md §4.10); con `page.mouse.click(x, y)` a la coordenada vieja, vuelve
  a pasar.
- **Tipear en un editor CodeMirror-like: clickear `.cm-line`, no el wrapper.**
  Clickear el `<div contenteditable>` grande puede dejar el caret fuera de la
  línea (en un hijo vacío, fuera del flujo de texto). `escribir()` busca
  `.cm-line` adentro del objetivo y clickea ESE elemento antes de tipear, y
  verifica el resultado leyendo ese mismo `.cm-line` (igual que
  `references/guion-y-edicion.md` describe para la fuente de datos del zoom:
  nunca a ojo).
- **`grabar_iniciar` pisa `DISPLAY` del proceso, no sólo el de Chrome.**
  `rec.py`/`plataforma.cmd_captura` arman el comando de `x11grab` leyendo
  `os.environ["DISPLAY"]` AL MOMENTO de arrancar la captura — el display de la
  Toma (`:2`, Xephyr) y el del proceso Python que corre el script pueden ser
  distintos (p.ej. el script corre con el `:1` real del host bajo Wayland).
  Sin pisarlo, `rec.py` graba la pantalla EQUIVOCADA: un `.mkv` que abre bien
  pero sale **negro**, el mismo síntoma de "Wayland sin Xephyr" pero disparado
  desde adentro de `Toma` en vez de por el entorno del shell. `grabar_iniciar`
  lo pisa con el `display` de la Toma y lo restaura después de arrancar.
- **Diálogos nativos: el override es la defensa real, `page.on("dialog")` es
  la red de seguridad.** `alert()`/`confirm()`/`print()`/`prompt()` se
  reemplazan en el `window` de la página ANTES de que el navegador pueda abrir
  el cartel nativo (confirm devuelve `true`, prompt saca la próxima respuesta
  de una cola). Si de todas formas se dispara un diálogo nativo (algo que
  bypasee el override), `Toma` lo acepta para no colgar el proceso y la
  PRÓXIMA acción (`click`/`escribir`/`ir`) revienta con `DialogoNativoError` en
  vez de seguir grabando una página congelada — nunca se entrega una toma con
  un diálogo nativo sin que algo lo haya marcado.
- **`entradas(lista)` encola, no reemplaza.** Llamarlo varias veces ACUMULA
  respuestas en la cola de `window.prompt()` (la Plataforma usa `prompt()`
  nativo para el `input()` de Pyodide); si una toma hace más `prompt()` que
  `entradas()` encoladas, la cola se vacía y el próximo `prompt()` devuelve
  `null` — eso es session de guion, no bug de `grabar_web.py`: encolar antes
  de cada paso que vaya a preguntar.

## Comandos de entorno, grabación y manejo del agente

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
```

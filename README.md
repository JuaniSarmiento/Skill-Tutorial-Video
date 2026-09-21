# tutorial-video-agente

Skill de [Claude Code](https://claude.com/claude-code) para producir series de video-tutoriales
sin editor de video: graba la pantalla, controla al agente o al editor, corta por segmentos,
narra con TTS y entrega los `.mp4` con subtítulos.

Está hecha para el caso en que **la clase la da una máquina y el guion lo escribe otra**: se
graba una sesión larga, se marca lo que importa, y después se destila en videos de cinco
minutos con voz de profe. Nació grabando a un agente resolviendo un proyecto en la terminal
y hoy también graba código escribiéndose en VS Code.

> Probada en producción: dos series terminadas, 14 videos, unos 48 minutos.
> La última reemplaza una clase virtual de una materia de la UTN.

---

## La idea que la hace distinta: la imagen se mide con la voz

Casi todo editor hace lo contrario: primero el video, después la narración encima, y quedan
silencios de relleno o voz apurada.

Acá el orden es al revés. Para cada segmento del guion:

1. se genera el audio y **se mide**,
2. el tramo de video correspondiente **se estira o se acelera** hasta durar lo mismo,
3. se concatenan los tramos y se pega la voz.

Consecuencias prácticas: no hay silencios muertos, no hay que calzar nada a mano, y **cambiar
de voz re-arma la película entera** porque los tiempos cambian. Por eso cada voz tiene su
propio `video-<voz>.mp4`.

---

## Qué produce

```
videos/u6-p3/
├── seg/00.mp4 … 09.mp4     un archivo por segmento, ya estirado al audio
├── joven/00.wav … 09.wav   la voz de cada segmento
├── video-joven.mp4         la imagen concatenada
├── final-joven.mp4         ← el entregable
└── final-joven.srt         subtítulos, generados del mismo guion
```

---

## Requisitos

**Los dos sistemas**

| Qué | Para qué |
|---|---|
| `ffmpeg` · `ffprobe` | grabar, cortar, concatenar |
| `python3` | los scripts |
| `tesseract` | el barrido OCR de privacidad |
| una API de TTS | Fish Audio o ElevenLabs. También corre `piper` local |

**Sólo Linux**

| Qué | Para qué |
|---|---|
| `xdotool` · `wmctrl` | tipear y mover ventanas |
| `Xephyr` · `openbox` · `xterm` | **sólo bajo Wayland**, ver abajo |

```bash
# Linux
sudo apt install ffmpeg xdotool wmctrl xserver-xephyr openbox xterm tesseract-ocr

# Windows: nada más que esto. La entrada va por ctypes, que es librería estándar.
winget install Gyan.FFmpeg
winget install UB-Mannheim.TesseractOCR
```

Antes de grabar, en cualquiera de los dos:

```bash
assets/scripts/plataforma.py info
```

Te dice qué sistema detectó, qué herramientas faltan, con qué comando va a
capturar, y si estás en Wayland te avisa antes de que grabes una hora de negro.

La key del proveedor va en `~/.config/<proveedor>/api_key` con `chmod 600`.
**Nunca en un script ni en un guion.**

---

## Instalación

```bash
git clone https://github.com/JuaniSarmiento/Skill-Tutorial-Video.git \
  ~/.claude/skills/tutorial-video-agente
chmod +x ~/.claude/skills/tutorial-video-agente/assets/scripts/*
```

Claude Code la descubre sola por el frontmatter de `SKILL.md`. Se dispara con cosas como
"grabá un tutorial de X", "narrá estos videos", "cambiá la voz".

---

## Arranque rápido

```bash
export TUT_ROOT=~/Proyectos/mi-tutorial     # ahí viven raw/, guion/, videos/
S=~/.claude/skills/tutorial-video-agente/assets/scripts

# 0. diagnóstico: qué sistema, qué falta, con qué va a capturar
$S/plataforma.py info

# 0b. SÓLO Linux con Wayland. En Windows saltealo: gdigrab captura el real
$S/entorno.sh start                          # imprime el DISPLAY a usar

# 1. grabar, marcando lo que pasa  (rec.py anda en los dos sistemas)
$S/rec.py start v01
$S/rec.py mark v01 "escribe el modelo"
$S/rec.py stop v01

# 2. escribir guion/v01.json mirando FRAMES, no las marcas (ver abajo)

# 3. renderizar
$S/editar.py imagen v01 joven
$S/editar.py voz    v01 joven                # deja final-joven.mp4 + .srt
```

---

## El guion

Un JSON por video. Cada segmento toma un tramo del crudo y le pone un texto:

```json
{
  "raw": "raw/v01.mkv",
  "segmentos": [
    {
      "tipo": "titulo",
      "titulo": "Unidad 6 · Muchos a muchos",
      "subtitulo": "Primero nos equivocamos a propósito",
      "min": 3,
      "texto": "Lo que se dice sobre la placa de título."
    },
    {
      "inicio": 52.4,
      "fin": 84.4,
      "decimar": false,
      "zoom": { "x": 18, "y": 60, "w": 1150, "h": 650 },
      "texto": "Lo que se narra mientras se ve ese tramo."
    }
  ]
}
```

| Campo | Qué hace |
|---|---|
| `inicio` / `fin` | segundos del crudo. Los tramos **no tienen que ser contiguos**: así se saltean las tomas fallidas y el tiempo muerto |
| `texto` | lo que dice la voz. Define la duración del segmento |
| `zoom` | recorta esa región y la agranda a pantalla completa. Sin esto, cuando la voz dice "mirá esta línea" nadie sabe dónde mirar |
| `decimar` | `mpdecimate` salta frames quietos. Ponelo en `false` en tramos de tipeo o las pausas intencionales desaparecen |
| `tipo: "titulo"` | placa generada, sin video |

El guion es lo único que vale la pena versionar: `raw/` y `videos/` pesan y se regeneran.

---

## Los scripts

**Plataforma, entorno y captura**

| | |
|---|---|
| `plataforma.py` | **los tres verbos que dependen del sistema**: capturar, tipear, enfocar. `info` diagnostica antes de grabar |
| `rec.py` | `start\|mark\|stop`. Multiplataforma. Graba y anota marcas de tiempo |
| `rec.sh` | lo mismo en bash, sólo Linux |
| `entorno.sh` | `start\|chrome\|status\|stop`. Xephyr para grabar bajo Wayland. **Sólo Linux, y en Windows no hace falta** |
| `shot.sh` · `bot.sh` | capturas sueltas (Linux). En cualquier sistema: `plataforma.py captura` |

**Manejar un agente (opencode / Claude Code)**

| | |
|---|---|
| `ty.py` | tipea en una terminal real. No-ASCII de a un carácter, que xdotool los pierde en ráfaga |
| `ty-cdp.py` · `click-cdp.py` | lo mismo para apps Electron, por Chrome DevTools Protocol |
| `oclog.py` · `ocwatch.py` · `lastq.py` | siguen al agente leyendo su SQLite, no con capturas |
| `drive.sh` · `drive-cdp.py` | aprueban permisos seguros y **frenan** ante uno riesgoso |
| `allow.sh` · `answer.sh` · `cmd.sh` | responden diálogos puntuales |

**Manejar VS Code**

| | |
|---|---|
| `codigo-vscode.py` | escribe código con verificación de punta a punta. `--crear` crea el archivo con `touch` en cámara |
| `term-vscode.py` | corre un comando en la terminal integrada, vía Command Palette |

**Editar y verificar**

| | |
|---|---|
| `editar.py` | `imagen` y `voz`. El corazón de todo |
| `verificar_voz.py` | transcribe con Whisper y marca las alucinaciones del TTS |
| `censurar.py` | busca credenciales con OCR y las tapa con una caja por tramo |

---

## Voces

`editar.py` trae varias y se le agregan más en un diccionario. La principal es
`joven` (Fish Audio, "Narrador Joven argentino"), a `speed 0.90` y pausas de 0.55 s,
unas 170 palabras por minuto.

**`speed` no significa lo mismo en dos voces distintas.** Con el mismo `0.8` las candidatas
fueron de 87 a 133 palabras por minuto. Si una suena arrastrada es la voz, no el parámetro.

Y calibrá contra cómo se mira: quien estudia pone el video a 1.25, así que una voz lenta
termina reproducida a una velocidad que vos nunca elegiste. Mejor que ya salga bien.

> **Nunca voces de famosos ni clones de personas reales sin consentimiento**, ni en joda.
> Los IDs de `references/voces.md` son del catálogo público del proveedor.

---

## Lo que costó caro

Esta es la parte que justifica el repo. Cada línea es un fallo real, y casi todos
**fallaron en silencio**: produjeron archivos que parecían válidos.

### Wayland rompe todo, y no avisa

`x11grab` graba un rectángulo **negro** (brillo 0.0/255, un solo color) y `xdotool` sólo ve
ventanas Xwayland. No hay error: hay un `.mkv` de 300 MB que no se puede usar.

La salida es `entorno.sh start`, que levanta un X11 real dentro de una ventana. Render por
software, 30 fps sostenidos con un navegador scrolleando. Adentro:

- **`kitty` y `alacritty` no abren**: exigen OpenGL 3.3. El proceso vive, nunca crea ventana,
  no escribe un error. Va `xterm`.
- **Chrome ignora `DISPLAY`** y abre en el escritorio real. Necesita `--ozone-platform=x11`
  **y** `env -u WAYLAND_DISPLAY`. Con una sola de las dos, no alcanza.

### Electron ignora xdotool

La app de escritorio de OpenCode, y cualquier Electron, **filtra los eventos sintéticos de
XTEST**. X11 reporta que la ventana tiene foco y `xdotool type` no entrega un solo carácter.
Verificado con foco forzado y a cuatro velocidades.

Se entra por **Chrome DevTools Protocol** (`--remote-debugging-port=9222`), que va por dentro
de la app y **no depende del foco de ninguna ventana**.

### VS Code: `Ctrl+P` no crea archivos

De cuatro formas de crear un archivo, una sola sirve para automatizar:

| Forma | Qué pasa |
|---|---|
| "File: New File" del Command Palette | escribe el texto **"New File" adentro del código** |
| `code archivo.py` | abre un editor, el archivo **no existe hasta que guardás** |
| click derecho en el explorador | necesita coordenadas, y el explorador está oculto |
| **`touch archivo.py` en la terminal** | **crea el archivo en disco, verificable** |

Y `touch` encima es didáctico: quien mira ve cómo se crea un archivo desde la terminal.

Otras dos del mismo editor:

- **`Ctrl+grave` no abre la terminal con teclado latinoamericano.** El comando termina tipeado
  adentro del archivo de código. Todo lo que toque la terminal va por el Command Palette.
- **El buffer sucio sobrevive a matar el proceso.** `hotExit` lo guarda en `Backups/` y lo
  resucita idéntico. Y con un buffer sucio el Command Palette se come los comandos: quedan
  líneas como `KAll Terminals` en medio del código. Va `"files.hotExit": "off"`.

### Escribir a ciegas falla en silencio

Cuatro veces seguidas el texto terminó en el archivo equivocado o en la terminal, sin un solo
error, y se descubrió recién al correr el código. Por eso `codigo-vscode.py` verifica tres
cosas antes de tipear una letra: que el archivo **exista**, que la ventana muestre **ese**
archivo, y que después de guardar el contenido **esté en disco**.

### El guion se escribe mirando frames, no marcas

Las marcas dicen cuándo pasó algo, no qué se ve. Entre dos marcas puede haber diez minutos de
pantalla congelada esperando un permiso. Un guion escrito desde las marcas **narra cosas que
en pantalla no ocurren**, y eso sólo se descubre cuando alguien mira el video terminado.

Antes de cada segmento: `ffmpeg -ss <t> -i raw.mp4 -frames:v 1` y mirar. Si tres frames del
mismo tramo son idénticos, ahí no pasa nada.

### Un render por vez

Dos `editar.py imagen` sobre el mismo video **se borran los `.tmp.mp4` entre ellos**, y el
segundo muere con un `FileNotFoundError` que no dice nada del problema real. Pasa fácil con
`nohup … &`, porque `$!` y el pid que devuelve `pgrep` no son el mismo proceso. Esperá por
**ausencia de proceso**, no por un pid.

### `pkill -f` se mata a sí mismo

`pkill` compara contra la cmdline completa, así que un script que contiene el patrón se mata
solo (exit 144). Va `pkill -x <exe>` o verificar `/proc/<pid>/exe`.

---

## Privacidad: lo que se filma no se puede despublicar

Tres cosas se colaron en videos ya renderizados y **ninguna se habría visto mirando el
material por encima**. Aparecieron buscándolas con OCR.

- **El token no está donde lo buscás.** Aparece en el mensaje del chat donde se lo pegaste al
  agente, que queda scrolleado y visible medio video, no sólo en el comando que lo usa. En una
  tanda apareció en **75 frames de 4 videos**.
- **Telegram Web muestra la lista de contactos** con nombres reales en la barra izquierda.
- **Verificá con OCR, no a ojo.** Un barrido con `tesseract` cada 2 s sobre el video terminado.
  Es la única forma de saberlo.

Para tapar, `censurar.py` emite **una caja por tramo, nunca una sola**: el texto se mueve con
el scroll, y unir todas las posiciones detectadas en un rectángulo tapaba el 60% de la
pantalla. Caja negra sólida, no desenfoque: un blur suave deja legible un número grande.

Los patrones a tapar **no van en el código**, van en un archivo fuera del repo:

```bash
mkdir -p ~/.config/tutorial-video && chmod 700 ~/.config/tutorial-video
cat > ~/.config/tutorial-video/secretos.txt <<'EOF'
1234567890     # prefijo del token, alcanza el fragmento
micorreo       # usuario del mail
EOF
chmod 600 ~/.config/tutorial-video/secretos.txt
```

Y **volvé a barrer el video ya censurado**. Dar por buena la censura sin verificarla es el
mismo error que dar por buena la grabación sin mirarla.

---

---

## Windows

Anda, y con una ventaja: **todo el problema de Wayland desaparece.** `gdigrab`
captura el escritorio real, así que no hace falta Xephyr ni nada anidado.

La skill se apoya en tres verbos que dependen del sistema, y viven aislados en
[`plataforma.py`](assets/scripts/plataforma.py). El resto — `editar.py`,
`censurar.py`, `verificar_voz.py`, los scripts de CDP — es ffmpeg y Python puro
y corre igual en los dos lados sin una línea de diferencia.

| verbo | Linux | Windows |
|---|---|---|
| capturar | `x11grab` | `gdigrab -i desktop` |
| tipear | `xdotool type` | `SendInput` con `KEYEVENTF_UNICODE` |
| enfocar | `wmctrl -a` | `SetForegroundWindow` |

**No hace falta instalar ninguna librería de Python.** La entrada va por `ctypes`
contra `user32`, que viene con Python: nada de pyautogui ni pywin32.

**Las tildes salen mejor que en Linux.** `KEYEVENTF_UNICODE` manda el codepoint
en vez de una tecla, así que no depende del layout del teclado. En Linux hay que
forzar `setxkbmap -layout latam` o xdotool escribe `@` donde va `"`.

Dos diferencias que la skill ya contempla:

- La terminal integrada de VS Code es PowerShell, donde `touch` no existe: va
  `ni`, el alias de `New-Item`. `codigo-vscode.py` lo distingue solo.
- Los `.sh` son de Linux. El reemplazo multiplataforma de `rec.sh` es
  [`rec.py`](assets/scripts/rec.py), con los mismos tres verbos. Los que manejan
  opencode por terminal no tienen equivalente: en Windows se maneja por CDP, que
  ya es portable.

> **Sin probar en Windows todavía.** La rama Linux está probada de punta a punta;
> la de Windows está escrita contra la API de Win32 pero **nadie la corrió en una
> máquina Windows**. Empezá por `plataforma.py info` y una grabación corta con
> `rec.py` antes de confiarle una serie entera. Si algo falla, es un issue y se
> arregla: el diseño ya está separado.

## Límites

- **En Linux es X11.** Bajo Wayland funciona sólo adentro de Xephyr. En Windows no aplica.
- **Nadie toca la máquina mientras `xdotool` escribe**: las teclas van a la ventana con foco.
  Con Xephyr pesa menos, pero adentro el foco sigue siendo uno solo.
- **En Linux, un layout de teclado único.** Con `us,latam,us` xdotool escribe `@` en vez de `"`. En Windows no pasa: se tipea por codepoint.
- **Publicar requiere OK explícito.** La skill nunca sube nada por su cuenta.
- El TTS alucina: repite palabras, alarga frases. Por eso existe `verificar_voz.py`.

---

## Licencia

Apache-2.0. Ver [LICENSE](LICENSE).

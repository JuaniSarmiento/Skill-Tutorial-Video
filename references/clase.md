# Clase con personaje (vertical, Remotion)

Un video vertical (1080×1920, 30 fps) donde un personaje ilustrado presenta un tema frente a una
pizarra blanca: la boca se mueve con la voz, cambia de pose por segmento (con un rebote), la cámara
corta entre el plano general, la pizarra y el primer plano del personaje, y en la pizarra se escribe
con fibrón, se arma un diagrama de flujo, se tipea el código real y se ve su salida real en una
terminal. Música y efectos sintetizados, subtítulos palabra por palabra.

Todo sale de un guion JSON (`"formato": "clase"`) con un solo comando. El guion elige personaje,
vestuario y fondo de una **biblioteca**; lo que no está, lo dibuja el **generador de imágenes** una
vez y queda guardado para el próximo video.

## Comandos

```bash
S=<skill>/assets/scripts
TUT_ROOT=<serie> uv run $S/clase.py reparto guion/clase-01.json            # resuelve y genera lo que falta
TUT_ROOT=<serie> uv run $S/clase.py props   guion/clase-01.json -o props.json   # voz, tiempos, boca (para inspeccionar)
TUT_ROOT=<serie> uv run $S/clase.py render  guion/clase-01.json -o clase-01.mp4
```

- `clase.py` declara sus dependencias (PEP 723): `uv run clase.py` alcanza.
- `render` hace `reparto` y `props` si hace falta y deja el mp4 (sin `-o`, en
  `TUT_ROOT/videos/<guion>/<guion>.mp4`). La primera vez instala el motor de Remotion
  (`assets/remotion/`, `npm ci`; hace falta Node.js) y Remotion baja su Chrome headless.
- La voz se cachea por texto en `TUT_ROOT/videos/<guion>/voz/`: correr `props` y después `render` no
  la paga dos veces, y cambiar una frase regenera sólo esa.
- Las rutas relativas del guion (`codigo`) se resuelven contra `TUT_ROOT`.
- Antes de gastar nada (voz, imágenes, render) se valida el guion: una pose que el personaje no
  tiene y sin descripción para generarla, una cámara o escena que no existe, un archivo de código que
  falta, fallan con un mensaje que nombra el problema.

## El guion

```json
{"formato": "clase", "titulo": "¿Qué es un condicional?",
 "personaje": "profe", "vestuario": "base", "fondo": "aula-pizarra",
 "voz_id": "<id de una voz de Fish Audio>", "velocidad": 1.15,
 "codigo": {"edad": "codigo/edad.py"},
 "pronunciacion": {"while": "guáil"},
 "segmentos": [
  {"texto": "¿Cómo decide un programa qué hacer? Con un condicional.", "pose": "pensar", "camara": "profe",
   "escena": {"tipo": "pizarra", "texto": "¿Condicional?"}},
  {"texto": "Pregunta algo: si la respuesta es sí, hace una cosa; si es no, hace otra.", "pose": "senalar",
   "camara": "normal", "escena": {"tipo": "diagrama", "condicion": "edad >= 18", "si": "Puede votar", "no": "Todavía no"}},
  {"texto": "En Python se escribe con if y else.", "pose": "tipear", "camara": "pizarra",
   "escena": {"tipo": "codigo", "archivo": "edad"}},
  {"texto": "Lo corres, y como la edad es veinte, puede votar.", "pose": "festejar", "camara": "pizarra",
   "escena": {"tipo": "terminal", "archivo": "edad"}}
 ]}
```

Arriba del guion:

| Campo | Qué es |
|---|---|
| `personaje`, `vestuario`, `fondo` | nombres de la biblioteca (`vestuario` por defecto `base`), o lo nuevo con descripción (ver abajo) |
| `voz_id` | **obligatorio**: id de la voz en la biblioteca de Fish Audio (no hay voz por defecto). La key se lee de `~/.config/fish/api_key` |
| `velocidad` | aceleración de la voz ya generada (`atempo`, no cambia el tono). Por defecto 1.0 |
| `codigo` | `{nombre: ruta}`: el archivo se muestra tal cual y se ejecuta con `python3` (timeout 30 s) para la terminal |
| `pronunciacion` | `{palabra: cómo decirla}` sólo para el TTS (palabra entera); los subtítulos muestran el texto original |
| `poses` | `{pose: descripción}` para pedir una pose que no está entre las conocidas |

Cada segmento:

| Campo | Qué es |
|---|---|
| `texto` | lo que dice la voz (una idea, 3-6 s) |
| `pose` | `parado`, `senalar`, `pensar`, `tipear`, `sorprenderse`, `festejar` u otra con descripción en `poses`. `luego: [{"pose", "cue"}]` la cambia en una palabra |
| `camara` | `profe` (primer plano del personaje), `normal` (plano general) o `pizarra` (acercamiento a la pizarra) |
| `planos` | opcional: `[{"cue": "palabra", "camara": "profe"}]` cortes propios dentro del segmento |
| `escena` | lo que se ve en la pizarra (abajo) |
| `sfx` | opcional: `[{"tipo": "boing", "cue": "palabra"}]` además de los automáticos (`marcador`, `pop`, `ding`, `whoosh`, `teclas`, `boing`) |
| `pausa` | opcional: segundos de silencio extra al final, para que respire un remate |

Escenas (`escena.tipo`):

- `pizarra`: `texto` (o `lineas: [...]`) escrito con letra de fibrón, que se subraya y se adorna
  mientras habla. Sólo para palabras: **nunca código con letra de mano**.
- `diagrama`: `condicion` (en letra de código, dentro del rombo), `si`, `no`; se dibuja el rombo,
  las flechas a «Sí» y «No» y una ficha que recorre `camino` (`si` por defecto).
- `codigo`: `archivo` (un nombre de `codigo`): editor claro, JetBrains Mono sin ligaduras, 40 px o
  más, que se tipea línea por línea durante la voz.
- `terminal`: `archivo`: el código arriba y la terminal con `$ python3 <archivo>` y su salida real
  línea por línea.

Cada paso entra repartido a lo largo de la voz; para atarlo a una palabra, `cue_<paso>` en la
escena: `cue_si`, `cue_no`, `cue_ficha` (diagrama), `cue_linea0`..., `cue_subrayado` (pizarra),
`cue_salida`, `cue_remate` (terminal). La cue es una frase que el segmento dice literalmente.

## La biblioteca (`TUT_REPARTO`)

Las imágenes pesan: viven fuera del repo de la skill, en `TUT_REPARTO` (por defecto
`~/.local/share/tutorial-video/reparto/`). Su índice es `catalogo.json`, con rutas relativas:

```json
{"personajes": {"profe": {"referencia": "personajes/profe/referencia.png", "descripcion": "...",
    "vestuarios": {"base": {"poses": {"parado": {"cerrada": "personajes/profe/base/parado-cerrada.png",
        "abierta": "personajes/profe/base/parado-abierta.png", "boca": [x, y, w, h], "prompt": "..."}}}}}},
 "fondos": {"aula-pizarra": {"archivo": "fondos/aula-pizarra.png", "prompt": "...", "pizarra": [x, y, w, h]}}}
```

- Cada pose tiene dos PNG transparentes del mismo tamaño (lienzo 960×1440, pies en y=1400):
  `cerrada` y `abierta`. La abierta es la cerrada con **sólo la caja `boca`** de la abierta pegada:
  las dos son idénticas fuera de la boca y el personaje no tiembla al hablar.
- El fondo es 1080×1620; `pizarra` es el interior blanco de la pizarra (se detecta solo; si no se
  encuentra, se usa el del aula de ejemplo).

### Pedir algo nuevo

Lo nuevo se pide con una descripción; `reparto` lo genera **una vez** y la segunda corrida lo reusa:

```json
"vestuario": {"nombre": "invierno", "descripcion": "con bufanda roja y gorro de lana"}
"fondo": {"nombre": "laboratorio", "descripcion": "un laboratorio de computación con una pizarra blanca"}
"personaje": {"id": "profa", "descripcion": "una profesora de pelo corto violeta y anteojos"}
```

- **Vestuario nuevo**: por cada pose que usa el guion, dos imágenes con la referencia del personaje
  adjunta: la cerrada y la abierta (su prompt dice «boca abierta» y adjunta también la cerrada). Se
  recortan (fondo blanco conectado con el borde → transparente), se alinean los pies, se busca la
  caja de la boca y se guarda el prompt en el catálogo.
- **Fondo nuevo**: una imagen; al prompt se le suma el estilo (pastel claro, pizarra blanca grande y
  vacía, sin texto ni personas, vertical).
- **Personaje nuevo**: primero su `referencia` y después las poses del vestuario `base` con esa
  referencia. Mirá la referencia antes de usarlo en serio: si no gusta, se borra del catálogo y se
  pide de nuevo.
- Es **transaccional**: todo se arma en un directorio temporal y recién al final se copian los
  archivos y se reescribe el catálogo. Si el generador falla o no existe, el error nombra lo que
  faltaba y la biblioteca queda como estaba. Nunca se inventa un reemplazo.

### El generador (`TUT_GENERADOR`)

Un comando `<cmd> --prompt <texto> --salida <png> [--referencia <png>]...` que sale con 0 y deja el
PNG. Por defecto es `assets/scripts/generar_imagen.py`, un envoltorio de `codex exec` con su
herramienta de generación de imágenes: copia las referencias a un directorio temporal, le pasa el
encargo por stdin (si stdin no se cierra, codex se queda esperando) y copia el PNG. Para usar otro
generador, `TUT_GENERADOR="python3 mi_generador.py"`. `TUT_GENERADOR_TIMEOUT` (s) limita cada imagen.

## Lo que ya se aprendió (la prueba piloto)

- **Los cortes los da la cámara.** Un plano quieto con un personaje que sólo mueve la boca cansa en
  dos segundos. El guion elige la cámara de cada segmento; `clase.py` suma un corte a mitad de los
  segmentos largos y siempre devuelve el primer plano al plano general (si no, lo que se escribió en
  la pizarra durante ese segmento no se ve nunca). Apuntá a un corte cada 4-5 s; `planos` agrega los
  tuyos en una palabra (un primer plano del personaje en el chiste).
- **La pizarra nunca arranca vacía.** El primer elemento de cada segmento entra cuando el segmento
  arranca, no cuando la voz llega a nombrarlo; en el primer segmento ya está escrito en el cuadro 1.
- **El código va en letra de código.** La letra de mano es ilegible para código (y para la condición
  del diagrama): JetBrains Mono, sin ligaduras (`>=` tiene que verse como dos signos), 40 px o más.
- **Palabras en inglés.** El TTS en español puede leer mal `while`, `print` o `else`: escuchá el
  segmento y agregá la palabra a `pronunciacion` (sólo cambia lo que oye el TTS; el subtítulo y el
  código quedan bien escritos).
- **Subtítulos centrados** abajo (y=1380-1560), una palabra resaltada a la vez, tarjeta clara con
  borde oscuro para que se lean sobre el fondo pastel. Nada importante arriba de y=200 ni pegado a
  los bordes.
- **El personaje no se corta en los zooms**: el primer plano encuadra cabeza y torso con margen
  arriba; el acercamiento a la pizarra lo deja con la cabeza a la vista.
- **El AAC sube el pico.** El audio se normaliza a -16 LUFS con el limitador apuntando a -3 dBTP y
  se mide sobre el mp4 final: si el pico pasó de -1,5 o el integrado se corrió, se corrige y se
  vuelve a codificar.

## Revisar antes de entregar

- Hoja de contacto de 16 cuadros y 3 cuadros a resolución completa, mirados: ¿se lee en un celular?
  ¿hay algo pegado a un borde? ¿la pizarra se ve cuando la voz la nombra?
- `ffmpeg -i video.mp4 -af ebur128=peak=true -f null -` → I ≈ -16 LUFS, pico ≤ -1,5 dBTP.
- Para iterar la imagen sin re-renderizar todo: `props` y después `npx remotion still` de cuadros
  sueltos desde `assets/remotion/` (`--props=<props.json> --public-dir=<dir con fondo, poses y fuentes>`).

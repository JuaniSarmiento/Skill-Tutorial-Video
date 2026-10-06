## El guion y `editar.py`

- **Encoder de video** (`editar.py`, `escena.py`): `TUT_ENCODER` elige `software` (libx264,
  default, idéntico a como salía antes) | `auto` (VAAPI si el GPU codifica h264 de verdad,
  probado codificando 1 cuadro; si no, libx264 con un aviso) | `vaapi` (exige VAAPI, aborta
  antes del primer tramo si no hay). `TUT_VAAPI_DEVICE` pisa `/dev/dri/renderD128`. Vacía o con
  mayúsculas/espacios (`""`, ` AUTO `) se normaliza igual que sin definirla. Si VAAPI falla a
  mitad de un tramo, el error sugiere `TUT_ENCODER=software` (nunca mezcla encoders a mitad
  de un render: rompe G4). Cada llamada a ffmpeg de `editar.py` (incluido `musica.py`, QA
  04/10/2026) pasa por `editar.run()`, que vigila el PROGRESO, no el tiempo total
  (`TUT_FFMPEG_TIMEOUT`, default 120 s = segundos SIN avance): un render largo que progresa
  nunca falla por tardar; si se cuelga de verdad (deadlock, 0% CPU, sin salida), falla
  nombrando el comando en vez de colgar el proceso para siempre. `escena.py`
  (`subprocess.Popen` en el loop de cuadros) y `encoder.py` (`subprocess.run` para probar
  VAAPI) NO pasan por `editar.run()`: tienen su propio manejo de proceso, sin ese vigía.
- **Velocidad de la voz** (`editar.py imagen`/`voz`, `preparar()`): `"velocidad_voz"` arriba del
  guion (número > 0) pisa el default; sin la clave, **1.25** para las voces TTS (`argentina`,
  `joven`, `profe`, `fish`, `daniela`, `elevenlabs` — Juani la escucha mejor así: la probó en el
  reproductor a 1.25x, aceleración sin cambio de tono) y **1.0** para la voz grabada `juani` (no
  se mueve del default, así que G3 no cambia con el default solo). La voz se genera como
  siempre y se acelera DESPUÉS, con `atempo` (`editar.acelerar_voz`), nunca con el `speed` de
  Fish (`FISH_SPEED`): `speed` cambia la entonación, `atempo` sólo estira el tiempo (ver
  `references/voces.md`). El slot se mide sobre la voz YA acelerada y `palabras.py` transcribe
  esa misma voz, así los tiempos por palabra salen ya en la línea de tiempo acelerada sin
  escalar nada. Caché: `editar.acelerar_voz_cacheada` guarda la voz acelerada junto a la cruda
  como `NN-x<velocidad>.wav` con un sello (sha256 de la voz de origen) — cambiar la velocidad no
  reusa el archivo viejo (el nombre cambia) y si la voz de origen cambió (texto nuevo) el sello
  lo nota y se re-acelera. `velocidad_voz` inválida (≤ 0, algo que no es un número) aborta con
  "velocidad_voz" en el mensaje, antes de generar nada.
- **Fuente de datos del zoom** (`editar.py zonas`, `zonas.py`): `rec.py` no guarda dónde tipea
  ni dónde clickea (grabó con `-draw_mouse 0`), así que los momentos clave para el zoom
  automático (S7b) salen de **detectar cambios entre los cuadros del CRUDO** (decisión Q5 de
  Juani, `docs/explicador/HITO2.md`): funciona con lo que ya está grabado, en Linux y en
  Windows. `editar.py zonas vNN` analiza, por cada segmento de pantalla (los títulos y las
  escenas no usan crudo), el tramo `[inicio, fin)` de su crudo y deja
  `videos/<vNN>/zonas/NN.json`: una lista de momentos
  `{"t", "x", "y", "w", "h", "importancia"}`, donde `t` está en el eje del propio crudo (el
  mismo que `seg["inicio"]`/`seg["fin"]`, ANTES de `mpdecimate`) y `x`/`y`/`w`/`h` son una caja
  en píxeles del crudo sin escalar (misma convención que el `"zoom": {x,y,w,h}` fijo). Se
  escala cada eje por separado (ancho y alto reales del crudo contra el ancho/alto de la
  grilla reducida de análisis): con una sola escala para los dos ejes, redondear el alto a
  un entero par corre la caja en resoluciones no 16:9 (hasta ~30px en 3440x1440).
  Muestrea a pocos fps y en escala de grises, reducido con promedio de área (`flags=area`,
  no vecino más cercano: a 14-16px de fuente, "vecino más cercano" se queda con 1 de cada
  ~144 píxeles y el tipeo desaparece) para no depender de numpy y analizar rápido (un crudo
  de 10 min a 1080p, en segundos).

  El cambio entre dos cuadros se agrupa en **componentes conexas** (una dilatación chica
  junta letras de la misma línea sin unir dos cambios que están lejos de verdad, como un
  aviso en una esquina y la salida de un comando en otra) y cada componente se clasifica
  por separado contra un "estado estable" que se va actualizando POR REGIÓN, no entero:
  - **ruido** (cursor parpadeando, reloj): por debajo de un mínimo de píxeles cambiados,
    no se guarda y no mueve la base en esa región -así no estira la caja de un momento
    vecino que sí importa-.
  - **scroll**: un componente de varias filas donde el contenido nuevo es, en lo esencial,
    el viejo CORRIDO verticalmente (se prueban varios corrimientos y se mide cuánto no
    calza ni corrido) no es un momento, pero sí actualiza la base (si no, todo lo que
    venga después del scroll "cambiaría" para siempre contra la pantalla de antes). Mide
    el desplazamiento del contenido, no el área de la caja: una terminal con texto
    alineado a la izquierda da una caja angosta y alta que antes pasaba el filtro de
    "área grande" por accidente.
  - **parpadeo**: un cambio que ya volvió al estado estable en el cuadro siguiente (o que
    es la repetición exacta de un parpadeo ya confirmado antes, incluso si cae justo en
    el último cuadro de la secuencia y no hay un cuadro posterior para confirmarlo) es
    ruido, no un momento.
  - **momento de verdad**: lo que no entra en ninguna categoría anterior se guarda como
    momento y la base de esa región pasa a ser el nuevo estado.

  `importancia` mide píxeles CAMBIADOS de verdad en el componente (no el área de la
  caja que lo encierra): así un comando tipeado (muchos píxeles de varios caracteres)
  pesa más que un dígito de una barra de estado (un puñado de píxeles), aunque sus cajas
  fueran del mismo tamaño -el área de la caja sola premiaba scrolls y cajas unidas-.

  Sólo lee: no genera voces ni renderiza nada. No decide cuáles momentos usar ni limita la
  frecuencia entre acercamientos: eso es trabajo de S7b. Si falta el crudo de un segmento,
  si a un segmento le falta `inicio`/`fin` o tiene `inicio >= fin`, aborta nombrando el
  segmento (sin traceback); si `fin` va más allá de la duración real del crudo es un
  aviso, no un abort. Los `zonas/NN.json` de índices que ya no son de pantalla (guion
  editado después de la última corrida) se borran al regenerar.

**Editar**
- Idea central: la **imagen** se arma por voz con slots = duración de esa voz + margen corto; así no hay silencios de relleno y cambiar de voz = regenerar audio.
- Remuxear los `.mkv` a `.mp4` (`-c copy -movflags +faststart`) antes de cortar: `-ss` sobre mkv cortado por kill es impreciso.
- `mpdecimate` (`decimar: true`) sirve para saltar tiempo muerto: un agente pensando, una compilación. Pero **sólo si al tramo le sobra material**. Si el slot de voz supera al tramo, decimar lo vacía — ver el gotcha de abajo, que costó un render entero. `decimar: false` en tramos de navegador (las pausas son intencionales) y en terminales donde lo que se ve es texto quieto y no una espera.
- Voz educativa: speed **0.90** y pausas de 0.55 s (≈170 palabras/min). A 0.8 suena arrastrada:
  quien mira pone el video a 1.25 y entonces la voz ya no es la que elegiste. Por debajo de
  0.35 s de pausa suena apurado.
- Términos en inglés: con Fish escribirlos tal cual; siglas fonéticas (`opsx` → "o pe ese equis", `.md` → "punto eme de"). Piper necesita fonética ("esquils").

**Cuando el slot es más largo que el tramo, se congela EL ÚLTIMO FRAME**

Y por eso ese frame tiene que ser el que la voz está describiendo, no uno cualquiera
del tramo. Un segmento con 56 s de voz y 24 s de crudo pasa 32 s quieto en el frame
final: si ahí la página ya scrolleó a otra cosa, el video narra los tres pasos mientras
muestra otra sección, y no hay error que lo delate. Antes de fijar `fin`, sacar el frame
de ese segundo exacto y mirarlo.

**`decimar: true` en un tramo de terminal lo puede vaciar**

`mpdecimate` salta frames quietos, y una terminal está quieta casi todo el tiempo. Un
tramo de 47 s quedó reducido a unos pocos segundos de material y el segmento terminó
siendo **60 s de prompt vacío** mientras la voz explicaba el entregable. Se detecta
midiendo el brillo: `signalstats` clavado en el mismo valor durante seis muestras
seguidas es imagen congelada, no una pantalla oscura.

- Para un tramo de terminal: `decimar: false`.
- Y la toma **no termina con `clear` ni con un comando de salida corta** (`wc -l`), o
  el frame que se congela es la pantalla vacía. Que termine con contenido a la vista.

**Sincronía: escribir el guion mirando frames, no marcas**

Las marcas de `rec.sh` dicen cuándo pasó algo, no qué se ve. Entre dos marcas puede haber
diez minutos de pantalla congelada esperando un permiso. Un guion escrito desde las marcas
narra cosas que en pantalla no ocurren.

Antes de escribir cada segmento: `ffmpeg -ss <t> -i raw.mp4 -frames:v 1` y mirar el frame.
Si tres frames distintos del mismo tramo son idénticos, ahí no pasa nada y no sirve.

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

## Comandos de edición y verificación de voz

```bash
export TUT_ROOT=~/Proyectos/tutorial-X
export TUT_ENCODER=auto                   # auto|vaapi|software (default software, igual que antes de VAAPI)
export TUT_VAAPI_DEVICE=/dev/dri/renderD128  # sólo si el dispositivo no es el default
S=~/.claude/skills/tutorial-video-agente/assets/scripts

# remux + editar + verificar
for f in raw/*.mkv; do ffmpeg -y -i "$f" -c copy -movflags +faststart "${f%.mkv}.mp4"; done
$S/editar.py imagen v01 argentina && $S/editar.py voz v01 argentina   # argentina = voz principal (default)
uv run --with faster-whisper --with "av<19" python $S/verificar_voz.py argentina v01
ffmpeg -i videos/v01/final-argentina.mp4 -af silencedetect=noise=-40dB:d=0.9 -f null - 2>&1 | grep -c silence_end
```

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
- Explicar un tema que no es de pantalla (finanzas, biología, historia) con escenas animadas: ver Escenas.

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
- **Música de fondo** (`editar.py voz`, `musica.py`): `"musica": {"archivo", "debajo_de_la_voz_lu"?,
  "fundido"?}` arriba del guion (ver README → El guion); `"musica": false` en un segmento la apaga
  sólo ahí. `archivo` es relativo a `TUT_ROOT`; la música la pone quien arma el tutorial en
  `TUT_ROOT/musica/` (la skill no la trae, por licencia) y si falta o no se puede leer, aborta
  antes de generar nada. Ducking en rampa EN dB (no en escalón ni en amplitud lineal, QA
  04/10/2026): 18 LU bajo la voz mientras hay voz, 10 LU en los silencios
  (`debajo_de_la_voz_lu` sólo ajusta el primero); ataque rápido, liberación lenta
  (`ATTACK_S`/`RELEASE_S`, sin bombeo). El final sigue dando -16 LUFS / TP ≤ -1.5 dBTP
  igual que sin música: `musica.normalizar_dos_pasadas` mide con `loudnorm` de dos pasadas
  y aplica un limitador de TRUE PEAK aparte (una sola pasada no llega al integrado cuando el
  TP la restringe, QA 04/10/2026). Música más corta que el total: bucle con una UNIDAD sin
  costura (el crossfade aplicado una vez, no por vuelta -el costo no crece con la cantidad
  de vueltas); rechaza con `SystemExit` una música más corta que 2x el crossfade. Sin la clave `musica`
  el final pasa por las mismas dos pasadas (decisión del 04/10/2026: todo final a -16 LUFS),
  así que el audio del Hito 1 cambió a propósito; el video no.
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

## Escenas: segmentos que no son pantalla grabada

Un segmento con `"escena"` en vez de `inicio`/`fin` no se corta del crudo: se renderiza desde
una plantilla HTML (`assets/escenas/`) y dura su slot de voz, igual que cualquier tramo. Se
pueden mezclar con segmentos de pantalla en el mismo guion. Ejemplo completo, sin crudo:
`assets/guion-ejemplo/explicador-interes-compuesto.json`.

| `tipo` | Qué muestra | Elementos con `cue` |
|---|---|---|
| `presentacion` | título cinético + puntos (sin puntos: portada con `subtitulo`) | `puntos[]`, `subtitulo` |
| `diagrama` | nodos en fila y flechas que se dibujan | `nodos[]` (`id`, `texto`, `detalle`), `flechas[]` (`de`, `a`, `texto`) |
| `datos` | barras que crecen hasta su valor, con el número contando | `barras[]` (`etiqueta`, `valor`, `destacar`), `prefijo`, `nota` |
| `imagen` | metáforas dibujadas (SVG local), una fila, cada una con su rótulo | `dibujos[]` (`id`, `svg`, posición `x`/`y`? opcional), `rotulos[]` (`texto`, `de`) |

- **`cue` es la frase que nombra al elemento**, tal cual la dice el `texto` del segmento
  (`"cue": "tres décadas"`), o un número de segundos. El elemento entra en esa palabra.
  Se resuelve transcribiendo la voz con faster-whisper. Lo que Whisper oye mal se
  tolera así: una palabra de 6+ letras admite 1 error ("tembrano"). Si la cue tiene
  además un **ancla** (otra palabra suya de 4+ letras oída exacta, que no sea artículo),
  se admite 1 error en una palabra de 5 letras o menos ("más que poner" ← "las que
  poner") y hasta 2 en una de 6+ ("Hagamos números" ← "Hablamos números"). Una cue
  de una sola palabra corta y los números van exactos ("sí"≠"sin", "10"≠"100"). Los
  números se comparan en dígitos: "17 .000", "17.000", "17000" y "diecisiete mil" son
  el mismo ("por ciento" no se convierte). Sólo se unen los miles con punto y
  exactamente tres dígitos detrás: "100, 200" y "3 100" son dos números, y una coma
  entre dígitos es decimal ("2,500" es dos coma cinco y no matchea "2500"). **Costo**: dos errores sin ancla no se
  resuelven ("pesa más" ← "pesan las"). **Nunca anclan** (`NO_ANCLAN` en `palabras.py`):
  los artículos (el, la, los, las, lo, un, una, unos, unas), las contracciones al y del,
  y los demostrativos (este, ese, aquel y sus formas). Van delante de cualquier
  sustantivo, así que oírlos exactos no dice nada de la palabra que sigue: "unas tasas"
  no es "unas casas", igual que "la tasa" no es "la casa". "esta" también es "está" sin
  tilde y pierde el ancla: es más estricto, no más laxo. Si una cue no se encuentra, el error muestra
  qué se oyó: corregí la cue, no el guion.
- **Hoja de contacto antes del render**: `editar.py escenas vNN VOZ` genera las voces y deja
  cada spec resuelto en `videos/vNN/escenas/`; imprime el comando de `escena.py contacto`.
  Mirá el PNG (10/50/90 % de cada escena) y recién ahí `editar.py imagen`.
- **Título largo**: el contenido de las tres plantillas arranca debajo de la cabecera
  medida (kicker + título, con 40 px de aire), así que un título de 4 renglones baja
  los nodos, los puntos o las barras en vez de quedar tapado. Si desde ahí no queda
  lugar (un nodo o un renglón al piso de 24 px, o 240 px de gráfico), la escena falla
  nombrando el título.
- **Estilo**: `brand.json` en `TUT_ROOT` pisa lo que declare de `assets/escenas/brand.json`
  (colores, `fuente`, movimiento). Un solo color de acento, una sans-serif.
- **Escena `imagen`**: metáforas dibujadas, no fotos (decidido por Juani, Q8). El `svg` de cada
  dibujo es una ruta a un archivo en `assets/escenas/dibujos/` (o al de la serie): SVG local
  escrito a mano para esta skill, o de un set de licencia MIT/ISC recoloreado, nunca una foto
  ni una referencia de red. Falta o `href` externo (`http://`/`https://` en `href`/`xlink:href`)
  → error antes de abrir Chrome, sin `.mp4` ni `.parcial.mp4`.
  - **Recoloreado**: el SVG se escribe con el trazo en `stroke="currentColor"` y, si tiene
    relleno secundario, `class="lleno" fill="currentColor"`. Nunca un color fijo (`#fff`, `red`)
    adentro del SVG: la escena fija la propiedad CSS `color` del contenedor al acento del brand
    si el dibujo es el foco (el que entró más recientemente, igual que nodos y flechas de
    `diagrama.html`) o a `--tenue` en caso contrario. Así cambiar `colores.acento` sólo mueve
    los píxeles del dibujo en foco.
  - **Que se dibuje, no que aparezca**: el trazo avanza con `stroke-dasharray`/`stroke-dashoffset`
    en función de `t` (ease-out, sin overshoot: los píxeles no-fondo del recuadro nunca bajan de
    un cuadro al siguiente, R-4.2) y el relleno `.lleno` entra después, en el último 15 % de
    `movimiento.entrada` del brand (cuando el trazo ya está prácticamente completo, no a mitad
    de camino). Si tiene o hereda `stroke` (el caso de los sets tipo Lucide/Tabler/Font Awesome,
    que lo ponen en el `<svg>` raíz, no en cada `<path>`) se dibuja por trazo igual: la detección
    mira el estilo COMPUTADO, no el atributo propio del elemento. Un SVG externo fuera de esta
    convención (forma sólo con relleno, `<text>`) se revela con la MISMA curva ease-out (escala
    0→1, sin overshoot) en vez de aparecer de golpe — no con resorte: el resorte tiene un ~4 % de
    overshoot que hace bajar los píxeles al asentarse, y R-4.2 exige que nunca bajen. Sin
    `viewBox` se calcula desde el bbox del contenido, o falla claro si no hay nada medible; un
    color fijo (`#fff`, `rgb()`, nombres) en `fill`/`stroke` falla claro en vez de quedar pegado
    para siempre.
  - Sin posición (`x`/`y`) van en una sola fila, cuadrados, espaciados (como máximo 8 a 160 px de
    lado); con muchos dibujos, textos de rótulo largos, `x`/`y` puesto en sólo algunos dibujos, o
    dos posiciones que se pisan, igual que las otras plantillas, falla claro en vez de pisar.
- **Cero WebGL**: el motor bloquea `getContext('webgl'|'webgl2'|'experimental-webgl')` en
  cualquier plantilla (la GPU integrada de Juani la arrastra, PLAN.md); si una lo llama, sale
  como `ContratoError`, igual que cualquier otro error de JavaScript de la página.
- **Plantilla propia**: un HTML con `window.DURATION` y `async window.seek(t)` donde todo es
  función pura de `t` (sin `Date.now`, timers, `requestAnimationFrame` ni transiciones CSS).
  `escena.py render` falla claro si falta el contrato o si el JS tira un error.
- **Forzar relayout del `body` después de cada `seek` hace determinista el render**
  (medido: sin él 14/27 y 11/27 cuadros dependen del orden; con él 0). La causa exacta
  en Chrome no está identificada: en la portada la diferencia cae en el borde de un
  elemento redondeado, en `datos` en una fila horizontal de ~242 px.
- Chrome a escala fraccionaria tampoco es determinista: el motor captura siempre a
  1920x1080 y achica con ffmpeg.
- **`av<19`**: la faster-whisper actual rompe con `av` 19 (`metadata_errors`). Va pineado en
  los comandos de abajo.

## Transiciones

`"transicion"` en el guion (S6 del Hito 2, `docs/explicador/HITO2.md`): **arriba** del guion es
el default para todos los cambios de tramo; **en un segmento** es la transición **de entrada**
de ESE segmento (la que pasa entre él y el anterior). Un string es taquigrafía de su objeto
(`"transicion": "barrido"` ≡ `{"tipo": "barrido"}`). Sin la clave en ningún lado: `corte` (seco,
el comportamiento de siempre). Tipos: `corte` | `fundido` | `barrido`; cualquier otro valor
aborta antes de generar nada, listando los tres válidos.

- **Decisión de Juani (Q4)**: hay transición sólo si **al menos uno de los dos lados es una
  escena** (`"escena"` en el segmento); pantalla→pantalla queda siempre en corte seco, sin
  importar lo que diga el guion (un recorte de pantalla grabada no tiene "forma" que fundir o
  barrer; una escena sí). El primer segmento no tiene tramo anterior: si declara su propia
  `"transicion"` se avisa y se ignora.
- **Pasa DENTRO del slot, nunca lo mueve** (hallazgo 2 de HITO2.md: una superposición tipo
  `xfade` desincroniza la voz, porque el video se arma con `concat -c copy` y la voz suma
  slots). La mitad de la duración se pinta en los ÚLTIMOS segundos del `seg/NN.mp4` saliente y
  la otra mitad en los PRIMEROS del entrante, cada uno reencodeado en su propio archivo: G1
  (cuadros = Σ round(slot×30)) y G2 (el `.srt` y el arranque de la voz) quedan intactos.
- **Duración**: la que pida el guion (`"duracion"` en el objeto de transición, en segundos) o,
  si no, `brand.json` → `movimiento.entrada` (la misma noción de "cuánto tarda en entrar algo"
  que usan las escenas). Si el slot más corto de los dos lados no entra 3 veces en esa duración,
  se acorta a slot/3 con un aviso (nunca en silencio).
- **`barrido`**: una franja del color de **acento** del brand que CRUZA la pantalla en una sola
  pasada: en la mitad saliente el borde de ataque entra por la izquierda y cubre, hasta llegar
  al 100 % justo en el corte; en la mitad entrante el borde de SALIDA sigue de largo hacia la
  derecha y descubre (la franja sale por la derecha), en vez de retraerse hacia la izquierda
  como una cortina que entra y vuelve. Una sola curva ease-in-out continua
  (`ancho × (1 - cos(π·p))`, p de 0 a 1 en toda la transición, no dos mitades independientes)
  para que no haya salto de velocidad en el corte.
  - **Gotcha medido (ffmpeg 6.1.1)**: `drawbox` NO reevalúa `w`/`x` por cuadro aunque la
    expresión use `t` (queda congelada en el primer valor, calculado con `t` indefinido); y
    `w=0` significa "ancho completo" para `drawbox`, no "nada". Por eso el barrido se maneja
    cuadro a cuadro con un script de `sendcmd` (un comando `x` y un `w` por cuadro, calculados
    en Python) en vez de una expresión continua, y "sin barrido" se representa como 1px (no 0);
    y la caja lleva `enable='between(t,a,b)'` acotado a la ventana de la transición, para que
    fuera de ella no quede ni un píxel del acento montado en el resto del archivo.
- **`fundido`**: fundido A UN COLOR del brand (el **fondo**, no el acento: una pantalla "en
  blanco" entre dos tramos, no un flash de acento en cada corte), con el filtro nativo `fade` de
  ffmpeg — no es un cross-dissolve: cada tramo vive en su propio `seg/NN.mp4` (`concat -c copy`)
  y no tiene acceso a los píxeles del otro lado del corte.
- **R-6.5**: si la primera cue de la escena ENTRANTE cae dentro de la ventana de la transición,
  avisa (no aborta: la escena sigue siendo válida, nace con su primer elemento tapado un
  instante).
- **G4**: el reencode de la transición pasa por `encoder.vf()`/`encoder.cv_args()`, igual que
  `build_segment`, así que respeta `TUT_ENCODER` y todos los tramos siguen compartiendo códec,
  tamaño, pix_fmt y fps.

## Director

Guía para escribir el guion como lo armaría quien edita videos de profesión, y los chequeos
que `editar.py revisar vNN [voz] [--estricto]` corre para medir que se cumplió. `revisar` sólo
lee: nunca genera ni modifica el guion ni los videos, y si falta el artefacto que un chequeo
necesita lo dice en vez de omitirlo en silencio.

- **Estructura de clase de profe** (`rol` en cada segmento, opcional): `gancho` abre,
  `repaso` cierra, y en el medio hay al menos una `analogia` y un `ejemplo`. Sin ningún `rol`
  declarado, `revisar` no exige nada: avisa que el guion no los declara y sigue.
- **Un plano no dura más de N = 6 s sin que pase algo nuevo en pantalla.** Si la voz sigue
  hablando pero la imagen no cambia (una terminal quieta, una escena sin una entrada nueva),
  cortá el tramo, agregá un `zoom`, o movelo a otra escena.
- **Qué escena usar cuándo** (tabla completa en Escenas, más arriba): `presentacion` para abrir
  o cerrar una idea con un título; `diagrama` para relaciones y flujo (nodos, flechas); `datos`
  para comparar números; `imagen` para una metáfora dibujada; pantalla grabada para mostrar una
  herramienta de verdad. Una escena sin nada que entre después del título es tiempo muerto,
  igual que una terminal quieta.
- **La primera palabra del texto nombra el primer elemento** (S8, primer video real). El
  título ya está en pantalla: una muletilla de arranque ("Pensalo como...", "Volvamos a...",
  "Para llevarte.") deja 2–4 s de título solo, que se ve vacío aunque D2 no lo marque. Abrí
  el gancho con una portada (`presentacion` sin puntos, título grande) de ~5 s, y no
  remates una escena con una frase que no trae elemento nuevo si ya va por los 5 s.
- **Que Whisper oiga la cue**: elegí cues de 2–3 palabras de contenido ("unos siete años"),
  no la preposición del arranque ("Al diez" se oyó "El 10") ni "por ciento" (no se pasa a
  `%`). Un `datos` con 2 barras se ve vacío: sumá la referencia ("Lo que pusiste").
- **Cada elemento entra en la palabra que lo nombra** (`cue`), nunca "cerca". El texto del
  segmento tiene que nombrar lo que el elemento muestra en el momento en que entra (ver
  resolución de cues en Escenas, más arriba).
- **Qué transición usar cuándo** (formato completo en Transiciones, más arriba; recordá Q4:
  sólo si al menos uno de los dos lados es una escena — pantalla→escena, escena→pantalla o
  escena→escena, nunca pantalla→pantalla): `corte` (el default, sin declarar nada) para la
  mayoría de los cambios — una transición en cada corte cansa, no edita;
  `barrido` para marcar un cambio de TEMA (de la pantalla grabada a la metáfora que lo explica,
  o viceversa), porque el acento que atraviesa la pantalla dice "ahora cambiamos de plano de
  verdad"; `fundido` para un respiro más calmo, por ejemplo entre el cierre de una idea
  (`presentacion` con `rol: repaso`) y el inicio de la siguiente (`gancho`), donde un corte seco
  o un barrido se sentirían apurados.

**Reglas que mide `revisar`** (cada una es una clave de `editar.CHEQUEOS`, que `revisar()`
recorre de verdad — R-5.8; no alcanza con nombrarla en un comentario):

- **D1**: ningún tramo de `video-<voz>.mp4` queda MÁS de N = 6 s sin cambio visual
  (`freezedetect`, con su umbral de sensibilidad estricto en -60dB: un cambio sutil pero real
  no es "congelado"). Un video que queda congelado hasta el final (`freeze_start` sin
  `freeze_end`) cierra en la duración del video, no se descarta.
- **D2**: en una escena, ninguna entrada de elemento queda a MÁS de N = 6 s de la anterior,
  contando también desde el segundo 0 hasta la primera entrada (una escena sin ninguna cue,
  sólo el título, es tiempo muerto entero) y desde la última entrada hasta el final; calculado
  desde el spec ya resuelto (`videos/<vNN>/escenas/*.json`), sin renderizar. Mismo criterio de
  borde que D1 (estrictamente MÁS de N, nunca "N o más"). Sólo mide los specs que corresponden
  a una escena del guion de HOY y cuya duración coincide con `slots-<voz>.json` de la voz
  pedida: un spec viejo o de otra voz se ignora (se avisa, no se mide), y un spec con una cue
  sin `t` o sin `duracion` es "no corrió" nombrando el archivo, nunca un traceback.
- **D3**: ningún silencio de la voz (`voz-<voz>.wav`, no el final, que con música no tiene
  silencio) dura más de 0.9 s, con un umbral de sensibilidad estricto en -40dB (una voz floja
  pero real no es silencio) y sin mirar el returncode de ffmpeg para confundir "corrió y no
  encontró nada" con "no pudo correr" (un wav vacío o corrupto es "no corrió", con la causa).
  El pipeline deja LEAD (0.3s) + cola (`TAIL`, 0.5s, igual para TODAS las voces desde la
  decisión de Juani del 03/10/2026 — antes 1.0s para `FISH_LENTAS` y 0.6s para las rápidas) =
  0.8s de silencio de diseño en cada borde entre segmentos; como 0.8s < 0.9s, D3 no lo confunde
  con un silencio real.
- **D4**: si el guion declara `rol` en algún segmento, el primero es `gancho`, el último
  `repaso`, y hay al menos una `analogia` y un `ejemplo`; sin ningún `rol`, una sola línea
  avisa que el guion no los declara. Un rol que no es ninguno de los cuatro válidos
  (`gancho`, `analogia`, `ejemplo`, `repaso`) avisa "rol desconocido" con la lista de válidos
  y no cuenta como ninguno de ellos; uno que sólo difiere en mayúsculas o tildes (`Analogía`)
  se normaliza con un aviso aparte (ese aviso no cuenta como hallazgo para `--estricto`); uno
  que no es texto (p.ej. `1`, guion mal armado) se informa como "rol inválido", nunca un
  traceback.

`revisar` informa los hallazgos pero sale con 0 igual; sólo con `--estricto` sale con 1 si
encontró algún hallazgo real, O SI ALGÚN CHEQUEO NO CORRIÓ (decisión de Juani, 03/10/2026).
Esa política vive en una sola función, `_estricto_falla`.

Un nombre de voz sin NINGÚN artefacto (ni `video-<voz>.mp4`, ni `voz-<voz>.wav`, ni
`slots-<voz>.json`, ni la carpeta `<voz>/` de wavs importados) habiendo artefactos de OTRA voz
es casi siempre un nombre tipeado mal: `revisar` sale con error, listando las voces que sí
tienen artefactos. Si no hay artefactos de ninguna voz (un `vNN` recién creado), sigue de largo
como siempre. Un `vNN` inexistente, un guion con JSON inválido o sin `"segmentos"`, sin
argumentos, demasiados argumentos, o un flag que no es `--estricto` (incluido uno corto como
`-e`) dan un mensaje claro con el uso, nunca traceback.

Un spec de escena (`videos/<vNN>/escenas/NN.json`) queda atado, al escribirlo `escenas()`, a la
voz y al CONTENIDO del segmento del guion (un hash). Si el guion cambió, si el spec es de otra
voz, si el archivo no existe, o si es JSON inválido, D2 no lo mide y lo dice (nombrando el
archivo), para cada índice de escena de hoy — nunca se saltea una escena sin spec en silencio.

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

**Reproducir un video de YouTube en cámara mete anuncios**

Un corte de Amazon Prime, con subtítulos en alemán, en medio de un video institucional.
Y las recomendaciones de la barra lateral traen lo que traigan — en una toma apareció
contenido político. Saltar el anuncio, cerrar el popup de Premium, y encuadrar con
`zoom` para dejar fuera la franja de recomendaciones. Después revisar los frames: el
anuncio puede entrar a mitad de la toma, no sólo al principio.

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

**Límites duros**
- Nunca voces de famosos ni clones de personas reales sin consentimiento, aunque sea "en joda".
- API keys en `~/.config/<proveedor>/api_key` con `chmod 600`; nunca en guiones ni scripts. Si el usuario las pega en el chat, recomendar rotarlas.
- Publicar (YouTube/Drive público) requiere OK explícito del usuario; avisar si el contenido es una solución de TP antes del cierre.

## Commands

```bash
# variables comunes
export TUT_ROOT=~/Proyectos/tutorial-X   # raíz: raw/, guion/, videos/
export TUT_ENCODER=auto                   # auto|vaapi|software (default software, igual que antes de VAAPI)
export TUT_VAAPI_DEVICE=/dev/dri/renderD128  # sólo si el dispositivo no es el default
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
$S/editar.py imagen v01 argentina && $S/editar.py voz v01 argentina   # argentina = voz principal (default)
uv run --with faster-whisper --with "av<19" python $S/verificar_voz.py argentina v01
ffmpeg -i videos/v01/final-argentina.mp4 -af silencedetect=noise=-40dB:d=0.9 -f null - 2>&1 | grep -c silence_end

# escenas (Chrome instalado, no baja navegadores)
E="uv run --with playwright --with faster-whisper --with av<19 python"
$E $S/editar.py escenas v01 argentina          # voces + specs resueltos, sin renderizar
uv run --with playwright python $S/escena.py contacto videos/v01/escenas/*.json -o videos/v01/contacto.png
$E $S/editar.py imagen v01 argentina && $S/editar.py voz v01 argentina
uv run --with playwright python $S/escena.py render datos spec.json -o prueba.mp4 --ancho 960 --fps 12   # prueba suelta

# comprimir para subir
ffmpeg -y -i videos/v01/final-argentina.mp4 -c:v libx264 -preset slow -crf 30 -tune stillimage -c:a aac -b:a 128k "drive/1 - Titulo.mp4"
```

## Resources

- **Scripts**: [assets/scripts/](assets/scripts/) — grabación, control de opencode, edición y verificación.
- **Entorno bajo Wayland**: [assets/scripts/entorno.sh](assets/scripts/entorno.sh) — `start|chrome|status|stop`.
- **Guiones de ejemplo**: [assets/guion-ejemplo/](assets/guion-ejemplo/) — video de navegador (v01), ciclo OPSX (v07) y explicador con escenas (interés compuesto).
- **Escenas**: [assets/escenas/](assets/escenas/) — plantillas, `base.js` (contrato y resortes) y `brand.json`. Motor: `escena.py`, tiempos por palabra: `palabras.py`.
- **Voces y proveedores**: [references/voces.md](references/voces.md) — IDs, costos, licencias y cómo agregar una voz a `editar.py`.
- **Caso real completo**: `~/Proyectos/tutorial-active-stack/` (TP2 Java con Active Stack + opencode + Muse Spark).

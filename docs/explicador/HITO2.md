# Hito 2: requisitos y rebanadas

Escrito por el analista funcional el 03/10/2026 a partir de `PLAN.md` y del código del Hito 1.
Cada "falla hoy" sale de leer el código, no de correrlo: antes de implementar, correr el
comando del requisito y ver que efectivamente falla. Si pasa, el requisito está mal escrito.

## Hallazgos que cambian el plan

1. **El zoom automático parte de algo falso.** `PLAN.md` dice que la skill "ya sabe dónde tipea
   y clickea". No lo sabe: `rec.py` solo escribe `.log`, `.t0`, `.pid` y `.marks` (hora + texto
   libre), se graba con `-draw_mouse 0` y `click-cdp.py` clickea por texto sin coordenadas.
   El zoom se parte en S7a (de dónde salen los datos) y S7b (el zoom).
2. **Un fundido hecho como superposición desincroniza la voz.** El video se arma con
   `concat -c copy` y la voz se arma sumando slots (`editar.py:397`, `428-435`). Si dos tramos
   se superponen, el video queda más corto y la voz se corre en cada cambio. Las transiciones
   tienen que pasar *dentro* del slot, sin moverlo.
3. **VAAPI por defecto contradice "el guion del Hito 1 sale idéntico"**: otro encoder da otros
   cuadros. Default: software, VAAPI con `TUT_ENCODER=auto`.

## Invariantes globales (ninguna rebanada las rompe)

| ID | Invariante | Cómo se mide |
|---|---|---|
| G1 | Cuadros de `final-<voz>.mp4` = Σ round(slot_i × 30) | `ffprobe -count_packets`, como `test_editar_e2e.py:57` |
| G2 | El `.srt` sale idéntico con o sin campos nuevos; la voz del segmento i arranca en Σslots[:i] + LEAD (0.3 s) ±1 cuadro | `cmp` |
| G3 | Un guion sin campos nuevos produce los mismos cuadros y audio que antes del Hito 2 | `framemd5` de video y `md5` de audio contra la base de S0 |
| G4 | Todos los tramos comparten códec, tamaño, pix_fmt y fps | `ffprobe` de cada `seg/NN.mp4` |

## Rebanadas

| # | Rebanada | Depende de |
|---|---|---|
| S0 | Red de seguridad: base congelada del Hito 1 | — |
| S1 | Encoder centralizado: VAAPI con respaldo a software | S0 |
| S2 | Música de fondo y loudness | S0 |
| S3 | Efectos de sonido sobre palabras | S2 |
| S4 | Escena `imagen` | S0 |
| S5 | El director: `editar.py revisar` + sección en `SKILL.md` | S0 |
| S6 | Transiciones | S1, S4 |
| S7a | Fuente de datos del zoom | Q5 |
| S7b | Zoom automático | S7a, S1 |
| S8 | Ejemplo de punta a punta + documentación | todas |

S5 va antes que S6 y S7 porque mide tiempo muerto y cambio visual: así transiciones y zoom
tienen un antes y un después medibles.

## Requisitos

### S0: Red de seguridad
- **R-0.1** Dos renders seguidos (`imagen` + `voz`) de `explicador-interes-compuesto.json` y de un
  guion mixto tipo v01, con voces sintéticas y palabras falsas como en `test_editar_e2e.py`, dan
  el mismo framemd5 y el mismo md5 de audio. Si no dan igual, G3 pasa a ser
  "PSNR ≥ 50 dB por cuadro + G1 + G2".
- **R-0.2** Los hashes quedan versionados en `tests/` y G3 se compara contra ellos
  (test de caracterización: pasa hoy por construcción).

### S1: Encoder
- **R-1.1** `TUT_ENCODER=auto` con VAAPI disponible: el stream dice `h264_vaapi` y se cumple G4
  (h264, 1920x1080, yuv420p, 30/1). Falla hoy: no hay `vaapi` en `assets/scripts`.
- **R-1.2** `auto` sin VAAPI (`TUT_VAAPI_DEVICE=/no/existe`): libx264, **una** línea en stderr
  `VAAPI no disponible (<motivo>): uso libx264`, salida 0.
- **R-1.3** `TUT_ENCODER=vaapi` sin VAAPI: salida ≠ 0 **antes del primer tramo**, el mensaje nombra
  el dispositivo.
- **R-1.4** La disponibilidad se decide codificando 1 cuadro de prueba, no por la existencia de
  `/dev/dri/renderD128`. Dispositivo sin permisos → respaldo de R-1.2.
- **R-1.5** Sin `TUT_ENCODER`: software, se cumple G3.
- La velocidad no es criterio de aprobación: se mide y se reporta como juicio.
- `libx264` hoy está escrito a mano en `editar.py:257,281,292` y `escena.py:59`.
- VAAPI falla a mitad del render: corta, sugiere `TUT_ENCODER=software`, no mezcla encoders (G4).
- Windows con `auto`: software + aviso.

### S2: Música y loudness
- **R-2.1** Con `"musica": {"archivo": ...}`, los primeros 0.3 s del final tienen RMS > -60 dBFS.
  Falla hoy: silencio digital (`editar.py:430`), `astats` da `-inf`.
- **R-2.2** Se escribe `videos/vNN/musica-<voz>.wav` ya atenuada; en tramos con voz queda ≥ 15 LU
  por debajo de la voz (`ebur128` por tramo).
- **R-2.3** Con música, el final mide I = -16 ±1 LUFS y TP ≤ -1.5 dBTP.
- **R-2.4** Música más corta: bucle. Más larga: corte con fundido de 2 s. El audio dura lo mismo
  que el video ±0.05 s.
- **R-2.5** `"musica": false` en un segmento: la música queda < -60 dBFS en ese slot.
- **R-2.6** Archivo faltante o ilegible: salida ≠ 0 al arrancar, ruta absoluta en el mensaje,
  no escribe ni pisa ningún `final-*.mp4`.
- **R-2.7** Se cumple G2.

### S3: Efectos de sonido
- **R-3.1** `"sfx": [{"archivo", "cue", "ganancia_db"?}]`: el efecto arranca en
  Σslots[:i] + LEAD + t(palabra) ±1 cuadro (se verifica con `silencedetect`).
- **R-3.2** Funciona igual en tramos de pantalla. Falla hoy: las palabras solo se transcriben
  para escenas (`editar.py:360`).
- **R-3.3** Cue que no se dice: salida ≠ 0 con segmento, "sfx", cue y lo que se oyó
  (reusar `palabras.py:244-245`).
- **R-3.4** Cue numérica cuenta desde el inicio del slot; fuera del slot, error con el segmento.
- **R-3.5** Con efectos se sigue cumpliendo R-2.3.
- Archivo de sfx faltante: igual que la música.

### S4: Escena `imagen`
- **R-4.1** `escena.py render imagen spec.json -o x.mp4` da un mp4 con la duración del spec.
  Falla hoy: `ValueError: no hay plantilla de escena 'imagen'` (`escena.py:115-118`).
- **R-4.2** Píxeles no-fondo en el recuadro del dibujo: antes de su `t` = fondo; en
  `t + movimiento.entrada` = máximo; en el medio estrictamente entre los dos y nunca bajan de un
  cuadro al siguiente.
- **R-4.3** Mismo `t`, mismo PNG, sin importar el orden (patrón de `test_plantillas.py`).
- **R-4.4** Cambiar `colores.acento` cambia los píxeles de acento y deja los demás iguales.
- **R-4.5** Cero llamadas a `getContext('webgl'|'webgl2'|'experimental-webgl')`; si una plantilla
  llama a WebGL, `ContratoError`.
- **R-4.6** SVG faltante o con `href` externo: error antes de abrir Chrome, sin `.mp4` ni
  `.parcial.mp4`.
- **R-4.7** En `t = DURATION` ninguna `[data-caja]` se superpone y el texto mide ≥ 24 px.
- **R-4.8** `escena.py contacto` acepta specs `imagen`.

### S5: El director
- **R-5.1** `editar.py revisar vNN [voz]` imprime un informe. Falla hoy: `sys.exit(__doc__)`
  (`editar.py:478-479`).
- **R-5.2** Tramos > N s (default 6) sin cambio visual en `video-<voz>.mp4`, con `freezedetect`.
- **R-5.3** Escenas con más de N s entre dos entradas de elementos (o entre la última y el final),
  calculado desde los specs resueltos, sin render.
- **R-5.4** Silencios > 0.9 s en `voz-<voz>.wav` (no en el final, que con música no tiene silencio).
- **R-5.5** Con `rol` en algún segmento: el primero es `gancho`, el último `repaso`, hay al menos
  una `analogia` y un `ejemplo`. Sin ningún `rol`: una línea "el guion no declara roles".
- **R-5.6** Dice qué chequeos no corrieron y por qué; nunca los omite en silencio.
- **R-5.7** Sale con 0 aunque haya hallazgos; con `--estricto` sale con 1.
- **R-5.8** Sección "Director" en `SKILL.md` con reglas numeradas; un test estilo
  `test_docs_comandos.py` comprueba que cada regla tiene su chequeo en `revisar`.

### S6: Transiciones
- **R-6.1** `"transicion": {"tipo": "barrido"}` entre dos tramos grises: cerca del cambio hay un
  área del acento del brand ≥ 20 % de la pantalla. Con corte seco da 0 %.
- **R-6.2** Se cumplen G1 y G2: la transición no mueve nada de lugar.
- **R-6.3** El color sale del brand.
- **R-6.4** Dura `duracion` ±1 cuadro (cuadros con acento > 1 %); default desde `brand.movimiento`.
- **R-6.5** Si la primera cue de la escena entrante cae dentro de la transición: aviso.
- **R-6.6** Slot < 3 × duración: se acorta a slot/3 con aviso.
- **R-6.7** Tipo desconocido: salida ≠ 0 con la lista `corte`, `fundido`, `barrido`.
- En el primer segmento se ignora con aviso.

### S7a: Fuente de datos del zoom
- Opción por defecto (detección de cambios): `editar.py zonas vNN` sobre un crudo sintético
  (cuadrado blanco en (1400, 800) en t = 1.0 s) escribe `videos/vNN/zonas/NN.json` con
  `{t≈1.0, x≈1400, y≈800}`.
- Alternativa (eventos al grabar): `rec.py` deja `raw/<nombre>.eventos.jsonl` con `{t, tipo, x, y}`
  desde el mismo t0 que `.marks`.

### S7b: Zoom automático
- **R-7.1** `"zoom": "auto"`: 0.5 s después del momento clave el cuadrado ocupa ≥ 1.5× más píxeles
  y su centro cae en el 50 % central. Falla hoy: `TypeError` en `z['w']` (`editar.py:276`).
- **R-7.2** La escala no cambia > 5 % entre cuadros, rampa ≥ 0.4 s, escala máx. 2.0, como mucho
  un acercamiento cada 3 s.
- **R-7.3** El zoom fijo `{x, y, w, h}` no cambia (G3).
- **R-7.4** Sin momentos clave: aviso con el segmento, salida 0, resultado igual que sin zoom.
- **R-7.5** Cerca del borde, el recorte se ajusta adentro, sin franjas.
- **R-7.6** Con `decimar: true` se calcula en el tiempo del crudo, antes de `mpdecimate`.
- **R-7.7** `"zoom": "auto"` en una escena o título: error con el segmento.

## Formato del guion

Todas las claves son opcionales; sin ellas, el comportamiento es el del Hito 1.

| Clave | Dónde | Si no está |
|---|---|---|
| `musica` | Arriba: objeto `{archivo, debajo_de_la_voz_lu?, fundido?}`; en segmento: `false` la apaga | Sin música |
| `transicion` | Arriba: default para todos los cambios; en segmento: transición **de entrada** | `corte` |
| `sfx[]` | Segmento: `archivo`, `cue` (texto o segundos), `ganancia_db?` | Sin efectos |
| `zoom` | `{x, y, w, h}` fijo o `"auto"` | Sin zoom |
| `escena.tipo = "imagen"` | `dibujos[]` (`id`, `svg`, `cue`, posición?) y `rotulos[]` (`texto`, `cue`, `de`) | — |
| `rol` | Segmento: `gancho`, `analogia`, `ejemplo`, `repaso` | `revisar` avisa |

El encoder va en `TUT_ENCODER` (`auto`, `vaapi`, `software`), no en el guion: es de la máquina,
no del video. Rutas relativas a `TUT_ROOT`. Una clave desconocida (por ejemplo `transicon`) da un
aviso con su nombre.

## Decididas por Juani el 03/10/2026

- **Q5**: el zoom sale de detectar cambios en los cuadros del crudo.
- **Q1**: la música la pone Juani en `musica/` y verifica la licencia; los sfx se generan con ffmpeg.
- **Q7**: VAAPI es opt-in (`TUT_ENCODER=auto`); el default sigue siendo software.
- **Q4**: transición solo si uno de los dos lados es escena; pantalla→pantalla queda en corte seco.
- El resto de las preguntas va con su default.

## Preguntas abiertas (con el default que permite avanzar)

| # | Pregunta | Default |
|---|---|---|
| Q1 | Origen y licencia de música y sfx | Sfx generados con ffmpeg (lavfi). La música la pone Juani en `TUT_ROOT/musica/`; la skill no incluye música |
| Q2 | Loudness objetivo | -16 LUFS / -1.5 dBTP (el de hoy) |
| Q3 | Cuánto por debajo de la voz va la música | 18 LU con voz, 10 LU en silencios |
| Q4 | ¿Transiciones entre dos tramos de pantalla? | No: solo si uno de los dos lados es escena |
| Q5 | De dónde salen los momentos clave del zoom | Detección de cambios en los cuadros del crudo |
| Q6 | ¿Zoom auto activado por defecto? | No, se pide con `"zoom": "auto"` |
| Q7 | ¿VAAPI por defecto? | No, `TUT_ENCODER=auto` |
| Q8 | ¿Escena `imagen` solo vector, quién dibuja? | SVG local, del agente o de sets MIT/ISC, recoloreado al brand. Sin fotos. OpenMoji es CC BY-SA |
| Q9 | Cue de sfx que no se dice | Frena el render |
| Q10 | N del cambio visual; ¿`revisar` frena? | N = 6 s; solo frena con `--estricto` |
| Q11 | ¿Campo `rol`? | Sí, opcional |

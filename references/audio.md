## Audio: música, voiceover carve, loudness y sfx

- **Música de fondo** (`editar.py voz`, `musica.py`): `"musica": {"archivo", "debajo_de_la_voz_lu"?,
  "fundido"?}` arriba del guion (ver README → El guion); `"musica": false` en un segmento la apaga
  sólo ahí. `archivo` es relativo a `TUT_ROOT`; la música la pone quien arma el tutorial en
  `TUT_ROOT/musica/` (la skill no la trae, por licencia) y si falta o no se puede leer, aborta
  antes de generar nada. **"Voiceover carve" (H1, Hito 3, `docs/explicador/HITO3.md`)**: ANTES del
  ducking de banda ancha, un EQ peaking fijo (`musica.BANDAS_VOZ_HZ`: 250/400/630/1000/2500 Hz a
  -7dB, 1600 Hz a -15dB -idea robada de HyperFrames, `packages/core/src/audioCarve.ts`, Apache 2.0,
  bandas fijas en vez de su FFT por voz) baja la música SÓLO en esas bandas mientras hay voz, y
  vuelve a sonar entera en los silencios -mismo ataque/liberación que el ducking
  (`musica.aplicar_carve_voz`, `ATTACK_S`/`RELEASE_S`); los graves (< 150 Hz) no los toca. Con el
  carve haciendo buena parte del trabajo de "sacarse del medio", el ducking de banda ancha baja
  MENOS que antes del Hito 3: **10 LU** bajo la voz mientras hay voz (antes 18), 10 LU en los
  silencios (`debajo_de_la_voz_lu` sólo ajusta el primero) -ducking en rampa EN dB (no en escalón
  ni en amplitud lineal, QA 04/10/2026), ataque rápido, liberación lenta
  (`ATTACK_S`/`RELEASE_S`, sin bombeo). **Perfiles de loudness por destino (H1)**: `"destino"`
  arriba del guion, `"youtube"` (default, -16 LUFS / TP ≤ -1.5 dBTP, el mismo de antes del Hito 3)
  o `"redes"` (-14 LUFS / TP ≤ -1.0 dBTP); cualquier otro valor aborta nombrando los dos válidos
  (`musica.PERFILES_LOUDNESS`). El final sigue dando el perfil elegido igual que sin música:
  `musica.normalizar_dos_pasadas` mide con `loudnorm` de dos pasadas y aplica un limitador de TRUE
  PEAK aparte (una sola pasada no llega al integrado cuando el TP la restringe, QA 04/10/2026;
  margen del AAC: `musica.tp_interno`). Música más corta que el total: bucle con una UNIDAD sin
  costura (el crossfade aplicado una vez, no por vuelta -el costo no crece con la cantidad
  de vueltas); rechaza con `SystemExit` una música más corta que 2x el crossfade. Sin la clave `musica`
  el final pasa por las mismas dos pasadas (decisión del 04/10/2026: todo final al perfil elegido),
  así que el audio del Hito 1 cambió a propósito; el video no (G3 sigue siendo sólo framemd5 sin la
  clave `musica`, el carve y el nuevo default de ducking no tocan ese camino).
- **Efectos de sonido** (`editar.py voz`, `sfx.py`): `"sfx": [{"archivo", "cue", "ganancia_db"?}]`
  en un segmento (ver README → El guion). `archivo` es el nombre de un sonido generado (`pop`,
  `click`, `whoosh`, `ding`; decisión Q1 de Juani, `docs/explicador/HITO2.md`: sin licencia, se
  generan con ffmpeg lavfi, reproducibles) o una ruta propia relativa a `TUT_ROOT`, resuelta igual
  que `musica.resolver_archivo` (si falta, aborta antes de escribir nada, con su ruta absoluta).
  `cue` es una frase (se resuelve por `palabras.py`, igual que en una escena, incluso en un tramo
  de pantalla -R-3.2-) o un número de segundos **contado desde el inicio del slot**, no desde el
  arranque de la voz; fuera de `[0, slot)` aborta nombrando el segmento. Una cue de texto que no
  se dice aborta con el segmento, `sfx` y la cue, reusando el mensaje de `palabras.resolver_cue`
  ("no se dice en la voz. Se oyó: ..."). Los sonidos generados ya traen fundido en los dos bordes
  (sin click) y un nivel discreto por debajo de la voz; `ganancia_db` suma o resta dB sobre ese
  nivel. La mezcla entra ANTES de `musica.normalizar_dos_pasadas` (no después): así el limitador
  de TRUE PEAK final ve también los sfx y R-2.3 (-16 LUFS / TP ≤ -1.5 dBTP) sigue cumpliéndose con
  efectos (R-3.5). Sin la clave `sfx` en ningún segmento, no se genera ni se toca ningún archivo
  de sfx (G1-G4 no se mueven).
  - **Guía del Director**: un sfx marca el dato clave o el remate de una idea, no cada frase.
    Dos o tres por video alcanzan; uno en cada oración cansa y deja de significar nada.

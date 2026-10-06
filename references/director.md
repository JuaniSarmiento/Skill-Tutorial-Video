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
- **Dirección visual** (H2; la miden D5 y D6 y la puerta de `escena.py render`): títulos de 64
  a 120 px, cuerpo de 28 a 42, etiquetas de 18 a 24 en mono (kicker, notas, rótulos de
  flecha). El contenido vive en el 83 % de arriba: el 17 % de abajo es de los subtítulos.
  Fondo plano: nada de degradés grandes sobre fondo oscuro (hacen bandas en H.264). El dato
  clave de una escena va como **número protagonista** (`presentacion` con `numero` y, si hay
  contra qué compararlo, `contra`: "10 años" en acento contra "30" en tenue), no en un punto
  más de una lista.

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
- **D5**: ningún texto de una escena tiene contraste menor a 4,5:1 contra su fondo (WCAG AA;
  3:1 si mide 32 px, o 24 px en negrita), medido con la puerta de `verificar.py` sobre el spec
  resuelto (`videos/<vNN>/escenas/*.json`) con el brand del tutorial, en 12 tiempos más los de
  cada cue. Sólo cuenta un texto ya entrado (opacidad plena, no a mitad de fundido).
- **D6**: ningún texto visible de una escena pisa a otro, se sale del cuadro útil (invade la
  banda de subtítulos, el 17 % de abajo) ni de su caja; misma puerta y mismos tiempos que D5.
  Si la puerta no puede correr (Chrome, un spec roto), D5 y D6 son "no corrió" con la causa.
- **D7** (H5 ronda 2, HITO3.md): ningún texto visible de una escena mide menos de 24 px
  (umbral configurable en `verificar.hallazgos_del_cuadro`, `umbral_texto_chico`); un kicker o
  una etiqueta en mono de exactamente 24 px pasa. Misma puerta y mismos tiempos que D5/D6: si no
  puede correr, D7 es "no corrió" con la causa, igual que D5 y D6.

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

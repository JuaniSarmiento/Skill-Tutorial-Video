## Director de Shorts verticales

`revisar_short.py` es el Director (D1-D8 de `references/director.md`) aplicado a episodios de un
canal que **no renderiza con esta skill**: el canal de Shorts verticales "Fuera de Rango"
(TikTok/YouTube), cuyo pipeline propio es `voz.py` → `tiempos.json` → Remotion → `.mp4`
1080×1920. Este script **no arma videos, sólo los revisa** ya grabados y publicados, igual de
espíritu que `editar.py revisar` para los de 16:9: sólo lee, nunca genera ni modifica nada, y si
un chequeo no puede correr (archivo faltante, ffprobe/ffmpeg falla) lo dice como "no corrió",
nunca como un pase silencioso.

### Cómo se corre

Sobre un episodio ya producido del canal, con sus tres artefactos:

```bash
uv run --with pytest python revisar_short.py guion/eNN-*.json video/public/eNN-*/tiempos.json \
  series/<serie>/publicados/eNN-*.mp4 [--estricto]
```

`--estricto` sale con 1 si encontró algún hallazgo real (sin el prefijo `aviso: `) o si algún
chequeo no corrió; sin el flag, informa igual pero sale con 0 (mismo criterio que
`editar.py revisar`, ver `references/director.md`).

### Qué mide

- **D1** (tiempo muerto): reusa `editar._freezes` tal cual (no se copia) sobre el `.mp4`: ningún
  tramo queda más de 6s sin cambio visual.
- **D2** (entradas): a diferencia del D2 16:9 (que mide desde los specs de escena resueltos,
  `videos/<vNN>/escenas/*.json`), acá no hay specs: se mide directo de `tiempos.json`, contando
  como entrada el **inicio de cada segmento** y el **tiempo de cada cue** (`cues`). Ningún tramo
  entre dos entradas (o desde 0 hasta la primera, o desde la última hasta el total) queda a más
  de 6s de la anterior.
- **D8** (ritmo): a diferencia del D8 16:9 (que agrupa por `escena.tipo`), acá agrupa por
  **`escena.forma`**, un campo nuevo y opcional que el guion del canal puede declarar (valores
  libres, p.ej. `"cancha"`, `"tarjeta"`, `"numero"`, `"bit"`, `"titulo"`, `"cierre"`). La razón:
  en el canal cada escena tiene un `tipo` único por momento del partido (`z34_boca_433`,
  `z34_boca_paredes`, `z34_boca_cita`...), así que medir por `tipo` nunca vería una racha aunque
  todas esas escenas sean, visualmente, la misma forma ("cancha con fichas"). Si **ningún**
  segmento del guion declara `forma`, D8 no tiene con qué medir: se informa como
  "D8 no corrió: el guion no declara escena.forma" (no un pase silencioso) y no cuenta ninguna
  racha. Igual que D8 16:9: ninguna racha de MÁS de 2 segmentos consecutivos con la misma forma.
- **Vertical**: el `.mp4` tiene que medir 1080×1920 (si no, hallazgo); si dura más de 180s, aviso
  de que ya no entra en YouTube Shorts (Pizarra, con su excepción a 2-3 min, puede pisar esto a
  propósito — es aviso, no bloqueo); loudness integrado y true peak medidos con `ebur128`
  (reusa `musica.medir_i_tp`), aviso si el true peak supera -1 dBFS.

### El campo `escena.forma`

Es del guion del canal, no de la skill: no lo escribe ni lo exige ningún otro script (`voz.py`,
Remotion). Es puramente informativo para que D8 pueda agrupar escenas que comparten forma visual
aunque tengan `tipo` distinto. Si un guion no lo declara, D8 avisa que no corrió en vez de pasar
en falso (confundiendo "sin racha" con "no hay con qué medir"); declararlo en los guiones nuevos
es la única forma de que D8 mida algo de verdad.

### Qué NO hace

No renderiza, no re-arma, no sube nada. No toca ningún default de la skill 16:9 (`editar.py`,
`escena.py`, etc.): es un módulo nuevo que **reusa** lo que ya mide lo mismo (`editar._freezes`,
`musica.medir_i_tp`) y escribe de cero lo que no tiene equivalente ahí.

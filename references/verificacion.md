## Verificación

### Puerta antes del render (`verificar.py`, H2)

`escena.py render` lleva la escena a 12 tiempos parejos más justo antes y después de cada cue y
NO renderiza si dos textos visibles se pisan, si un texto se sale del cuadro útil (invade la
banda de subtítulos) o de su caja, si el contraste es menor a 4,5:1 (3:1 en texto de 32 px, o de
24 en negrita), si un texto visible mide menos de 24 px (umbral configurable,
`umbral_texto_chico` en `verificar.hallazgos_del_cuadro`; un kicker o etiqueta en mono de
exactamente 24 px pasa — hallazgo "texto chico", H5 ronda 2), o si un elemento se ve antes de su
cue (las plantillas marcan cada elemento con `data-t`). Nombra escena, tiempo y elemento.
`--sin-verificar` la saltea a propósito; suelta: `verificar.py spec.json...` (sale con 1 si hay
hallazgos). El fondo de un texto es el de sus ancestros: un texto encima de una forma que no lo
contiene se mide contra la página.

Estos mismos chequeos (contraste, superposición y texto chico) son los que mide D5/D6/D7 de
`editar.py revisar` sobre el guion completo: ver `references/director.md`.

### Revisar el guion (`editar.py revisar`)

`editar.py revisar vNN [voz] [--estricto]` corre el conjunto de chequeos del Director (tiempo
muerto, silencios, roles, contraste, superposición): ver `references/director.md` para las
reglas D1-D6 completas y cómo se registran en `editar.CHEQUEOS`.

- Chequear el guion por repeticiones propias ("modelo, modelo actividades…") antes de culpar a
  la voz: lo que suena como una alucinación del TTS a veces ya está repetido en el texto que se
  le pasó.

### Verificar la voz (`verificar_voz.py`)

Transcribe cada tramo con faster-whisper y marca las alucinaciones del TTS (repeticiones,
frases de más). Se corre después de `editar.py voz`, antes de dar por buena una tanda:

```bash
uv run --with faster-whisper --with "av<19" python $S/verificar_voz.py argentina v01
```

### Privacidad: lo que se filma no se puede despublicar

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

`censurar.py` implementa esta caja-por-tramo con OCR. Los patrones a tapar no van en el código,
van en `~/.config/tutorial-video/secretos.txt` (ver README.md → Privacidad).

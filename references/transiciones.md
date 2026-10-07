## Transiciones

`"transicion"` en el guion (S6 del Hito 2, `docs/explicador/HITO2.md`): **arriba** del guion es
el default para todos los cambios de tramo; **en un segmento** es la transición **de entrada**
de ESE segmento (la que pasa entre él y el anterior). Un string es taquigrafía de su objeto
(`"transicion": "barrido"` ≡ `{"tipo": "barrido"}`). Sin la clave en ningún lado: `corte` (seco,
el comportamiento de siempre). Tipos: `corte` | `fundido` | `barrido` | `whip`; cualquier otro
valor aborta antes de generar nada, listando los cuatro válidos.

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
- **`whip`** (H7, HITO3.md): latigazo de cámara con **velocidades pareadas** — el tramo saliente
  sale desplazándose (hacia la izquierda) acelerando, con desenfoque de movimiento CRECIENTE; el
  entrante llega desde el lado opuesto (la derecha) frenando, con el desenfoque DECRECIENTE, así
  que la velocidad en el corte es la misma de los dos lados. Usa el color de **fondo** del brand
  (como `fundido`: no hay acento de por medio, es el "vacío" que se revela cuando el cuadro se
  corrió), nunca el acento.
  - **Misma curva que `barrido`** (`sweep(p) = ancho·(1 − cos(π·p))`, p de 0 a 1 en TODA la
    transición, 0.5 = el corte): no son dos efectos independientes por mitad, es la MISMA función
    continua vista desde cada lado, así que la derivada (la velocidad) es continua en el corte por
    construcción — no hay salto que ajustar a mano. `anchos_whip` la reusa para el desplazamiento
    del recorte (`x`, 0→ancho en cada mitad) y para el desenfoque (`sigma = sigma_max·sin(π·p)`:
    0 en los dos extremos -reposo, nítido-, máxima exactamente en el corte, la MISMA en saliente y
    entrante).
  - **Mecánica**: la imagen se estira sobre un lienzo `2×ancho` (`pad`, con el color de fondo del
    lado libre) y `crop` recorta una ventana de `ancho` que se desplaza (`x`) según la curva de
    arriba; `gblur` sigue la misma `sigma` por cuadro (desenfoque de movimiento). Mismo gotcha que
    `barrido` (`crop`/`gblur` no reevalúan sus parámetros por cuadro con una expresión de `t` en
    ffmpeg 6.1.1): se maneja cuadro a cuadro con `sendcmd` (un `x` de `crop` y un `sigma` de
    `gblur` por cuadro), igual arquitectura que el barrido (G1/G2/G4 intactos por construcción,
    archivo de `sendcmd` que se borra siempre).
  - **Q4 también aplica**: sólo hay `whip` si al menos uno de los dos lados es una escena;
    pantalla→pantalla queda en corte seco.
- **R-6.5**: si la primera cue de la escena ENTRANTE cae dentro de la ventana de la transición,
  avisa (no aborta: la escena sigue siendo válida, nace con su primer elemento tapado un
  instante).
- **G4**: el reencode de la transición pasa por `encoder.vf()`/`encoder.cv_args()`, igual que
  `build_segment`, así que respeta `TUT_ENCODER` y todos los tramos siguen compartiendo códec,
  tamaño, pix_fmt y fps.

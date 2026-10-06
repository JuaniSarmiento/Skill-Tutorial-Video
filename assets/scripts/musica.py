"""Música de fondo con ducking bajo la voz (S2 del Hito 2) + "voiceover carve" y perfiles
de loudness por destino (H1, Hito 3, docs/explicador/HITO3.md).

La música la pone Juani en TUT_ROOT/musica/ (la skill no la incluye, ver
docs/explicador/HITO2.md, Q1). Se atenúa para quedar por debajo de la voz: el default
(elegido por editar.py) es 10 LU en los tramos con voz y 10 LU en los silencios (Q3; antes
del carve era 18 LU en voz -ver H1 más abajo-). La transición entre niveles es una rampa,
no un escalón, para no "bombear".

H1: ANTES de ese ducking de banda ancha, `aplicar_carve_voz` baja la música SÓLO en las
bandas de la voz (`BANDAS_VOZ_HZ`, EQ peaking fijo -idea robada de HyperFrames,
heygen-com/hyperframes, Apache 2.0, packages/core/src/audioCarve.ts, bandas fijas en vez de
su análisis FFT por voz) mientras hay voz, y vuelve a sonar entera en los silencios, sin
tocar los graves. Con ese carve haciendo buena parte del trabajo de "sacarse del medio", el
ducking de banda ancha puede bajar menos (10 LU en vez de los 18 originales) y la mezcla
sigue separando la voz de la música. `PERFILES_LOUDNESS` (youtube/redes) elige a qué
integrado y TP normaliza el final, por `"destino"` arriba del guion.
"""
import array
import json
import math
import re
import subprocess
import wave
from pathlib import Path

SILENCIO_LU = 10   # Q3: 10 LU bajo la voz en los silencios (fijo, no configurable en el guion)
MUTE_DB = -90      # "musica": false en un segmento: de sobra por debajo de -60 dBFS (R-2.5)
SR_ENVOLVENTE = 1000  # Hz de la envolvente de ganancia (B1, QA): de sobra para rampas >= 50ms

# J1 (QA 03/10/2026): un ducking profesional baja rápido y sube lento ("attack"/"release"
# de un compresor): antes los dos lados usaban la misma rampa (150ms), y liberar tan rápido
# como atacar se oye como un bombeo. ATTACK_S queda en el rango 100-200ms; RELEASE_S en
# 400-800ms. Además, un hueco CORTO entre frases (silencio < UMBRAL_HUECO_S) no dispara la
# subida a nivel de silencio: la música se queda atenuada hasta que el hueco es de verdad.
ATTACK_S = 0.15
RELEASE_S = 0.6
UMBRAL_HUECO_S = 0.8

# H1 (Hito 3, docs/explicador/HITO3.md): "voiceover carve" -idea y bloque robados de
# HyperFrames (heygen-com/hyperframes, Apache 2.0, commit b9e511a,
# packages/core/src/audioCarve.ts; NO se usa como dependencia, se reimplementa en Python +
# ffmpeg, aviso y atribución acá). Ahí el carve mide el espectro de CADA voz con una FFT
# propia y elige qué bandas dipear; acá se usa el conjunto FIJO que su propio SKILL.md
# documenta como salida a fuerza 0.8 (6 bandas, 250-2500 Hz, -7dB salvo 1.6kHz en -15dB): la
# voz humana ocupa casi siempre esas bandas, y medir el espectro de cada voz agrega una FFT
# por render para casi nunca cambiar qué banda gana. Simplificación deliberada del time-box
# de esta rebanada (~2h); si una voz atípica necesitara otro perfil, queda para abrir boca.
BANDAS_VOZ_HZ: list[tuple[float, float]] = [
    (250, -7.0), (400, -7.0), (630, -7.0), (1000, -7.0), (1600, -15.0), (2500, -7.0),
]
Q_CARVE = 2.06  # HyperFrames: q = 1.1 + strength*1.2; a fuerza 0.8 (su default alto) da 2.06

# H1: perfiles de loudness por destino, elegibles desde "destino" arriba del guion (ver
# editar.py). "youtube" es el default y es EL MISMO comportamiento de antes de este cambio
# (-16 LUFS / TP <= -1.5 dBTP, R-2.3): no regresa nada ya cumplido (G3).
PERFILES_LOUDNESS = {
    "youtube": {"i": -16.0, "tp": -1.5},
    "redes": {"i": -14.0, "tp": -1.0},
}
# N2 (QA 03/10/2026): el AAC del final le agrega TP de más (hasta ~0.7dB medido con música
# picuda): el limitador interno apunta más abajo que el TP real exigido por el perfil, para
# que el final MEDIDO (post-encode) siga cumpliéndolo. Antes era TP_OBJETIVO_CON_MUSICA fijo
# en -2.0 (= -1.5 - 0.5, el perfil "youtube"); ahora es el mismo margen aplicado al perfil
# elegido.
MARGEN_AAC_DB = 0.5


def tp_interno(destino: str) -> float:
    """El TP que se le pide al LIMITADOR final (no a loudnorm) para el perfil `destino`:
    `MARGEN_AAC_DB` más estricto que el TP real exigido, con margen para lo que agrega el
    AAC del mux final."""
    return PERFILES_LOUDNESS[destino]["tp"] - MARGEN_AAC_DB


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """`subprocess.run(cmd, capture_output=True, text=True)`, pero pasando por el vigía
    anti-cuelgue de `editar.run()` (QA 04/10/2026, NOTE ronda 3: todo subprocess de este
    módulo tiene que pasar por ahí, no por `subprocess.run` directo).

    Import perezoso -DENTRO de la función, no arriba del archivo-: `editar.py` hace
    `import musica` en su tope; si este módulo hiciera `import editar` ahí también, el
    ciclo se resolvería mal según quién se importe primero. Acá los dos módulos ya están
    completamente cargados cuando `_run` corre (se llama desde el cuerpo de una función,
    nunca al importar), así que no hay ciclo real.

    `editar.run()` ya devuelve `(stdout, stderr)` con `devolver_stderr=True` y ya decodifica
    con `errors="replace"`; esto sólo adapta esa forma a la que todo el resto de este
    archivo ya esperaba de `subprocess.run` (un objeto con `.returncode`/`.stdout`/`.stderr`),
    para no tener que tocar cada call site más de lo necesario.
    """
    import editar

    try:
        out, err = editar.run(cmd, devolver_stderr=True)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr=err)
    except RuntimeError as e:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))


_RE_INTEGRADA = re.compile(r"Integrated loudness:\s*\n\s*I:\s*(-?\d+\.?\d*) LUFS")


def loudness_integrada(path: Path) -> float:
    """Loudness integrado (LUFS), medido con el filtro ebur128 de ffmpeg."""
    res = _run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128",
               "-f", "null", "-"])
    m = _RE_INTEGRADA.search(res.stderr)
    if not m:
        raise RuntimeError(f"no se pudo medir el loudness de {path}:\n{res.stderr[-1000:]}")
    return float(m.group(1))


_RE_TP = re.compile(r"True peak:\s*\n\s*Peak:\s*(-?\d+\.?\d*) dBFS")


def medir_i_tp(path: Path) -> tuple[float, float]:
    """(I en LUFS, TP en dBTP) de `path`, medidos con ebur128=peak=true."""
    res = _run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true",
               "-f", "null", "-"])
    i = _RE_INTEGRADA.search(res.stderr)
    tp = _RE_TP.search(res.stderr)
    if not i or not tp:
        raise RuntimeError(f"no se pudo medir I/TP de {path}:\n{res.stderr[-1000:]}")
    return float(i.group(1)), float(tp.group(1))


_RE_JSON_LOUDNORM = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def _medir_loudnorm(path: Path, objetivo_i: float, margen_tp: float, lra: float = 11.0) -> dict:
    """1ra pasada de loudnorm (print_format=json): measured_I/TP/LRA/thresh de `path`."""
    res = _run(
        ["ffmpeg", "-nostats", "-i", str(path), "-af",
         f"loudnorm=I={objetivo_i}:TP={margen_tp}:LRA={lra}:print_format=json", "-f", "null", "-"])
    m = _RE_JSON_LOUDNORM.search(res.stderr)
    if not m:
        raise RuntimeError(f"no se pudo medir loudnorm (pasada 1) de {path}:\n{res.stderr[-1500:]}")
    return json.loads(m.group(0))


def normalizar_dos_pasadas(entrada: Path, salida: Path, objetivo_i: float, margen_tp: float,
                            limite_tp_final: float, sr: int = 48000) -> None:
    """Normaliza `entrada` a `objetivo_i` LUFS con **loudnorm de dos pasadas** (QA
    04/10/2026, R-2.3): la 1ra mide (`_medir_loudnorm`), la 2da aplica con `measured_*` y
    `linear=true` para que el integrado llegue al objetivo con precisión -el estándar
    profesional; una sola pasada no llega cuando el TP restringe la ganancia.

    `margen_tp` es el TP que se le pide a loudnorm en las dos pasadas (deliberadamente
    laxo: así no es loudnorm el que frena la ganancia hacia `objetivo_i`). El TP real
    queda garantizado después por un **limitador de TRUE PEAK** aparte (sobremuestreo +
    `alimiter`, porque `linear=true` no limita TP en absoluto) a `limite_tp_final`.
    `-ar sr` queda explícito en la salida: sin esto, el sample rate que loudnorm usa
    internamente para sobremuestrear se cuela a la salida.
    """
    sr_oversample = sr * 4

    def _filtro_limitador(limite_tp: float) -> str:
        limite_lineal = 10 ** (limite_tp / 20)
        # level=disabled: por default alimiter RENORMALIZA la salida (level=true), lo que
        # anula el recorte que acaba de aplicar (QA 04/10/2026: sin esto, el límite pedido
        # no se respetaba en absoluto).
        return (f"aresample={sr_oversample},alimiter=limit={limite_lineal:.6f}:attack=1:release=50:"
                f"level=disabled,aresample={sr}")

    # Paso 1: domar los TRANSIENTES de la entrada ANTES de medir/normalizar (p.ej. música
    # de clicks/percusión: picos aislados muy por encima de 0dBTP). Si no se hace esto
    # primero, loudnorm ve un TP crudo altísimo y reacciona bajando la GANANCIA GLOBAL
    # (modo dinámico) para controlar el pico, lo que hunde el integrado entero en vez de
    # limitar sólo esos picos puntuales -exactamente el bug que esto arregla.
    domada = salida.with_name(f"{salida.stem}.domada.wav")
    res = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(entrada), "-af",
               _filtro_limitador(margen_tp), str(domada)])
    if res.returncode != 0:
        raise RuntimeError(f"falló domando transientes antes de normalizar: {res.stderr[:2000]}")
    try:
        # Paso 2: loudnorm de dos pasadas sobre la señal ya domada (ahora su TP real
        # coincide con `margen_tp`, así que loudnorm puede aplicar la ganancia que hace
        # falta para el integrado sin que el TP la frene).
        medidas = _medir_loudnorm(domada, objetivo_i, margen_tp)
        filtro = (
            f"loudnorm=I={objetivo_i}:TP={margen_tp}:LRA=11:"
            f"measured_I={medidas['input_i']}:measured_TP={medidas['input_tp']}:"
            f"measured_LRA={medidas['input_lra']}:measured_thresh={medidas['input_thresh']}:"
            f"offset={medidas['target_offset']},"
            f"{_filtro_limitador(limite_tp_final)}"
        )
        res = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(domada), "-af", filtro,
                   "-ar", str(sr), str(salida)])
    finally:
        domada.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló normalizando en dos pasadas: {res.stderr[:2000]}")


def duracion(path: Path) -> float:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"ffprobe no pudo leer {path}: {out.stderr[-500:]}")
    return float(out.stdout)


def ventanas(slots: list[float], voces: list[tuple[float, float] | None]) -> list[tuple[float, float, str]]:
    """[(inicio, fin, nivel)] cubriendo [0, total) sin huecos. nivel: "voz"|"silencio"|"mute".

    `voces[i]` es (inicio_rel, fin_rel) de la voz dentro del slot i (LEAD incluido), o None si
    el segmento tiene `"musica": false`: ahí el slot entero queda "mute".
    """
    out = []
    t = 0.0
    for slot, v in zip(slots, voces):
        if v is None:
            out.append((t, t + slot, "mute"))
        else:
            vi, vf = v
            if vi > 0:
                out.append((t, t + vi, "silencio"))
            out.append((t + vi, t + vf, "voz"))
            if vf < slot:
                out.append((t + vf, t + slot, "silencio"))
        t += slot
    return out


def _puntos_envolvente(vts: list[tuple[float, float, str]], ganancias_db: list[float],
                        ramp: float, ramp_release: float | None = None) -> list[tuple[float, float]]:
    """[(t, nivel_db)] que describe la envolvente como curva lineal A TRAMOS EN dB:
    constante en cada meseta, en rampa (no en escalón) entre niveles vecinos. `ramp`
    segundos centrados en cada cambio, recortados si alguna de las dos ventanas vecinas es
    más chica que eso.

    QA 04/10/2026 (NOTE, ronda 3): la interpolación es en dB (no en amplitud lineal como
    antes): interpolar en amplitud lineal da saltos de varios dB en 10ms cerca del extremo
    bajo de una rampa grande (ahí la amplitud lineal cambia poco por muestra, pero esa
    misma variación es enorme en dB -el oído mide en dB, no en amplitud lineal). En dB, la
    rampa es una línea recta de verdad: dB/s constante en toda la transición.

    `ganancias_db` trae una ganancia POR VENTANA (no por nombre de nivel): dos ventanas
    "voz" pueden pedir ganancias distintas si la voz sonaba distinto en cada una (N1, QA).

    J1 (QA 03/10/2026): `ramp` es el ataque (música bajando) y `ramp_release` la liberación
    (música subiendo); si no se da `ramp_release`, se usa `ramp` para los dos lados (como
    antes de J1, simétrico). Las transiciones hacia/desde "mute" siguen usando `ramp` nada
    más (N5): son un corte deliberado, no la "respiración" voz/silencio que J1 ataca.
    """
    ramp_release = ramp if ramp_release is None else ramp_release
    niveles = list(ganancias_db)  # ya están en dB: la interpolación es en dB, no en lineal
    puntos = [(vts[0][0], niveles[0])]
    for i in range(len(vts) - 1):
        b = vts[i][1]
        antes, despues = niveles[i], niveles[i + 1]
        ancho_izq = vts[i][1] - vts[i][0]
        ancho_der = vts[i + 1][1] - vts[i + 1][0]
        nivel_antes, nivel_despues = vts[i][2], vts[i + 1][2]
        # N5 (QA 03/10/2026): entrando o saliendo de "mute" la rampa NO puede cruzar el
        # borde del slot mudo (R-2.5: < -60dBFS en TODO ese slot, desde su primera muestra).
        # Centrada (como el resto de las transiciones) dejaba la mitad de la bajada DENTRO
        # del slot mudo: la música entraba ~ramp/2 "de más". Acá termina de bajar justo en
        # el borde (toda la rampa adentro de la ventana de ANTES), o arranca a subir justo
        # en el borde (toda la rampa adentro de la ventana de DESPUÉS).
        if nivel_despues == "mute" and nivel_antes != "mute":
            r = max(min(ramp, ancho_izq), 0.0)
            lo, hi = b - r, b
        elif nivel_antes == "mute" and nivel_despues != "mute":
            r = max(min(ramp, ancho_der), 0.0)
            lo, hi = b, b + r
        else:
            # J1: subiendo (despues > antes) usa la liberación lenta; bajando, el ataque
            # rápido. Igual que antes si ramp_release == ramp (simétrico).
            r_dir = ramp_release if despues > antes else ramp
            r = max(min(r_dir, ancho_izq, ancho_der), 0.0)
            lo, hi = b - r / 2, b + r / 2
        if r <= 0:
            puntos.append((b, antes))
            puntos.append((b, despues))
        else:
            puntos.append((lo, antes))
            puntos.append((hi, despues))
    puntos.append((vts[-1][1], niveles[-1]))
    return puntos


def _muestras_envolvente(puntos: list[tuple[float, float]], sr: int) -> tuple["array.array[int]", float]:
    """Muestras s16 de la envolvente interpolada EN dB entre `puntos` (QA 04/10/2026: no en
    amplitud lineal -eso da saltos de varios dB en 10ms cerca del extremo bajo de una rampa
    grande), a `sr` Hz, y la `escala` (nivel LINEAL más alto) con la que hay que reescalar
    después de multiplicar.

    Recorre `puntos` con un puntero que sólo avanza (no retrocede): generar la envolvente es
    O(muestras), sin importar cuántos segmentos la originaron (B1).
    """
    total = puntos[-1][0]
    n = max(int(round(total * sr)), 1)
    escala = max(max(10 ** (g_db / 20) for _, g_db in puntos), 1e-9)
    out = array.array("h", bytes(2 * n))
    j = 0
    for i in range(n):
        t = i / sr
        while j + 2 < len(puntos) and puntos[j + 1][0] <= t:
            j += 1
        t0, db0 = puntos[j]
        t1, db1 = puntos[j + 1]
        db = db1 if t1 <= t0 else db0 + (db1 - db0) * (t - t0) / (t1 - t0)
        g = 10 ** (db / 20)
        out[i] = int(max(min(g / escala, 1.0), -1.0) * 32767)
    return out, escala


def _formato(path: Path) -> tuple[int, int]:
    """(sample_rate, canales) del stream de audio de `path`, vía ffprobe."""
    res = _run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels", "-of", "csv=p=0", str(path)])
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"ffprobe no pudo leer el formato de audio de {path}: {res.stderr[:1000]}")
    sr, canales = res.stdout.strip().split(",")
    return int(sr), int(canales)


def _sin_huecos_cortos(vts: list[tuple[float, float, str]], ganancias_db: list[float],
                        umbral: float) -> list[float]:
    """Una ventana "silencio" más corta que `umbral` no deja que la música suba: se queda
    en la ganancia más atenuada de sus vecinas (J1, QA 03/10/2026: un hueco corto entre dos
    frases no es un silencio "de verdad", y subir y volver a bajar ahí es bombeo).

    QA 04/10/2026 (NOTE, ronda 3): un hueco real puede cruzar el borde entre dos slots y
    quedar partido en VARIAS ventanas "silencio" contiguas (una por slot): cada una por
    separado puede ser más corta que `umbral` aunque juntas duren más. Acá se agrupan las
    ventanas "silencio" contiguas y se evalúa la duración TOTAL del grupo, no la de cada
    ventana aislada.
    """
    out = list(ganancias_db)
    i = 0
    while i < len(vts):
        if vts[i][2] != "silencio":
            i += 1
            continue
        j = i
        while j + 1 < len(vts) and vts[j + 1][2] == "silencio":
            j += 1
        duracion_grupo = vts[j][1] - vts[i][0]
        if duracion_grupo < umbral:
            vecinas = [out[k] for k in (i - 1, j + 1) if 0 <= k < len(vts)]
            if vecinas:
                nivel = min(vecinas)
                for k in range(i, j + 1):
                    out[k] = nivel
        i = j + 1
    return out


def aplicar_ducking(pista: Path, vts: list[tuple[float, float, str]],
                     ganancia_db: "dict[str, float] | list[float]", out: Path, ramp: float = 0.15,
                     ramp_release: float | None = None) -> None:
    """Aplica la envolvente de ganancia (por ventana, en rampa) a `pista` y la deja en `out`.

    `ganancia_db` acepta un dict {nivel: dB} (la misma ganancia para todas las ventanas de
    ese nivel) o una lista con una ganancia por ventana (N1, QA: cada ventana "voz" puede
    pedir una ganancia distinta si la voz sonaba distinto ahí).

    B1 (QA 03/10/2026): antes la envolvente era una expresión `if()` anidada para
    `volume=eval=frame` (2 niveles por transición), y el evaluador de ffmpeg corta en 100
    niveles: con >= 33 segmentos (>= ~64 transiciones) fallaba con "Missing ')' or too many
    args" (con 32 andaba). Acá la envolvente se genera como SEÑAL -un wav de muestras
    calculadas en Python, sin ninguna expresión- y se aplica multiplicando sample a sample
    (`amultiply`): la profundidad del filtergraph no depende de la cantidad de segmentos.

    J1 (QA 03/10/2026): un hueco "silencio" corto (< UMBRAL_HUECO_S) entre dos tramos de
    voz no dispara la subida a nivel de silencio (bombeo); `ramp_release`, si se da, hace
    la liberación (subir) más lenta que el ataque (bajar) `ramp`.
    """
    ganancias = ([ganancia_db[nivel] for _, _, nivel in vts] if isinstance(ganancia_db, dict)
                 else list(ganancia_db))
    ganancias = _sin_huecos_cortos(vts, ganancias, UMBRAL_HUECO_S)
    puntos = _puntos_envolvente(vts, ganancias, ramp, ramp_release)
    muestras, escala = _muestras_envolvente(puntos, SR_ENVOLVENTE)
    envolvente = out.with_name(f"{out.stem}.envolvente.wav")
    with wave.open(str(envolvente), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR_ENVOLVENTE)
        w.writeframes(muestras.tobytes())
    try:
        sr, canales = _formato(pista)
        # la envolvente es mono: si la pista tiene más de un canal, se duplica a todos con
        # pan= antes de multiplicar (amultiply exige el mismo layout en los dos lados).
        pan = f",pan={canales}c" + "".join(f"|c{c}=c0" for c in range(canales)) if canales != 1 else ""
        filtro = (f"[1:a]aresample={sr},asetnsamples=n=64{pan}[env];"
                  f"[0:a][env]amultiply[prod];[prod]volume={escala:.8f}[out]")
        res = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pista), "-i", str(envolvente),
                   "-filter_complex", filtro, "-map", "[out]", str(out)])
    finally:
        envolvente.unlink(missing_ok=True)
    if res.returncode != 0:
        # B1 (QA): el mensaje tiene que mostrar el COMIENZO del stderr (ahí está la causa real,
        # p.ej. "Missing ')' or too many args"), no los últimos 1000 caracteres: con un
        # filtergraph grande, la causa queda lejos del final.
        raise RuntimeError(f"falló aplicando el ducking: {res.stderr[:2000]}")


def _puntos_presencia(vts: list[tuple[float, float, str]], ramp_in: float,
                       ramp_out: float) -> list[tuple[float, float]]:
    """[(t, nivel_db)] de cuánto EQ "húmedo" corresponde en cada instante: 0dB (a fondo) en
    las ventanas "voz", MUTE_DB (~0 tras 10**(db/20)) en "silencio"/"mute". Reusa
    `_puntos_envolvente` (la misma máquina de rampas que el ducking de banda ancha).

    `ramp_in`/`ramp_out` entran INVERTIDOS respecto de `ramp`/`ramp_release` de
    `_puntos_envolvente`: ahí "bajando" (atenuar la música) usa `ramp` y "subiendo"
    (liberar) usa `ramp_release`. Acá "entrar a la voz" ES una SUBIDA del valor de
    presencia (MUTE_DB -> 0dB), así que para que entre en `ramp_in` y salga en `ramp_out`
    hay que pasarle a `_puntos_envolvente` `ramp=ramp_out, ramp_release=ramp_in` (swap).
    """
    ganancias = [0.0 if nivel == "voz" else float(MUTE_DB) for _, _, nivel in vts]
    return _puntos_envolvente(vts, ganancias, ramp=ramp_out, ramp_release=ramp_in)


def _muestras_presencia(vts: list[tuple[float, float, str]], ramp_in: float, ramp_out: float,
                         sr: int) -> "array.array[int]":
    """Muestras s16 (0..32767) de la curva de presencia de `_puntos_presencia`, a `sr` Hz."""
    puntos = _puntos_presencia(vts, ramp_in, ramp_out)
    muestras, _escala = _muestras_envolvente(puntos, sr)
    return muestras


def aplicar_carve_voz(pista: Path, vts: list[tuple[float, float, str]], out: Path,
                       ramp: float = ATTACK_S, ramp_release: float = RELEASE_S,
                       bandas: list[tuple[float, float]] = BANDAS_VOZ_HZ,
                       q: float = Q_CARVE) -> None:
    """"Voiceover carve" (H1, HITO3.md): baja `pista` SÓLO en las bandas de la voz
    (`bandas`, EQ peaking) mientras hay voz, con la misma máquina de ataque/liberación que
    `aplicar_ducking` (entra en `ramp` segundos, sale en `ramp_release`); en los silencios
    vuelve a sonar entera, sin tocar nada fuera de esas bandas (los graves quedan intactos).

    Crossfade LINEAL (no en dB) entre `pista` tal cual y la misma `pista` con el EQ fijo de
    `bandas` aplicado: interpolar las dos ramas en dB por separado (como hace
    `aplicar_ducking` con UNA sola señal) deja un pozo de volumen a mitad de camino -ahí las
    dos ramas caen cerca de su propio piso en dB A LA VEZ (ej. -45dB cada una en el punto
    medio de una rampa 0dB<->-90dB), un hueco que no existe en la señal real-. Por eso la
    rama "seca" es el COMPLEMENTO LINEAL (32767 - húmeda) de la curva de presencia, nunca
    su propia pasada por dB.

    B1 (QA 03/10/2026, aplicar_ducking): misma técnica -la envolvente es una SEÑAL (un wav
    de muestras), no una expresión de ffmpeg-, así la profundidad del filtergraph no crece
    con la cantidad de segmentos.
    """
    humeda = _muestras_presencia(vts, ramp, ramp_release, SR_ENVOLVENTE)
    seca = array.array("h", (32767 - max(min(v, 32767), 0) for v in humeda))
    env_humeda = out.with_name(f"{out.stem}.carve-humeda.wav")
    env_seca = out.with_name(f"{out.stem}.carve-seca.wav")
    for envelope, muestras in ((env_humeda, humeda), (env_seca, seca)):
        with wave.open(str(envelope), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR_ENVOLVENTE)
            w.writeframes(muestras.tobytes())
    try:
        sr, canales = _formato(pista)
        pan = f",pan={canales}c" + "".join(f"|c{c}=c0" for c in range(canales)) if canales != 1 else ""
        eq = ",".join(f"equalizer=f={f}:t=q:w={q}:g={g}" for f, g in bandas)
        filtro = (
            f"[0:a]{eq}[eqd];"
            f"[1:a]aresample={sr},asetnsamples=n=64{pan}[hum];"
            f"[2:a]aresample={sr},asetnsamples=n=64{pan}[sec];"
            f"[0:a][sec]amultiply[seco];"
            f"[eqd][hum]amultiply[humedo];"
            f"[seco][humedo]amix=inputs=2:duration=first:normalize=0[out]"
        )
        res = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pista), "-i", str(env_humeda),
                   "-i", str(env_seca), "-filter_complex", filtro, "-map", "[out]", str(out)])
    finally:
        env_humeda.unlink(missing_ok=True)
        env_seca.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló aplicando el carve de voz: {res.stderr[:2000]}")


CROSSFADE_BUCLE = 0.1  # segundos de crossfade en cada costura del bucle (N6, QA 03/10/2026)


MINIMO_BUCLE_X_CROSSFADE = 2  # QA 04/10/2026: rechazar música más corta que esto (NOTE)


def _construir_unidad_de_bucle(archivo: Path, d: float, cf: float, out_unidad: Path) -> None:
    """Una unidad de bucle SIN COSTURA: el crossfade del final de `archivo` sobre su
    comienzo, aplicado UNA sola vez (no por vuelta). Dura `d - cf`: repetida con
    `-stream_loop` (sin más filtros), no hay click en la costura y el costo de generarla
    es O(1) -tres recortes fijos del mismo archivo-, no O(vueltas) (QA 04/10/2026, NOTE:
    antes se encadenaba un `acrossfade` POR VUELTA -1200 inputs para música de 1s en un
    total de 1200s, 294s; con música de 0.15s en 600s, el comando era tan largo que el
    sistema operativo lo rechazaba con "Argument list too long").
    """
    filtro = (
        f"[0:a]atrim=0:{cf:.6f}[a];"
        f"[1:a]atrim={max(d - cf, 0):.6f}:{d:.6f}[b];"
        f"[2:a]atrim={cf:.6f}:{max(d - cf, cf):.6f}[cuerpo];"
        f"[b][a]acrossfade=d={cf:.6f}:c1=tri:c2=tri[costura];"
        f"[costura][cuerpo]concat=n=2:v=0:a=1[out]"
    )
    res = _run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(archivo), "-i", str(archivo), "-i", str(archivo),
         "-filter_complex", filtro, "-map", "[out]", str(out_unidad)])
    if res.returncode != 0:
        raise RuntimeError(f"falló construyendo la unidad de bucle: {res.stderr[:2000]}")


def preparar_pista(archivo: Path, total: float, fundido: float, out: Path) -> None:
    """Deja la música durando exactamente `total` (R-2.4): bucle si es corta, recorte con
    fundido de `fundido` segundos al final si es larga.

    N6 (QA 03/10/2026): -stream_loop repite el clip tal cual, sin pisar los extremos: si no
    cierra en un cruce por cero, cada vuelta salta de golpe del último valor al primero (un
    click). QA 04/10/2026 (NOTE, ronda 3): el crossfade de la costura se arma UNA vez
    (`_construir_unidad_de_bucle`), no por vuelta -el costo no crece con la cantidad de
    vueltas-, y esa unidad se repite con `-stream_loop` sin filtros adicionales.
    """
    d = duracion(archivo)
    if d >= total:
        f = min(fundido, total)
        res = _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(archivo), "-t", f"{total:.3f}",
             "-af", f"afade=t=out:st={max(total - f, 0):.3f}:d={f:.3f}", str(out)])
        if res.returncode != 0:
            raise RuntimeError(f"falló preparando la pista de música: {res.stderr[:2000]}")
        return
    cf = min(CROSSFADE_BUCLE, d / 2)
    if cf > 0 and d < MINIMO_BUCLE_X_CROSSFADE * CROSSFADE_BUCLE:
        raise SystemExit(
            f"ABORTADO: el archivo de música es muy corto para hacer bucle en vueltas sin "
            f"costura ({d:.3f}s < {MINIMO_BUCLE_X_CROSSFADE * CROSSFADE_BUCLE:.3f}s, "
            f"{MINIMO_BUCLE_X_CROSSFADE}x el crossfade de {CROSSFADE_BUCLE}s): {archivo}")
    if cf <= 0:
        vueltas = max(1, int(total // d) + 1)
        res = _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(vueltas), "-i", str(archivo),
             "-t", f"{total:.3f}", str(out)])
        if res.returncode != 0:
            raise RuntimeError(f"falló preparando la pista de música: {res.stderr[:2000]}")
        return
    unidad = out.with_name(f"{out.stem}.unidad-bucle.wav")
    _construir_unidad_de_bucle(archivo, d, cf, unidad)
    try:
        dur_unidad = duracion(unidad)
        vueltas = max(1, int(total // dur_unidad) + 2)
        res = _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(vueltas), "-i", str(unidad),
             "-t", f"{total:.3f}", str(out)])
    finally:
        unidad.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló preparando la pista de música: {res.stderr[:2000]}")


_RE_MOMENTANEO = re.compile(r"pts_time:(-?[\d.]+)\nlavfi\.r128\.M=(-?[\d.]+|-inf|nan)")


def _momentaneos(wav: Path) -> list[tuple[float, float]]:
    """[(pts_time, M_dB)] del loudness MOMENTÁNEO (ventana de 400ms, cada 100ms) de `wav`,
    medido en UNA sola pasada con ebur128 (QA 04/10/2026, NOTE: `construir_pista` ya no
    hace un ffmpeg por ventana de voz -2 por ventana, 57s con 300 segmentos-, sino uno
    para todo el archivo)."""
    meta = wav.with_name(f"{wav.stem}.momentaneos.txt")
    res = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af",
               f"ebur128=metadata=1,ametadata=print:file={meta}", "-f", "null", "-"])
    if res.returncode != 0:
        raise RuntimeError(f"falló midiendo el loudness momentáneo de {wav}: {res.stderr[:1500]}")
    try:
        texto = meta.read_text()
    finally:
        meta.unlink(missing_ok=True)
    out = []
    for m in _RE_MOMENTANEO.finditer(texto):
        val = m.group(2)
        if val not in ("-inf", "nan"):
            out.append((float(m.group(1)), float(val)))
    return out


def _loudness_de_ventanas(wav: Path, ventanas: list[tuple[float, float]],
                           default: float) -> list[float]:
    """Loudness aproximado de cada (inicio, fin) en `ventanas`, en UNA pasada sobre `wav`:
    promedio EN ENERGÍA (no en dB) de los valores momentáneos que caen en cada rango.
    `default` si una ventana no tiene ningún punto adentro (muy corta para el gate)."""
    momentaneos = _momentaneos(wav)
    out = []
    for ini, fin in ventanas:
        valores = [db for t, db in momentaneos if ini <= t < fin]
        if not valores:
            out.append(default)
            continue
        energia = sum(10 ** (v / 10) for v in valores) / len(valores)
        out.append(10 * math.log10(energia) if energia > 0 else float("-inf"))
    return out


def _voz_lu_mas_cercana(voz_lu_por_indice: dict[int, float], i: int, default: float) -> float:
    """El loudness de la ventana "voz" más cercana a `i` en la secuencia (antes si hay,
    si no después): una ventana "silencio"/"mute" no tiene voz propia para medir."""
    for j in range(i - 1, -1, -1):
        if j in voz_lu_por_indice:
            return voz_lu_por_indice[j]
    for j in sorted(k for k in voz_lu_por_indice if k > i):
        return voz_lu_por_indice[j]
    return default


def construir_pista(voz_wav: Path, pista: Path, vts: list[tuple[float, float, str]],
                     debajo_de_la_voz_lu: float, out: Path) -> None:
    """La pista de música ya atenuada (R-2.2): mide la voz y la música, y calcula cuánta
    ganancia hace falta para que la música quede `debajo_de_la_voz_lu` LU bajo la voz en los
    tramos con voz, y SILENCIO_LU en los silencios. "mute" (musica: false) va a MUTE_DB fijo.

    N1 (QA 03/10/2026): la voz se mide POR VENTANA "voz" (no una sola vez para todo el
    archivo): medida una sola vez, con una diferencia grande de volumen entre tramos la
    mitad floja queda mucho más cerca de la música que el piso de R-2.2 (cumple sólo "en
    promedio", no en cada tramo). Las ventanas "silencio"/"mute" no tienen voz propia:
    usan el loudness de la ventana "voz" más cercana en la secuencia.
    """
    musica_lu = loudness_integrada(pista)
    voz_lu_global = loudness_integrada(voz_wav)
    indices_voz = [i for i, (_, _, nivel) in enumerate(vts) if nivel == "voz"]
    ventanas_voz = [(vts[i][0], vts[i][1]) for i in indices_voz]
    voz_lu_por_indice: dict[int, float] = dict(zip(
        indices_voz, _loudness_de_ventanas(voz_wav, ventanas_voz, voz_lu_global)))
    ganancias_db = []
    for i, (ini, fin, nivel) in enumerate(vts):
        if nivel == "mute":
            ganancias_db.append(MUTE_DB)
            continue
        voz_lu = voz_lu_por_indice.get(i, None)
        if voz_lu is None:
            voz_lu = _voz_lu_mas_cercana(voz_lu_por_indice, i, voz_lu_global)
        objetivo = debajo_de_la_voz_lu if nivel == "voz" else SILENCIO_LU
        ganancias_db.append((voz_lu - objetivo) - musica_lu)
    # J1 (QA): acá, en el camino real, el ataque es rápido y la liberación lenta.
    aplicar_ducking(pista, vts, ganancias_db, out, ramp=ATTACK_S, ramp_release=RELEASE_S)


def _tiene_audio(path: Path) -> bool:
    """True si `path` tiene al menos un stream de audio (un mp4 sin audio no lo tiene,
    aunque ffprobe lea bien su duración de CONTENEDOR: esa es de video, no de audio)."""
    out = _run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)])
    return out.returncode == 0 and bool(out.stdout.strip())


def resolver_archivo(root: Path, archivo: str) -> Path:
    """Ruta absoluta del archivo de música, o aborta (R-2.6) si no existe, no se puede leer,
    no tiene audio, o dura 0 segundos.

    N4 (QA 03/10/2026): antes sólo atrapaba RuntimeError de duracion(), así que un wav de
    0s (ffprobe da "N/A", float("N/A") tira ValueError) se escapaba sin SystemExit y sin
    ruta; y un mp4 sin audio pasaba de largo (su duración de CONTENEDOR es válida) y recién
    reventaba más adelante, al tratar de procesarlo como audio, después de escribir la voz.
    """
    ruta = (root / archivo).resolve()
    if not ruta.exists():
        raise SystemExit(f"ABORTADO: no existe el archivo de música: {ruta}")
    try:
        d = duracion(ruta)
    except (RuntimeError, ValueError) as e:
        raise SystemExit(f"ABORTADO: no se pudo leer el archivo de música {ruta}: {e}")
    if d <= 0:
        raise SystemExit(f"ABORTADO: el archivo de música dura 0 segundos: {ruta}")
    if not _tiene_audio(ruta):
        raise SystemExit(f"ABORTADO: el archivo de música no tiene audio: {ruta}")
    return ruta

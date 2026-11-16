# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow", "scipy", "faster-whisper", "av<19"]
# ///
"""Formato «clase con personaje»: un personaje presenta frente a una pizarra, vertical 1080×1920.

Guía completa: references/clase.md. El guion (`"formato": "clase"`) elige personaje, vestuario y
fondo de la biblioteca (`TUT_REPARTO`); lo que falta se genera una vez con `TUT_GENERADOR`.

uso:
  uv run clase.py reparto <guion.json>               resuelve el reparto y genera lo que falta
  uv run clase.py props   <guion.json> [-o props.json]   voz, tiempos, boca, código y audio (sin render)
  uv run clase.py render  <guion.json> [-o video.mp4]    todo lo anterior y el mp4 con Remotion

Las rutas relativas del guion (`codigo`) se resuelven contra TUT_ROOT (por defecto, la carpeta actual).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import reparto  # noqa: E402

SKILL = AQUI.parents[1]
REMOTION = SKILL / "assets" / "remotion"
FUENTES = SKILL / "assets" / "fuentes"
FPS = 30
ANCHO, ALTO = 1080, 1920
LEAD = 0.12   # silencio antes de cada segmento (ritmo de video corto)
TAIL = 0.22   # silencio después
SR = 44100
CAMARAS = ("profe", "normal", "pizarra")
ESCENAS = ("pizarra", "diagrama", "codigo", "terminal")
SFX_TIPOS = ("marcador", "pop", "ding", "whoosh", "teclas", "boing")
I_OBJETIVO, TP_MAXIMO = -16.0, -1.5


def root() -> Path:
    return Path(os.environ.get("TUT_ROOT") or os.getcwd()).resolve()


def falla(msg: str):
    raise SystemExit(f"clase: {msg}")


# ---------- validación (antes de gastar nada) ----------

def validar(g: dict) -> None:
    """Revisa la forma del guion. No genera, no llama a nada: si algo está mal, falla acá."""
    if g.get("formato") != "clase":
        falla("el guion no declara \"formato\": \"clase\"")
    if not isinstance(g.get("voz_id"), str) or not g["voz_id"]:
        falla("falta \"voz_id\" (id de la voz de Fish Audio) arriba del guion")
    try:
        v = float(g.get("velocidad", 1.0))
    except (TypeError, ValueError):
        v = 0
    if v <= 0:
        falla(f"\"velocidad\" tiene que ser un número mayor que 0 (vino {g.get('velocidad')!r})")
    segs = g.get("segmentos")
    if not isinstance(segs, list) or not segs:
        falla("el guion no tiene segmentos")
    codigo = g.get("codigo") or {}
    if not isinstance(codigo, dict):
        falla("\"codigo\" tiene que ser {nombre: ruta del archivo}")
    for nombre, ruta in codigo.items():
        if not (root() / ruta).is_file():
            falla(f"codigo «{nombre}»: no existe {root() / ruta}")
    for i, s in enumerate(segs):
        if not isinstance(s.get("texto"), str) or not s["texto"].strip():
            falla(f"segmento {i}: falta el texto")
        cam = s.get("camara", "normal")
        if cam not in CAMARAS:
            falla(f"segmento {i}: camara «{cam}» no existe (válidas: {', '.join(CAMARAS)})")
        e = s.get("escena") or {}
        tipo = e.get("tipo")
        if tipo not in ESCENAS:
            falla(f"segmento {i}: escena.tipo «{tipo}» no existe (válidas: {', '.join(ESCENAS)})")
        if tipo in ("codigo", "terminal") and e.get("archivo") not in codigo:
            falla(f"segmento {i}: escena {tipo} pide el archivo «{e.get('archivo')}», que no está en \"codigo\"")
        if tipo == "pizarra" and not (e.get("texto") or e.get("lineas")):
            falla(f"segmento {i}: la escena pizarra necesita \"texto\" o \"lineas\"")
        if tipo == "diagrama" and not all(e.get(k) for k in ("condicion", "si", "no")):
            falla(f"segmento {i}: el diagrama necesita \"condicion\", \"si\" y \"no\"")
        for x in s.get("sfx", []):
            if x.get("tipo") not in SFX_TIPOS:
                falla(f"segmento {i}: sfx «{x.get('tipo')}» no existe (válidos: {', '.join(SFX_TIPOS)})")
        for p in s.get("planos", []):
            if p.get("camara") not in CAMARAS or not p.get("cue"):
                falla(f"segmento {i}: cada plano necesita \"cue\" y una \"camara\" válida")
        # toda cue tiene que estar en el texto del segmento (se revisa antes de pagar la voz)
        dichas = " " + " ".join(_norm(w) for w in s["texto"].split() if _norm(w)) + " "
        cues = [x.get("cue") for x in [*s.get("luego", []), *s.get("planos", []), *s.get("sfx", [])]]
        cues += [v for k, v in e.items() if k.startswith("cue_")]
        for c in cues:
            if isinstance(c, str) and f" {' '.join(_norm(w) for w in c.split() if _norm(w))} " not in dichas:
                falla(f"segmento {i}: la cue «{c}» no está en el texto del segmento")


def cargar(ruta: str) -> dict:
    p = Path(ruta)
    if not p.is_file():
        falla(f"no existe el guion {p}")
    g = json.loads(p.read_text())
    validar(g)
    # el reparto también se valida antes de gastar (pose inexistente sin descripción, etc.)
    reparto.planear(g, reparto.leer_catalogo(reparto.biblioteca()))
    return g


def carpeta_trabajo(guion: Path) -> Path:
    d = root() / "videos" / guion.stem
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------- código real ----------

def codigo_y_consola(g: dict) -> tuple[dict, dict]:
    codigo, consola = {}, {}
    for nombre, ruta in (g.get("codigo") or {}).items():
        f = (root() / ruta).resolve()
        codigo[nombre] = f.read_text()
        try:
            r = subprocess.run(["python3", str(f)], capture_output=True, text=True, timeout=30, cwd=f.parent)
        except subprocess.TimeoutExpired:
            falla(f"codigo «{nombre}»: {f.name} no terminó en 30 s")
        if r.returncode != 0:
            falla(f"codigo «{nombre}»: {f.name} salió con {r.returncode}:\n{r.stderr[-800:]}")
        consola[nombre] = r.stdout.splitlines()
    return codigo, consola


# ---------- voz ----------

def _norm(w: str) -> str:
    t = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn" and c.isalnum())


def texto_para_voz(g: dict, texto: str) -> str:
    """Lo que se le manda al TTS: las reglas de pronunciación de Fish de la skill y las del guion
    (`"pronunciacion": {"while": "guáil"}`, por palabra entera). Los subtítulos usan el texto original."""
    import editar
    t = editar.adaptar(texto, "argentina")
    for palabra, dicha in (g.get("pronunciacion") or {}).items():
        t = re.sub(rf"(?<!\w){re.escape(palabra)}(?!\w)", dicha, t)
    return t


_WHISPER = None


def _whisper():
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel(os.environ.get("TUT_WHISPER", "small"), device="cpu", compute_type="int8")
    return _WHISPER


def leer_wav(path: Path):
    import numpy as np
    with wave.open(str(path)) as w:
        assert w.getsampwidth() == 2, path
        a = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768
        a = a.reshape(-1, w.getnchannels()).mean(axis=1)
        return a, w.getframerate()


def escribir_wav(path: Path, a, sr: int) -> None:
    import numpy as np
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())


def voz_segmento(g: dict, i: int, texto: str, cache: Path) -> tuple[Path, list[dict]]:
    """Wav acelerado del segmento y sus palabras (tiempos relativos al wav), cacheados por texto:
    `props` y `render` no regeneran la voz si el texto, la voz y la velocidad no cambiaron."""
    import editar
    dicho = texto_para_voz(g, texto)
    vel = float(g.get("velocidad", 1.0))
    clave = hashlib.sha1(json.dumps([g["voz_id"], dicho, vel], ensure_ascii=False).encode()).hexdigest()[:16]
    crudo, rapido, pal = cache / f"{clave}.wav", cache / f"{clave}-x.wav", cache / f"{clave}.json"
    if rapido.exists() and pal.exists():
        return rapido, json.loads(pal.read_text())
    for intento in range(2):
        if not crudo.exists():
            editar.tts_fish(dicho, crudo, speed=1.0, pausa=0.35, voice=g["voz_id"])
        editar.acelerar_voz(crudo, rapido, vel)
        a, sr = leer_wav(rapido)
        dur = len(a) / sr
        maximo = 0.11 * len(texto) + 1.5   # el TTS a veces alucina y repite: se descarta y se pide de nuevo
        if dur <= maximo:
            break
        crudo.unlink(missing_ok=True)
        rapido.unlink(missing_ok=True)
        if intento == 1:
            falla(f"segmento {i}: la voz dura {dur:.1f} s para {len(texto)} caracteres (máx {maximo:.1f}): "
                  "parece una alucinación del TTS; volvé a correr")
    partes, _ = _whisper().transcribe(str(rapido), language="es", word_timestamps=True, initial_prompt=texto)
    oidas = [{"w": w.word.strip(), "t0": round(w.start, 3), "t1": round(w.end, 3)} for p in partes for w in p.words]
    palabras = alinear(texto, oidas, dur)
    pal.write_text(json.dumps(palabras, ensure_ascii=False))
    return rapido, palabras


def alinear(texto: str, oidas: list[dict], dur: float) -> list[dict]:
    """Las palabras del GUION (no las que oyó Whisper, que puede escribir mal) con tiempos: se ubica
    cada palabra por su posición en el texto contra la posición de lo oído (interpolación monótona)."""
    import numpy as np
    tokens = texto.split()
    if not tokens:
        return []
    oidas = [o for o in oidas if _norm(o["w"])]
    if len(oidas) == len(tokens):
        return [{"w": t, "t0": o["t0"], "t1": o["t1"]} for t, o in zip(tokens, oidas)]

    def fracciones(ws):
        largos = [max(1, len(_norm(w))) for w in ws]
        total = sum(largos)
        acum = np.cumsum([0, *largos])
        return acum[:-1] / total, acum[1:] / total

    g0, g1 = fracciones(tokens)
    if not oidas:  # Whisper no oyó nada: reparto parejo
        return [{"w": t, "t0": round(a * dur, 3), "t1": round(b * dur, 3)} for t, a, b in zip(tokens, g0, g1)]
    o0, o1 = fracciones([o["w"] for o in oidas])
    xs = np.concatenate([[0], o0, [o1[-1]]])
    ts = np.concatenate([[oidas[0]["t0"]], [o["t0"] for o in oidas], [oidas[-1]["t1"]]])
    xe = np.concatenate([o1])
    te = np.array([o["t1"] for o in oidas])
    return [{"w": t, "t0": round(float(np.interp(a, xs, ts)), 3),
             "t1": round(float(max(np.interp(b, xe, te), np.interp(a, xs, ts) + 0.05)), 3)}
            for t, a, b in zip(tokens, g0, g1)]


def buscar_cue(palabras: list[dict], cue: str, i: int) -> float:
    """Momento en que la voz empieza a decir `cue` (palabras del guion, ya con tiempos absolutos)."""
    buscada = [_norm(w) for w in cue.split() if _norm(w)]
    tokens = [_norm(p["w"]) for p in palabras]
    for k in range(len(tokens) - len(buscada) + 1):
        if tokens[k:k + len(buscada)] == buscada:
            return palabras[k]["t0"]
    falla(f"segmento {i}: la cue «{cue}» no está en el texto del segmento")


def boca_de(voz: Path) -> list[list[float]]:
    """Tramos [inicio, fin] (s) con la boca abierta: sólo mientras la voz suena (energía por cuadro)."""
    import numpy as np
    a, sr = leer_wav(voz)
    n = math.ceil(len(a) / sr * FPS)
    rms = np.array([np.sqrt(np.mean(a[int(f * sr / FPS):int((f + 1) * sr / FPS)] ** 2) or 0) for f in range(n)])
    if not len(rms) or rms.max() <= 0:
        return []
    umbral = float(np.median(rms[rms > rms.max() * 0.05])) * 0.5
    abierta = rms > umbral
    tramos, inicio = [], None
    for f, ab in enumerate([*abierta, False]):
        if ab and inicio is None:
            inicio = f
        elif not ab and inicio is not None:
            tramos.append([round(inicio / FPS, 3), round(f / FPS, 3)])
            inicio = None
    return tramos


# ---------- cámara ----------

def planos_de(seg: dict, info: dict, i: int) -> list[dict]:
    """Planos del segmento: [{t, camara}]. El primero es la `camara` del guion; `planos` del guion
    agrega cortes en una cue. Sin `planos`, un segmento largo (o uno que arranca en primer plano) suma
    un corte automático a mitad de la voz (los cortes de cámara dan el ritmo: uno cada 4-5 s)."""
    cam = seg.get("camara", "normal")
    planos = [{"t": info["inicio"], "camara": cam}]
    if seg.get("planos"):
        for p in seg["planos"]:
            planos.append({"t": buscar_cue(info["palabras"], p["cue"], i), "camara": p["camara"]})
        return sorted(planos, key=lambda p: p["t"])
    largo = info["fin"] - info["inicio"]
    # Un primer plano del personaje siempre vuelve al plano general antes de terminar: si no, lo
    # escrito en la pizarra durante ese segmento no se ve nunca.
    if (largo > 4.2 or (cam == "profe" and largo > 2.4)) and len(info["palabras"]) > 3:
        meta = info["voz"] + (info["fin"] - info["voz"]) * 0.55
        corte = min((p["t0"] for p in info["palabras"][1:]), key=lambda t: abs(t - meta))
        # Lo que se lee en la pizarra (diagrama, código, terminal) no se tapa con un primer plano:
        # ahí el corte es a la pizarra (o al plano general si ya estaba en la pizarra).
        lectura = seg["escena"]["tipo"] != "pizarra"
        otra = {"profe": "normal", "normal": "pizarra" if lectura else "profe",
                "pizarra": "normal" if lectura else "profe"}[cam]
        planos.append({"t": round(corte, 3), "camara": otra})
    return planos


# ---------- escenas: tiempos de cada paso ----------

def pasos_de(seg: dict, info: dict, i: int, codigo: dict, consola: dict, rutas: dict) -> dict:
    """La escena con los momentos de cada elemento resueltos (s absolutos). Un elemento entra en su cue
    si el guion la da; si no, repartido a lo largo de la voz. El primero entra al arrancar el segmento:
    la pizarra nunca arranca vacía."""
    e = dict(seg["escena"])
    v0, v1 = info["voz"], info["voz"] + info["dur"]
    pal = info["palabras"]

    def cue(clave: str, defecto: float) -> float:
        c = e.get(f"cue_{clave}")
        return buscar_cue(pal, c, i) if c else defecto

    def reparto_parejo(n: int) -> list[float]:
        return [info["inicio"] if k == 0 else v0 + (v1 - v0) * k / n for k in range(n)]

    tipo = e["tipo"]
    if tipo == "pizarra":
        lineas = e.get("lineas") or [e["texto"]]
        ts = reparto_parejo(len(lineas) + 1)
        e["lineas"] = lineas
        e["t"] = [cue(f"linea{k}", ts[k]) for k in range(len(lineas))]
        e["t_subrayado"] = cue("subrayado", max(ts[-1], e["t"][-1] + 0.8))
        e["t_adorno"] = max(e["t_subrayado"] + 0.9, v0 + (v1 - v0) * 0.85)
    elif tipo == "diagrama":
        ts = reparto_parejo(5)
        e["t"] = {"rombo": info["inicio"], "condicion": ts[1] - 0.6 if ts[1] - 0.6 > info["inicio"] else info["inicio"] + 0.2,
                  "si": cue("si", ts[2]), "no": cue("no", ts[3])}
        camino = e.get("camino", "si")
        e["camino"] = camino if camino in ("si", "no") else "si"
        e["t"]["ficha"] = cue("ficha", max(ts[4], max(e["t"]["si"], e["t"]["no"]) + 0.5))
    elif tipo == "codigo":
        lineas = codigo[e["archivo"]].rstrip("\n").split("\n")
        e["lineas"] = lineas
        n = len(lineas)
        fin_tipeo = v0 + (v1 - v0) * 0.85
        e["t"] = [info["inicio"] + (fin_tipeo - info["inicio"]) * k / n for k in range(n)]
        e["dur_linea"] = max(0.25, min(0.9, (fin_tipeo - info["inicio"]) / n * 0.8))
        e["nombre"] = Path(rutas[e["archivo"]]).name
    elif tipo == "terminal":
        lineas = codigo[e["archivo"]].rstrip("\n").split("\n")
        salida = consola[e["archivo"]]
        e["codigo"] = lineas
        e["salida"] = salida
        e["nombre"] = Path(rutas[e["archivo"]]).name
        e["t_comando"] = info["inicio"] + 0.1
        t_sal = cue("salida", v0 + (v1 - v0) * 0.3)
        paso = min(0.6, max(0.15, (v1 - t_sal) * 0.6 / max(1, len(salida))))
        e["t_salida"] = [t_sal + k * paso for k in range(len(salida))]
        e["t_remate"] = cue("remate", max(t_sal + len(salida) * paso + 0.4, v0 + (v1 - v0) * 0.65))
    return e


def sfx_de(seg: dict, e: dict, info: dict, i: int, cambio_camara: bool) -> list[dict]:
    """Efectos de un segmento: los automáticos de su escena + los que pida el guion (`sfx`)."""
    s = []
    tipo = e["tipo"]
    if tipo == "pizarra":
        s += [{"tipo": "marcador", "t": t} for t in e["t"]]
        s.append({"tipo": "pop", "t": e["t_subrayado"]})
    elif tipo == "diagrama":
        s += [{"tipo": "marcador", "t": e["t"]["rombo"] + 0.05}, {"tipo": "pop", "t": e["t"]["si"]},
              {"tipo": "pop", "t": e["t"]["no"]}, {"tipo": "ding", "t": e["t"]["ficha"] + 0.9}]
    elif tipo == "codigo":
        s.append({"tipo": "teclas", "t": e["t"][0]})
    elif tipo == "terminal":
        s += [{"tipo": "teclas", "t": e["t_comando"]}, {"tipo": "ding", "t": e["t_salida"][0] if e["t_salida"] else e["t_remate"]}]
    if cambio_camara and i > 0:
        s.append({"tipo": "whoosh", "t": info["inicio"]})
    for x in seg.get("sfx", []):
        t = buscar_cue(info["palabras"], x["cue"], i) if x.get("cue") else info["inicio"]
        s.append({"tipo": x["tipo"], "t": t})
    return [{"tipo": x["tipo"], "t": round(max(0.0, x["t"]), 3)} for x in s]


# ---------- música y efectos (sintetizados: nada bajado, nada con licencia) ----------

def _t(d: float):
    import numpy as np
    return np.arange(int(SR * d)) / SR


def _poner(buf, senal, seg: float, gan: float = 1.0) -> None:
    i = int(max(0, seg) * SR)
    if i >= len(buf):
        return
    k = min(len(senal), len(buf) - i)
    buf[i:i + k] += gan * senal[:k]


def musica(dur: float, voz, voz_sr: int, semilla: int = 7):
    """Cama suave tipo lo-fi a 88 BPM (piano eléctrico, bajo, bombo blando) que baja mientras hay voz."""
    import numpy as np
    rng = np.random.default_rng(semilla)
    n = int(SR * dur)
    pulso = 60 / 88
    mus = np.zeros(n)

    def epiano(f, d):
        t = _t(d)
        env = np.exp(-t * 2.2) * (1 - np.exp(-t * 200))
        return (np.sin(2 * np.pi * f * t + 0.6 * np.sin(2 * np.pi * f * t) * np.exp(-t * 4))
                + 0.15 * np.sin(2 * np.pi * 2 * f * t)) * env

    acordes = [[261.6, 329.6, 392.0, 493.9], [220.0, 261.6, 329.6, 392.0],
               [174.6, 220.0, 261.6, 329.6], [196.0, 246.9, 293.7, 349.2]]
    bajos = [65.41, 55.0, 43.65, 49.0]
    tk = _t(0.3)
    bombo = np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-tk * 30)) / SR) * np.exp(-tk * 12)
    th = _t(0.04)
    hat = np.diff(rng.standard_normal(len(th)) * np.exp(-th * 120), prepend=0)
    k = 0
    while k * pulso < dur:
        tb, compas = k * pulso, (k // 4) % 4
        if k % 4 == 0:
            for j, f in enumerate(acordes[compas]):
                _poner(mus, epiano(f, pulso * 4), tb + j * 0.025, 0.16)
            tbj = _t(pulso * 3.8)
            _poner(mus, np.sin(2 * np.pi * bajos[compas] * tbj) * np.exp(-tbj * 0.8), tb, 0.35)
        if k % 4 == 2:
            _poner(mus, epiano(acordes[compas][-1] * 2, pulso * 1.5), tb + pulso * 0.5, 0.09)
        if k % 2 == 0:
            _poner(mus, bombo, tb, 0.35)
        _poner(mus, hat, tb + pulso / 2, 0.06)
        k += 1
    paso = max(1, voz_sr // 100)
    env = np.array([np.sqrt(np.mean(voz[j:j + paso] ** 2)) for j in range(0, len(voz), paso)])
    activa = np.convolve((env > 0.02).astype(float), np.ones(30) / 30, "same")
    activa = np.interp(np.arange(n) / SR, np.arange(len(activa)) / 100, activa, right=0)
    mus *= 1 - 0.6 * np.clip(activa * 1.5, 0, 1)   # ~8 dB abajo mientras se habla
    mus[: int(SR * 0.05)] *= np.linspace(0, 1, int(SR * 0.05))
    fin = min(n, int(SR * 1.5))
    mus[-fin:] *= np.linspace(1, 0, fin)
    return mus / (np.max(np.abs(mus)) or 1) * 0.2


def efecto(tipo: str, rng):
    import numpy as np

    def filtrado(ruido, corte):
        out, y = np.zeros(len(ruido)), 0.0
        for j in range(len(ruido)):
            y += corte[j] * (ruido[j] - y)
            out[j] = y
        return out

    if tipo == "marcador":   # fibrón sobre la pizarra
        d = 0.42
        t = _t(d)
        trazos = np.clip(np.sin(np.pi * t / d * 2) * 1.4, 0, 1) ** 0.5
        ruido = filtrado(rng.standard_normal(len(t)), np.full(len(t), 0.35))
        chillido = 0.25 * np.sin(2 * np.pi * (1800 + 300 * np.sin(2 * np.pi * 7 * t)) * t)
        s = (ruido - filtrado(ruido, np.full(len(t), 0.05)) + chillido) * trazos
    elif tipo == "whoosh":
        d = 0.4
        t = _t(d)
        s = filtrado(rng.standard_normal(len(t)), 0.02 + 0.25 * np.sin(np.pi * t / d) ** 2) * np.sin(np.pi * t / d)
    elif tipo == "pop":
        t = _t(0.14)
        s = np.sin(2 * np.pi * np.cumsum(900 * np.exp(-t * 18) + 250) / SR) * np.exp(-t * 28)
    elif tipo == "ding":
        t = _t(0.9)
        s = (np.sin(2 * np.pi * 1320 * t) + 0.4 * np.sin(2 * np.pi * 2640 * t)) * np.exp(-t * 5)
    elif tipo == "boing":
        t = _t(0.5)
        s = np.sin(2 * np.pi * np.cumsum(180 + 120 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 4)) / SR) * np.exp(-t * 5)
    else:  # teclas
        d = 1.2
        s = np.zeros(int(SR * d))
        tc = _t(0.03)
        clic = rng.standard_normal(len(tc)) * np.exp(-tc * 220)
        for x in np.cumsum(rng.uniform(0.06, 0.13, 20)):
            if x < d - 0.05:
                _poner(s, clic, x, 0.5)
    return s / (np.max(np.abs(s)) or 1)


GANANCIA_SFX = {"marcador": 0.2, "teclas": 0.15, "whoosh": 0.2, "pop": 0.28, "ding": 0.22, "boing": 0.25}


def pista_sfx(dur: float, sfx: list[dict]):
    import numpy as np
    rng = np.random.default_rng(11)
    buf = np.zeros(int(SR * dur))
    for x in sfx:
        adelanto = 0.18 if x["tipo"] == "whoosh" else 0.0   # el whoosh llega a su pico en el corte
        _poner(buf, efecto(x["tipo"], rng), x["t"] - adelanto, GANANCIA_SFX[x["tipo"]])
    return np.clip(buf, -0.9, 0.9)


# ---------- props ----------

def armar_props(guion_path: Path, g: dict, rep: dict) -> dict:
    import numpy as np
    import editar
    trabajo = carpeta_trabajo(guion_path)
    cache = trabajo / "voz"
    cache.mkdir(exist_ok=True)
    codigo, consola = codigo_y_consola(g)

    t, rate, pcm, infos = 0.0, None, [], []
    for i, seg in enumerate(g["segmentos"]):
        wav, palabras = voz_segmento(g, i, seg["texto"], cache)
        a, sr = leer_wav(wav)
        if rate is None:
            rate = sr
        elif sr != rate:
            falla(f"segmento {i}: la voz salió a {sr} Hz y la anterior a {rate} Hz")
        dur = len(a) / sr
        voz0 = t + LEAD
        fin = voz0 + dur + TAIL + float(seg.get("pausa", 0.0))
        infos.append({"inicio": round(t, 3), "fin": round(fin, 3), "voz": round(voz0, 3), "dur": round(dur, 3),
                      "palabras": [{"w": p["w"], "t0": round(voz0 + p["t0"], 3), "t1": round(voz0 + p["t1"], 3)}
                                   for p in palabras]})
        pcm += [np.zeros(int(LEAD * sr)), a, np.zeros(int((fin - voz0 - dur) * sr))]
        t = fin
    voz = np.concatenate(pcm)
    duracion = round(len(voz) / rate, 3)
    voz_wav = trabajo / "voz.wav"
    escribir_wav(voz_wav, voz, rate)

    segmentos, sfx, cam_prev = [], [], None
    for i, (seg, info) in enumerate(zip(g["segmentos"], infos)):
        e = pasos_de(seg, info, i, codigo, consola, g.get("codigo") or {})
        planos = planos_de(seg, info, i)
        luego = [{"pose": x["pose"], "t": buscar_cue(info["palabras"], x["cue"], i)} for x in seg.get("luego", [])]
        sfx += sfx_de(seg, e, info, i, planos[0]["camara"] != cam_prev)
        cam_prev = planos[-1]["camara"]
        segmentos.append({"texto": seg["texto"], "pose": seg.get("pose", "parado"), "luego": luego,
                          "camara": seg.get("camara", "normal"), "planos": planos, "escena": e, **info})
    sfx.sort(key=lambda x: x["t"])

    mus_wav, sfx_wav = trabajo / "musica.wav", trabajo / "sfx.wav"
    escribir_wav(mus_wav, musica(duracion + 0.3, voz, rate), SR)
    escribir_wav(sfx_wav, pista_sfx(duracion + 0.3, sfx), SR)

    publico = {"fondo": "fondo.png",
               "poses": {p: {"cerrada": f"poses/{p}-cerrada.png", "abierta": f"poses/{p}-abierta.png",
                             "boca": f["boca"]} for p, f in rep["poses"].items()}}
    return {"titulo": g.get("titulo", ""), "fps": FPS, "ancho": ANCHO, "alto": ALTO, "duracion": duracion,
            "voz": str(voz_wav), "musica": str(mus_wav), "sfx_wav": str(sfx_wav), "sfx": sfx,
            "boca": boca_de(voz_wav), "codigo": codigo, "consola": consola, "pizarra": rep["pizarra"],
            "reparto": {k: rep[k] for k in ("personaje", "vestuario", "fondo", "referencia", "fondo_archivo",
                                             "poses", "biblioteca")},
            "publico": publico, "colores": colores_del_fondo(Path(rep["fondo_archivo"])), "segmentos": segmentos}


def colores_del_fondo(fondo: Path) -> dict:
    """Color de la franja de arriba y de la de abajo del fondo: con eso se completa el cuadro de 1920."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(fondo).convert("RGB").resize((108, 162))).astype(float)
    hexa = lambda c: "#" + "".join(f"{int(round(x)):02x}" for x in c)
    return {"arriba": hexa(np.median(a[:3].reshape(-1, 3), axis=0)), "abajo": hexa(np.median(a[-3:].reshape(-1, 3), axis=0))}


# ---------- audio final ----------

def mezclar(props: dict, salida: Path) -> None:
    """Voz + música + efectos, normalizado a -16 LUFS con un limitador de true peak con margen
    (el AAC sube el pico: se apunta más abajo y se mide sobre el mp4)."""
    import numpy as np
    import musica as mus_mod
    import editar
    with tempfile.TemporaryDirectory() as tmp_:
        tmp = Path(tmp_)
        voz44 = tmp / "voz44.wav"
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-i", props["voz"], "-ar", str(SR), "-ac", "1", str(voz44)])
        voz, _ = leer_wav(voz44)
        mus, _ = leer_wav(Path(props["musica"]))
        efx, _ = leer_wav(Path(props["sfx_wav"]))
        n = int(SR * props["duracion"])
        mezcla = np.zeros(n)
        for pista, gan in ((voz, 1.0), (mus, 0.9), (efx, 1.0)):
            k = min(n, len(pista))
            mezcla[:k] += gan * pista[:k]
        crudo = tmp / "mezcla.wav"
        escribir_wav(crudo, mezcla / (np.max(np.abs(mezcla)) or 1) * 0.9, SR)
        mus_mod.normalizar_dos_pasadas(crudo, salida, I_OBJETIVO, -0.5, -3.0, sr=48000)


def muxear(video: Path, audio: Path, salida: Path, duracion: float) -> tuple[float, float]:
    """Pone el audio al video (AAC) y mide I/TP sobre el mp4; si el AAC lo corrió, corrige la ganancia."""
    import musica as mus_mod
    import editar
    gan = 0.0
    for _ in range(4):
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-af", f"volume={gan:.2f}dB,alimiter=limit={10 ** ((-3.0 + min(0, gan)) / 20):.4f}:level=disabled",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-t", f"{duracion:.3f}", "-movflags", "+faststart",
                    str(salida)], timeout=600)
        i, tp = mus_mod.medir_i_tp(salida)
        if abs(i - I_OBJETIVO) <= 0.5 and tp <= TP_MAXIMO:
            return i, tp
        if tp > TP_MAXIMO:
            gan -= (tp - TP_MAXIMO) + 0.3
        else:
            gan += I_OBJETIVO - i
    return i, tp


# ---------- Remotion ----------

def asegurar_remotion() -> None:
    if (REMOTION / "node_modules" / "remotion").is_dir() and (REMOTION / "node_modules" / "@remotion" / "cli").is_dir():
        return
    if not shutil.which("npm"):
        falla("hace falta Node.js (npm) para renderizar con Remotion")
    cmd = ["npm", "ci"] if (REMOTION / "package-lock.json").exists() else ["npm", "install"]
    print(f"instalando el motor de Remotion ({' '.join(cmd)})…", flush=True)
    r = subprocess.run([*cmd, "--no-audit", "--no-fund"], cwd=REMOTION, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        falla(f"no se pudo instalar Remotion:\n{r.stderr[-1500:]}")


def armar_publico(props: dict, publico: Path) -> None:
    rep = props["reparto"]
    (publico / "poses").mkdir(parents=True)
    shutil.copy(rep["fondo_archivo"], publico / "fondo.png")
    for p, f in rep["poses"].items():
        shutil.copy(f["cerrada"], publico / "poses" / f"{p}-cerrada.png")
        shutil.copy(f["abierta"], publico / "poses" / f"{p}-abierta.png")
    (publico / "fuentes").mkdir()
    for f in FUENTES.glob("*.ttf"):
        shutil.copy(f, publico / "fuentes" / f.name)


def renderizar(props: dict, salida: Path) -> None:
    asegurar_remotion()
    with tempfile.TemporaryDirectory(prefix="clase-") as tmp_:
        tmp = Path(tmp_)
        publico = tmp / "publico"
        armar_publico(props, publico)
        props_r = tmp / "props.json"
        props_r.write_text(json.dumps(props, ensure_ascii=False))
        mudo = tmp / "mudo.mp4"
        cmd = ["npx", "remotion", "render", "src/index.ts", "Clase", str(mudo), f"--props={props_r}",
               f"--public-dir={publico}", "--muted", "--log=error"]
        if os.environ.get("TUT_REMOTION_CONCURRENCY"):
            cmd.append(f"--concurrency={os.environ['TUT_REMOTION_CONCURRENCY']}")
        print("renderizando con Remotion…", flush=True)
        r = subprocess.run(cmd, cwd=REMOTION, capture_output=True, text=True, timeout=3000)
        if r.returncode != 0 or not mudo.is_file():
            falla(f"Remotion falló:\n{(r.stdout + r.stderr)[-2500:]}")
        audio = tmp / "audio.wav"
        mezclar(props, audio)
        final = tmp / "final.mp4"
        i, tp = muxear(mudo, audio, final, props["duracion"])
        salida.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(final), salida)
    print(f"{salida}  ({props['duracion']:.1f} s, {i:.1f} LUFS, TP {tp:.1f} dBTP)")


# ---------- comandos ----------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="clase.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("comando", choices=["reparto", "props", "render"])
    ap.add_argument("guion")
    ap.add_argument("-o", "--salida")
    a = ap.parse_args(argv)
    guion = Path(a.guion).resolve()
    g = cargar(a.guion)
    rep = reparto.resolver(g)
    if a.comando == "reparto":
        return
    props = armar_props(guion, g, rep)
    trabajo = carpeta_trabajo(guion)
    if a.comando == "props":
        out = Path(a.salida) if a.salida else trabajo / "props.json"
        out.write_text(json.dumps(props, ensure_ascii=False, indent=1))
        print(f"{out}  ({props['duracion']:.1f} s, {len(props['segmentos'])} segmentos, {len(props['sfx'])} efectos)")
        return
    (trabajo / "props.json").write_text(json.dumps(props, ensure_ascii=False, indent=1))
    renderizar(props, Path(a.salida) if a.salida else trabajo / f"{guion.stem}.mp4")


if __name__ == "__main__":
    main()

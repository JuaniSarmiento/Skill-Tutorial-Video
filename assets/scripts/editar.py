#!/usr/bin/env python3
"""Arma los videos del tutorial a partir de las grabaciones crudas y un guion por segmentos.

Idea: los slots se miden CON LA VOZ. Para cada tramo se genera primero el audio, se mide, y
el video de ese tramo se estira o acelera para durar lo mismo. Así no hay silencios de relleno.

OJO: eso significa que la imagen depende de la voz. Cambiar de voz NO es sólo regenerar el
audio: hay que rehacer `imagen` también, porque los slots cambian. Por eso cada voz tiene su
propio `video-<voz>.mp4` y su `slots-<voz>.json`. (El docstring original decía lo contrario
y mandaba a la gente a un remux que falla con FileNotFoundError.)

Cada segmento acepta "zoom": {"x","y","w","h"} para ampliar una región durante ese tramo,
y "raw": otro archivo crudo, para armar un video largo con capítulos grabados por separado.

uso:
  editar.py imagen  <vNN> [voz]      arma videos/<vNN>/video-<voz>.mp4 con slots medidos con esa voz (sin silencios de relleno)
  editar.py voz     <vNN> <voz>      genera videos/<vNN>/voz-<voz>.wav y final-<voz>.mp4 (+ .srt)
  editar.py exportar <vNN>           exporta textos por segmento para generar voces fuera (Colab)
  editar.py escenas <vNN> [voz]      deja videos/<vNN>/escenas/NN.json listos para la hoja de contacto (no renderiza)
  editar.py revisar <vNN> [voz] [--estricto]   el director: mide tiempo muerto, silencios y roles (sección Director en SKILL.md). Sólo lee: no genera ni modifica nada. Sin --estricto sale siempre con 0; con --estricto sale con 1 si hay hallazgos

Un segmento con "escena": {"tipo": "diagrama|presentacion|datos", ...} no se corta del crudo:
se renderiza con el motor de escenas (escena.py) y dura su slot, igual que los demás. Con
escenas, editar.py corre con: uv run --with playwright --with faster-whisper --with "av<19" python editar.py ...
voces: argentina (PRINCIPAL: Fish, femenina argentina, speed 0.80, la mas expresiva medida) | joven (Fish, "Narrador Joven argentino") | profe (Fish, Profesora Argentina, la mas plana) | daniela (Piper local) | juani (wavs importados en videos/<vNN>/juani/NN.wav) | elevenlabs (API, key en ~/.config/elevenlabs/api_key) | fish (Fish Audio, Profesora Argentina, key en ~/.config/fish/api_key)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import wave
from pathlib import Path

import encoder
import musica

ROOT = Path(os.environ.get("TUT_ROOT", os.getcwd()))
PIPER_MODEL = Path.home() / ".local/share/piper-voices/es_AR-daniela-high.onnx"
_ES_WINDOWS = sys.platform.startswith("win")


def _ruta_fuente(path: str, es_windows: bool = _ES_WINDOWS) -> str:
    """Ruta de fuente lista para el fontfile= de un filtro drawtext de ffmpeg.

    En ese filtro, ':' separa opciones (fontfile=RUTA:text=...:...). Una ruta
    de Windows tipo C:/Windows/Fonts/arialbd.ttf choca con eso: hay que
    envolverla entre comillas simples con el ':' escapado. En Linux la ruta
    no tiene ':' y se usa tal cual, sin tocarla.
    """
    if es_windows:
        return "'" + path.replace(":", r"\:") + "'"
    return path


FONT_BOLD = _ruta_fuente("C:/Windows/Fonts/arialbd.ttf" if _ES_WINDOWS
                         else "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf")
FONT = _ruta_fuente("C:/Windows/Fonts/arial.ttf" if _ES_WINDOWS
                    else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
RATE = 22050
LEAD = 0.3  # silencio antes de que arranque la voz en cada slot
TAIL = 0.5  # margen después de la voz
# N2 (QA 03/10/2026): el target de TP que se le pide a loudnorm en el camino CON música
# (-c:a aac le agrega TP de más después, hasta ~0.7dB medido con música picuda): más
# abajo que el -1.5 de R-2.3 para que el final MEDIDO (post-encode) siga cumpliéndolo.
TP_OBJETIVO_CON_MUSICA = -2.0


def _timeout_default() -> float:
    return float(os.environ.get("TUT_FFMPEG_TIMEOUT", "120"))


def run(cmd: list[str], timeout: float | None = None) -> str:
    """Corre `cmd` y devuelve stdout; falla (RuntimeError) si el proceso no termina bien.

    B2 (QA 03/10/2026): `timeout` (default `TUT_FFMPEG_TIMEOUT`) ya NO es un límite total
    -eso cortaba tramos largos que iban progresando bien, como un screen recording de 20
    minutos en la 2da pasada de build_segment-, sino segundos SIN AVANCE: el cuelgue real
    (atempo con ciertos wavs) es un deadlock con 0% CPU y sin salida. Si `cmd` es ffmpeg, se
    le agrega `-progress pipe:1` para tener un latido aunque "-loglevel error" lo deje
    callado mientras todo va bien; si no es ffmpeg (ffprobe, o los comandos de los tests),
    cualquier byte nuevo en stdout/stderr cuenta como avance, y sin avance alguno el límite
    sigue actuando como un timeout total (como antes).
    """
    t = timeout if timeout is not None else _timeout_default()
    es_ffmpeg = bool(cmd) and Path(cmd[0]).name == "ffmpeg"
    cmd_run = [cmd[0], "-progress", "pipe:1", *cmd[1:]] if es_ffmpeg else list(cmd)

    proc = subprocess.Popen(cmd_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    salida: dict[str, list[str]] = {"out": [], "err": []}
    estado = {"ultimo": time.monotonic()}
    bloqueo = threading.Lock()

    def _leer(stream, clave: str) -> None:
        for linea in iter(stream.readline, ""):
            with bloqueo:
                salida[clave].append(linea)
                estado["ultimo"] = time.monotonic()
        stream.close()

    hilos = [threading.Thread(target=_leer, args=(proc.stdout, "out"), daemon=True),
             threading.Thread(target=_leer, args=(proc.stderr, "err"), daemon=True)]
    for h in hilos:
        h.start()

    colgado = False
    while proc.poll() is None:
        time.sleep(0.05)
        with bloqueo:
            ocioso = time.monotonic() - estado["ultimo"]
        if ocioso > t:
            colgado = True
            proc.kill()
            break
    proc.wait()
    for h in hilos:
        h.join(timeout=1)

    if colgado:
        if es_ffmpeg and cmd:
            # el último argumento es la salida por convención en todos los llamados de este
            # módulo: a medio escribir, un .mp4/.wav parcial es peor que no tener nada (un
            # render repetido lo encontraría y lo daría por bueno).
            Path(cmd[-1]).unlink(missing_ok=True)
        raise RuntimeError(f"TUT_FFMPEG_TIMEOUT: {t:.1f}s sin avance corriendo: {' '.join(cmd)}")

    if proc.returncode != 0:
        # N6 (QA): si el tramo que falló usaba VAAPI, sugerir software en vez de
        # dejar que el usuario mezcle encoders a mitad de un render (rompe G4).
        sugerencia = ("\n(usaba h264_vaapi: probá TUT_ENCODER=software)" if "h264_vaapi" in cmd else "")
        raise RuntimeError(f"falló: {' '.join(cmd)}\n{''.join(salida['err'])[-2000:]}{sugerencia}")
    return "".join(salida["out"])


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def load(vid: str) -> dict:
    return json.loads((ROOT / "guion" / f"{vid}.json").read_text())


def tts_daniela(text: str, out: Path) -> None:
    subprocess.run(["piper", "-m", str(PIPER_MODEL), "-f", str(out)], input=text, text=True, capture_output=True, check=True)


ELEVEN_VOICE = "iP95p4xoKVk53GoZ742B"  # Chris (prediseñada: la cuenta gratis no permite voces de biblioteca por API)
ELEVEN_MODEL = "eleven_flash_v2_5"  # cuesta 0.5 crédito por carácter
ELEVEN_KEY = Path.home() / ".config/elevenlabs/api_key"


def tts_elevenlabs(text: str, out: Path) -> None:
    import urllib.request
    key = ELEVEN_KEY.read_text().strip()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": key})
    sub = json.loads(urllib.request.urlopen(req).read())
    restante = sub["character_limit"] - sub["character_count"]
    if restante < len(text):
        raise RuntimeError(f"ElevenLabs sin cupo: quedan {restante} créditos y el texto pide {len(text)}")
    body = json.dumps({"text": text, "model_id": ELEVEN_MODEL, "language_code": "es",
                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 1.05}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": key, "Content-Type": "application/json"}, method="POST")
    mp3 = out.with_suffix(".mp3")
    mp3.write_bytes(urllib.request.urlopen(req).read())
    trim_silence(mp3, out)
    mp3.unlink()


FISH_VOICE = "55589185654d4d5abc1035280611fb65"  # "Profesora Argentina" (biblioteca de Fish Audio)
FISH_MODEL = "s2.1-pro-free"
FISH_KEY = Path.home() / ".config/fish/api_key"


# Velocidad por voz. 0.8 suena a dictado (~118 pal/min); 1.0 es el ritmo natural de la
# voz (~148 pal/min) y es el que se escucha "de persona". Juani lo detectó reproduciendo
# los videos a 1.25x: eso es exactamente 0.8 -> 1.0.
FISH_SPEED = {"joven": 0.90, "argentina": 0.80}     # 170 pal/min: el ritmo natural. 0.8 daba 137 (dictado), 1.0 da 190 (apurado)
# A mas velocidad, pausas mas cortas o suena cortado. OJO: este parametro solo
# recorta silencios que YA existen, asi que en una voz que habla de corrido es
# inerte. En "argentina", los valores 0.35/0.45/0.55/0.70 dan la MISMA duracion
# al milisegundo: no tiene un solo silencio de mas de 0.2 s (medido hasta -28 dB).
# El 0.45 queda por coherencia, no porque cambie algo. Antes de tocarlo en una voz
# nueva, comprobar con silencedetect que hay silencios que recortar.
FISH_PAUSA = {"joven": 0.55, "argentina": 0.45}

# voces de la biblioteca de Fish Audio (la velocidad la define FISH_SPEED)
FISH_LENTAS = {
    "profe": "55589185654d4d5abc1035280611fb65",    # Profesora Argentina
    "joven": "b23ed8db79dd49feac23dacfdf762a18",    # Narrador Joven argentino
    "mendoza": "dcda4aaeb81c4a95bb9ac659b6753e41",  # Hombre Argentino (Mendoza), acento cuyano
    # Femenina argentina, tags educational/energetic/enthusiastic. Elegida el
    # 2026-09-22 midiendo expresividad (rango de pitch) sobre el MISMO texto en
    # 9 voces: 116 Hz contra los 51 Hz de "profe", que era la mas plana de todas.
    # speed 0.80 no es solo "mas lento que 0.84": tambien mide MAS expresivo
    # (116 Hz contra 100). Acelerarla la aplana, no solo la apura.
    "argentina": "8430c634564043c4a97e3828f5079baa",
}


def tts_fish(text: str, out: Path, speed: float = 1.0, pausa: float = 0.35, voice: str = FISH_VOICE) -> None:
    import time
    import urllib.error
    import urllib.request
    body = json.dumps({"text": text, "reference_id": voice, "format": "mp3", "normalize": True,
                       "prosody": {"speed": speed}}).encode()
    for intento in range(4):
        req = urllib.request.Request(
            "https://api.fish.audio/v1/tts", data=body, method="POST",
            headers={"Authorization": f"Bearer {FISH_KEY.read_text().strip()}", "model": FISH_MODEL,
                     "Content-Type": "application/json"})
        try:
            data = urllib.request.urlopen(req, timeout=180).read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == 3:
                raise RuntimeError(f"Fish Audio {e.code}: {e.read()[:300]!r}")
            time.sleep(15 * (intento + 1))
    mp3 = out.with_suffix(".mp3")
    mp3.write_bytes(data)
    trim_silence(mp3, out, pausa)
    mp3.unlink()


def trim_silence(src: Path, out: Path, pausa: float = 0.35) -> None:
    """Recorta silencio al inicio y al final, y acorta pausas internas largas a 0.35 s."""
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
          f"silenceremove=stop_periods=-1:stop_duration={pausa}:stop_threshold=-45dB")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af, "-ac", "1", "-ar", str(RATE), str(out)])


# Ajustes de pronunciación por voz. Piper necesitaba fonética ("esquils"); Fish es multilingüe y
# pronuncia bien los nombres en inglés escritos tal cual, pero lee mal siglas y extensiones.
PRONUNCIACION = {
    "fish": [("esquils", "skills"), ("Open Code", "OpenCode"), ("Open Spec", "OpenSpec"),
             ("Context seven", "Context7"), ("opsx ", "o pe ese equis "), ("punto md", "punto eme de"),
             ("kb creator", "ka be creator"),
             # Backend/SQLModel. El par es (lo que dice el GUION, lo que se manda al
             # TTS). Cada regla se eligio generando y transcribiendo con Whisper, y el
             # .srt no se ve afectado: usa seg["texto"], no esto. 2026-09-23, voz argentina.
             ("database", "deitabeis"),   # escrito tal cual se oye "la tabez" / "DadaVez"
             ("schemas", "esquemas"),     # escrito tal cual se oye "escamas"
             ("ORM", "O-R-M"),            # "sin ORM" se oye "si no ERM"; con guiones sale limpio
             ("back populates", "back populeits"),  # se oye "back populettes"
             ("JSON", "yeison"),          # se oye "Jason"
             ("FastAPI", "fast a pi ai"), # se oye "FASTP" / "fast a pie"
             ("SQLite", "esecuelait"),    # se oye "esquilite" / "esqueletes"
             ("sqlite", "esecuelait")],
             # NO hay regla para "table". Aislada en una frase inventada se oia
             # "tabla" y "teibol" la arreglaba, pero en el texto REAL del guion las
             # dos versiones dicen "table" bien: la regla no aportaba y sumaba riesgo
             # (replace() no respeta limites de palabra, y "table" vive dentro de
             # "establecido"). Probar las reglas con el texto real, no con ejemplos.
}


def adaptar(text: str, voz: str) -> str:
    reglas = PRONUNCIACION["fish"] if voz in FISH_LENTAS else PRONUNCIACION.get(voz, [])
    for viejo, nuevo in reglas:
        text = text.replace(viejo, nuevo)
    return text


def voice_wav(vid: str, voz: str, idx: int, text: str) -> Path:
    text = adaptar(text, voz)
    base = ROOT / "videos" / vid / voz
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{idx:02d}.wav"
    if voz == "daniela":
        stamp = out.with_suffix(".txt")
        if not out.exists() or not stamp.exists() or stamp.read_text() != text:
            tts_daniela(text, out)
            stamp.write_text(text)
    elif voz == "elevenlabs":
        stamp = out.with_suffix(".txt")
        if not out.exists() or not stamp.exists() or stamp.read_text() != text:
            tts_elevenlabs(text, out)
            stamp.write_text(text)
    elif voz == "fish" or voz in FISH_LENTAS:
        stamp = out.with_suffix(".txt")
        if not out.exists() or not stamp.exists() or stamp.read_text() != text:
            if voz in FISH_LENTAS:
                tts_fish(text, out, speed=FISH_SPEED.get(voz, 0.8),
                         pausa=FISH_PAUSA.get(voz, 0.8), voice=FISH_LENTAS[voz])
            else:
                tts_fish(text, out)
            stamp.write_text(text)
    elif voz == "juani":
        if not out.exists():
            raise FileNotFoundError(f"falta {out}: generalo afuera (editar.py exportar {vid}) y copialo acá")
    else:
        raise ValueError(voz)
    return out


def build_segment(vid: str, raw: Path, seg: dict, slot: float, out: Path, voz_palabras=None) -> None:
    """Arma el tramo de video de un segmento y lo deja durando exactamente `slot`.

    El segmento puede traer su propio "raw": un tutorial largo se graba por
    capitulos, y con un solo crudo global regrabar un capitulo obliga a rehacer
    la toma entera. Con `raw` por segmento se regraba solo ese archivo.
    """
    fps = 30
    if es_escena(seg):
        import escena
        spec = spec_de_escena(seg, slot, voz_palabras or [])
        brand = escena.cargar_brand(ROOT / "brand.json" if (ROOT / "brand.json").exists() else None)
        escena.render(escena.ruta_plantilla(spec["tipo"]), spec, out, brand=brand, fps=fps)
        return
    if seg.get("raw"):
        raw = ROOT / seg["raw"]
    if seg.get("tipo") == "titulo":
        vf = (
            f"drawtext=fontfile={FONT_BOLD}:text='{esc(seg['titulo'])}':fontcolor=white:fontsize=88:x=(w-tw)/2:y=(h/2)-110,"
            f"drawtext=fontfile={FONT}:text='{esc(seg.get('subtitulo', ''))}':fontcolor=0xB8C1EC:fontsize=44:x=(w-tw)/2:y=(h/2)+20"
        )
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x16161D:s=1920x1080:r={fps}:d={slot:.3f}",
             "-vf", encoder.vf(vf), *encoder.cv_args(crf=20, preset="veryfast"), str(out)])
        return
    tmp = out.with_suffix(".tmp.mp4")
    pre = "mpdecimate=hi=64*24:lo=64*8:frac=0.2," if seg.get("decimar", True) else ""

    # zoom: recorta una región y la amplía a pantalla completa. Sin esto, cuando la voz
    # dice "mirá esta línea" el alumno no sabe dónde mirar, que es el defecto que hunde
    # a los videos de código. Se declara en el guion como:
    #   "zoom": {"x": 280, "y": 400, "w": 900, "h": 300}
    z = seg.get("zoom")
    if z:
        # el recorte se hace ANTES de mpdecimate: al ampliar, los cambios chicos
        # (un cursor, una letra) pasan a ser grandes y mpdecimate ya no los descarta.
        #
        # El escalado ENCAJA la región adentro del lienzo, no fuerza el ancho. Forzando
        # el ancho, un recorte apenas más alto que 16:9 (1150x650 -> 1085 de alto) se
        # pasa por un pixel y pad muere con "Padded dimensions cannot be smaller than
        # input dimensions". Con force_original_aspect_ratio=decrease entra siempre,
        # sea la región más ancha o más alta que la pantalla.
        pre = (f"crop={z['w']}:{z['h']}:{z['x']}:{z['y']},"
               f"scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
               f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x16161D," + pre)

    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(seg["inicio"]), "-to", str(seg["fin"]), "-i", str(raw),
         "-vf", encoder.vf(f"{pre}setpts=N/{fps}/TB"), "-r", str(fps), "-an",
         *encoder.cv_args(crf=18, preset="ultrafast", pix_fmt=False), str(tmp)])
    d = duration(tmp)
    factor = d / slot
    if factor > 1.05:
        vf = f"setpts=PTS/{factor:.4f},fps={fps}"
        if factor >= 1.5:
            vf += (f",drawtext=fontfile={FONT_BOLD}:text='>> x{factor:.0f}':fontcolor=white:fontsize=38:"
                   f"box=1:boxcolor=0x000000AA:boxborderw=14:x=w-tw-40:y=h-th-40")
    else:
        vf = f"tpad=stop_mode=clone:stop_duration={max(slot - d, 0) + 0.2:.3f},fps={fps}"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-vf", encoder.vf(vf), "-t", f"{slot:.3f}",
         *encoder.cv_args(crf=20, preset="veryfast"), str(out)])
    tmp.unlink()


def es_escena(seg: dict) -> bool:
    return bool(seg.get("escena"))


def crudo_faltante(g: dict):
    """(índice, ruta) del primer segmento de pantalla cuyo crudo no existe, o None.

    Los títulos y las escenas no usan crudo: un guion hecho sólo de escenas no lo necesita.
    """
    raw = ROOT / g["raw"] if g.get("raw") else None
    for i, s in enumerate(g["segmentos"]):
        if s.get("tipo") == "titulo" or es_escena(s):
            continue
        r = ROOT / s["raw"] if s.get("raw") else raw
        if r is None or not r.exists():
            return i, r
    return None


def palabras_de_voz(wav: Path) -> list[dict]:
    """Tiempos por palabra del wav, cacheados en NN.palabras.json (se rehacen si la voz cambió).

    Se valida por el CONTENIDO del wav (sha256 en NN.palabras.sha256), no por la fecha:
    un `cp -p` o el unzip del export de Colab traen un wav nuevo con fecha vieja.
    """
    import hashlib
    import palabras
    cache, firma = wav.with_suffix(".palabras.json"), wav.with_suffix(".palabras.sha256")
    actual = hashlib.sha256(wav.read_bytes()).hexdigest()
    if cache.exists() and firma.exists() and firma.read_text() == actual:
        return json.loads(cache.read_text())
    out = palabras.transcribir(wav)
    cache.write_text(json.dumps(out, ensure_ascii=False))
    firma.write_text(actual)
    return out


def spec_de_escena(seg: dict, slot: float, voz_palabras: list[dict]) -> dict:
    """Spec listo para el motor: dura el slot y cada cue tiene su t dentro del slot.

    La voz arranca LEAD segundos después del inicio del slot, así que los tiempos de
    las palabras se corren LEAD. Una cue en segundos ya es relativa al slot.
    """
    import escena
    spec = seg["escena"]
    if not spec.get("tipo"):
        raise ValueError(f"la escena del segmento {seg.get('texto', '')[:40]!r} no dice su tipo "
                         "(diagrama, presentacion, datos)")
    corridas = [{**p, "inicio": p["inicio"] + LEAD, "fin": p["fin"] + LEAD} for p in voz_palabras]
    return escena.resolver_spec({**spec, "duracion": slot}, corridas)


def _cola(voz_name: str) -> float:
    """Margen después de la voz (NOTE 11): depende de si la voz es rápida
    (FISH_SPEED >= 1.0), de FISH_LENTAS, o ninguna de las dos (TAIL). Única fuente
    de esta cuenta: `preparar()` y el test de la decisión 2 (D3/FISH_LENTAS) la
    usan a través de esta función, no de un número copiado a mano."""
    return 0.6 if FISH_SPEED.get(voz_name, 0.8) >= 1.0 else (1.0 if voz_name in FISH_LENTAS else TAIL)


def preparar(vid: str, voz_name: str) -> list[tuple[dict, float, list | None]]:
    """Genera (o reusa) la voz de cada segmento y mide su slot: [(seg, slot, palabras)].

    Las palabras sólo se transcriben para los segmentos de escena, que las necesitan
    para resolver sus cues.
    """
    tramos = []
    for i, seg in enumerate(load(vid)["segmentos"]):
        wav = voice_wav(vid, voz_name, i, seg["texto"])
        voice = duration(wav)
        slot = round(max(seg.get("min", 0), voice + LEAD + _cola(voz_name)), 2)
        tramos.append((seg, slot, palabras_de_voz(wav) if es_escena(seg) else None))
        print(f"  seg {i:02d}: voz {voice:5.1f}s -> slot {slot:5.1f}s")
    return tramos


def escenas(vid: str, voz_name: str = "argentina") -> list[Path]:
    """Deja en videos/<vNN>/escenas/NN.json el spec resuelto de cada escena, SIN renderizar.

    Es el paso previo a la hoja de contacto: los slots y las cues ya son los del render.
    """
    out = ROOT / "videos" / vid / "escenas"
    out.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i, (seg, slot, pal) in enumerate(preparar(vid, voz_name)):
        if es_escena(seg):
            r = out / f"{i:02d}.json"
            # _voz/_segmento_hash (NOTE 2/3a, revisar): atan el spec a esta voz y a
            # este segmento del guion, para que `revisar` sepa si sigue valiendo.
            spec = {**spec_de_escena(seg, slot, pal), "_voz": voz_name, "_segmento_hash": _hash_segmento(seg)}
            r.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
            rutas.append(r)
    return rutas


def imagen(vid: str, voz_name: str = "argentina") -> None:
    encoder.preparar()  # aviso temprano: TUT_ENCODER=vaapi sin VAAPI no gasta en generar voces
    g = load(vid)
    raw = ROOT / g["raw"] if g.get("raw") else None
    # aviso temprano: un crudo que falta recien se nota a mitad del render
    falta = crudo_faltante(g)
    if falta:
        sys.exit(f"  ABORTADO: el segmento {falta[0]:02d} apunta a un crudo que no existe: {falta[1]}")
    work = ROOT / "videos" / vid
    (work / "seg").mkdir(parents=True, exist_ok=True)
    slots = []
    for i, (seg, slot, pal) in enumerate(preparar(vid, voz_name)):
        slots.append(slot)
        build_segment(vid, raw, seg, slot, work / "seg" / f"{i:02d}.mp4", pal)
    (work / f"slots-{voz_name}.json").write_text(json.dumps(slots))
    lst = work / "seg" / "lista.txt"
    lst.write_text("".join(f"file '{i:02d}.mp4'\n" for i in range(len(slots))))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(work / f"video-{voz_name}.mp4")])
    print(f"{vid}: video-{voz_name}.mp4 {duration(work / f'video-{voz_name}.mp4'):.1f}s")


def _factor_de_aceleracion(d: float, max_len: float) -> float:
    """Factor de `atempo` para que `d` entre en `max_len`, o 1.0 si no hace falta acelerar.

    N7 (QA 03/10/2026): ffmpeg 6.1.1 se cuelga (deadlock) no sólo con atempo=1.0000 exacto,
    sino con cualquier factor entre 1.0 y ~1.0003 (desde 1.0005 ya anda bien). Se trata como
    1.0 (sin filtro atempo) todo factor con |factor - 1| < 0.001: de sobra para cubrir el
    rango que cuelga, y a esa distancia de 1.0 la aceleración es inaudible.
    """
    tempo = d / max_len if d > max_len else 1.0
    return 1.0 if abs(tempo - 1.0) < 0.001 else tempo


def read_pcm(path: Path, max_len: float) -> bytes:
    """Lee un wav, lo normaliza a mono 22050 s16 y lo acelera si no entra en max_len.

    QA (03/10/2026): ffmpeg 6.1.1 se cuelga con `-af atempo=1.0000` para ciertas
    entradas (deadlock, no es un bug de esta skill). Factor 1.0 es exactamente
    el camino normal (la voz entra en el slot), así que no se arma ese filtro:
    no hay nada que acelerar.
    """
    norm = path.with_suffix(".norm.wav")
    d = duration(path)
    tempo = _factor_de_aceleracion(d, max_len)
    if tempo > 1.15:
        print(f"  AVISO {path.name}: la voz dura {d:.1f}s y el slot da {max_len:.1f}s (x{tempo:.2f})")
    af = [] if tempo == 1.0 else ["-af", f"atempo={tempo:.4f}"]
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), *af, "-ac", "1", "-ar", str(RATE),
         "-sample_fmt", "s16", str(norm)])
    with wave.open(str(norm)) as w:
        data = w.readframes(w.getnframes())
    norm.unlink()
    return data


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _normalizar_musica(musica_g):
    """Normaliza la clave "musica" de arriba del guion: {archivo,...} | false | ausente.

    N4 (QA 03/10/2026): HITO2.md documenta "musica" arriba como un objeto {archivo,...};
    "false" sólo está documentado adentro de un segmento. Elegido (y documentado acá):
    arriba, "false" se trata igual que ausente -"Sin música" es justamente el default de
    esa fila de la tabla del formato-, no es un error. Un objeto sin "archivo" sí lo es:
    aborta antes de generar nada (antes reventaba más adelante, después de escribir la voz).
    """
    if musica_g is False or musica_g is None:
        return None
    if not isinstance(musica_g, dict):
        sys.exit(f"ABORTADO: 'musica' tiene que ser un objeto {{archivo,...}} o false, no {musica_g!r}")
    if "archivo" not in musica_g:
        sys.exit("ABORTADO: falta la clave 'archivo' en 'musica'")
    return musica_g


def voz(vid: str, name: str) -> None:
    g = load(vid)
    work = ROOT / "videos" / vid
    slots = json.loads((work / f"slots-{name}.json").read_text())
    musica_g = _normalizar_musica(g.get("musica"))
    # R-2.6: archivo de música faltante o ilegible aborta ACÁ, antes de generar nada
    # (ni la voz): "al arrancar", no a mitad de render.
    m_archivo = musica.resolver_archivo(ROOT, musica_g["archivo"]) if musica_g else None

    pcm = bytearray()
    srt = []
    voces = []  # (inicio_rel, fin_rel) de la voz dentro de cada slot, o None si "musica": false
    t = 0.0
    for i, (seg, slot) in enumerate(zip(g["segmentos"], slots)):
        data = read_pcm(voice_wav(vid, name, i, seg["texto"]), slot - LEAD - 0.1)
        lead = b"\x00\x00" * int(LEAD * RATE)
        body = lead + data
        body += b"\x00\x00" * max(int(slot * RATE) - len(body) // 2, 0)
        pcm += body[: int(slot * RATE) * 2]
        srt.append(f"{i + 1}\n{srt_time(t + LEAD)} --> {srt_time(t + LEAD + len(data) / 2 / RATE)}\n{seg['texto']}\n")
        voces.append(None if seg.get("musica") is False else (LEAD, LEAD + len(data) / 2 / RATE))
        t += slot
    wav_out = work / f"voz-{name}.wav"
    with wave.open(str(wav_out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    (work / f"final-{name}.srt").write_text("\n".join(srt))
    final = work / f"final-{name}.mp4"
    # Manda el video, no la voz: cada tramo puede durar hasta un cuadro más que su slot,
    # y con -shortest el final perdía cuadros (685 -> 681, medido por QA). La voz se
    # completa con silencio (apad) hasta el largo del video.
    video = work / f"video-{name}.mp4"
    if musica_g is None:
        # sin "musica" en el guion: EXACTAMENTE el comando de antes del Hito 2 (G3).
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav_out), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5,apad",
             "-t", f"{duration(video):.6f}", str(final)])
    else:
        total = sum(slots)
        cruda = work / f"musica-cruda-{name}.wav"
        musica.preparar_pista(m_archivo, total, musica_g.get("fundido", 2.0), cruda)
        vts = musica.ventanas(slots, voces)
        musica_out = work / f"musica-{name}.wav"
        musica.construir_pista(wav_out, cruda, vts, musica_g.get("debajo_de_la_voz_lu", 18), musica_out)
        # N2 (QA 03/10/2026): loudnorm mide el TP ANTES del encode; el AAC de -c:a aac le
        # agrega TP de más (medido: hasta ~0.7dB con música picuda), así que pedirle
        # TP=-1.5 a loudnorm no alcanza para que el final MEDIDO cumpla R-2.3 (TP<=-1.5).
        # Apuntando más abajo (-2.0) queda margen para lo que el encoder agrega después.
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav_out), "-i", str(musica_out),
             "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest:normalize=0[amix];"
                                 f"[amix]loudnorm=I=-16:TP={TP_OBJETIVO_CON_MUSICA},apad[aout]",
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-t", f"{duration(video):.6f}", str(final)])
    print(f"{vid}: {final.name} {duration(final):.1f}s")


def exportar(vid: str) -> None:
    g = load(vid)
    out = ROOT / "videos" / vid / "textos.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{"archivo": f"{i:02d}.wav", "texto": s["texto"]} for i, s in enumerate(g["segmentos"])],
                              ensure_ascii=False, indent=1))
    print(out)


# --- revisar: el director (S5 del Hito 2, docs/explicador/HITO2.md) ---------------
#
# Mide lo que la sección "Director" de SKILL.md le pide al guion y al render. Sólo
# lee: nunca genera voces, specs ni videos. Si el artefacto que un chequeo necesita
# no está, lo dice (R-5.6) en vez de omitirlo en silencio.

# D1/D2 (SKILL.md → Director), Q10: N por defecto del tiempo sin cambio visual.
N_CAMBIO_VISUAL = 6.0


class RevisarError(Exception):
    """Error claro de `revisar` (B3a/B8): se informa sin traceback y sale != 0."""


FLAGS_REVISAR = ("--estricto",)
USO_REVISAR = "uso: editar.py revisar <vNN> [voz] [--estricto]"


def _estricto_falla(hallazgos: list[str], no_corrio: list[str]) -> bool:
    """B3c (DECISIÓN PENDIENTE DE JUANI, hoy no falla): política de si `--estricto`
    tiene que salir con 1 cuando algún chequeo no corrió (`no_corrio` no vacío),
    además de cuando hay `hallazgos`. Toda la política vive acá: cambiarla es
    una línea."""
    return bool(hallazgos)


# carpetas de trabajo que NO son el nombre de una voz (NOTE 3b)
_DIRS_RESERVADOS = {"escenas", "seg"}


def _voces_con_artefactos(work: Path) -> set[str]:
    """Nombres de voz para los que existe al menos un artefacto en `work`
    (video-<voz>.mp4, voz-<voz>.wav, slots-<voz>.json, o la carpeta <voz>/ de wavs
    importados — NOTE 3b, p.ej. "juani"). B3a: sirve para avisar de un nombre de
    voz tipeado mal cuando sí hay artefactos de otra voz."""
    voces = set()
    for ruta in work.glob("video-*.mp4"):
        voces.add(ruta.stem.removeprefix("video-"))
    for ruta in work.glob("voz-*.wav"):
        voces.add(ruta.stem.removeprefix("voz-"))
    for ruta in work.glob("slots-*.json"):
        voces.add(ruta.stem.removeprefix("slots-"))
    if work.is_dir():
        for ruta in work.iterdir():
            if ruta.is_dir() and ruta.name not in _DIRS_RESERVADOS:
                voces.add(ruta.name)
    return voces


def _freezes(video: Path, n: float) -> list[tuple[float, float]]:
    """D1: [(inicio, fin)] de los tramos de `video` sin cambio visual de MÁS de n
    segundos (B9: criterio estricto, igual que D2).

    B1: si el video queda congelado hasta el final, ffmpeg imprime `freeze_start`
    sin su `freeze_end` (nunca "descongela"); ese tramo cierra en la duración del
    video en vez de descartarse.
    """
    res = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(video), "-vf", f"freezedetect=n=-60dB:d={n:.3f}", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(m) for m in re.findall(r"freeze_start:\s*([\d.]+)", res.stderr)]
    fines = [float(m) for m in re.findall(r"freeze_end:\s*([\d.]+)", res.stderr)]
    if len(inicios) > len(fines):
        fines = fines + [duration(video)] * (len(inicios) - len(fines))
    return [(i, f) for i, f in zip(inicios, fines) if f - i > n]


def _huecos_escena(spec: dict, n: float) -> list[tuple[float, float]]:
    """D2: [(desde, hasta)] entre dos entradas de elementos (o la última y el final)
    con más de n segundos, calculado desde el spec YA RESUELTO (con "t"), sin render.

    B6: el hueco también se mide desde 0 hasta la primera entrada, así que una
    escena sin ninguna cue (sólo título) más larga que n es, entera, un hallazgo.
    B9: mismo criterio de borde que D1 (estrictamente MÁS de n, no "n o más").
    """
    import escena
    duracion = spec["duracion"]
    if not isinstance(duracion, (int, float)) or isinstance(duracion, bool):
        raise ValueError(f"'duracion' no es un número (vino {duracion!r})")
    tiempos = sorted(e["t"] for e in escena._con_cue(spec, []))
    puntos = [0.0, *tiempos, duracion]
    return [(a, b) for a, b in zip(puntos, puntos[1:]) if b - a > n]


def _silencios(wav: Path, d: float = 0.9) -> list[tuple[float, float]]:
    """D3: [(inicio, fin)] de los silencios de `wav` de >= d segundos."""
    res = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(wav), "-af", f"silencedetect=noise=-40dB:d={d:.3f}", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", res.stderr)]
    fines = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", res.stderr)]
    return list(zip(inicios, fines))


def _hash_segmento(seg: dict) -> str:
    """Identifica el CONTENIDO de un segmento de escena del guion (NOTE 2): si el
    segmento cambia, el hash cambia, sin importar qué pasó con los slots. `escenas()`
    lo guarda en el spec que escribe; `_specs_escena_vigentes` lo vuelve a calcular
    sobre el guion de HOY para comparar."""
    return hashlib.sha256(json.dumps(seg, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _specs_escena_vigentes(g: dict, voz_name: str, work: Path) -> tuple[list[Path], list[str]]:
    """B5/B5-bis: de los índices de escena del guion de HOY, cuáles specs en
    `escenas/` sirven para medir con la voz pedida.

    Un spec sirve si: existe, es JSON válido, se generó para ESTA voz (`_voz`,
    etiqueta que deja `escenas()`) y coincide con el segmento de HOY (`_segmento_hash`,
    NOTE 2: ya no depende de `slots-<voz>.json`, que además lo escribe `imagen`, no
    `escenas` — NOTE 4). Un índice de escena SIN spec en absoluto no se saltea en
    silencio (B5-bis): se informa igual, con el nombre que le faltó.

    Devuelve (vigentes, problemas): `problemas` son razones ya armadas con el
    nombre del archivo (o el que debería existir), para cada índice de escena que
    no se pudo usar.
    """
    escenas_dir = work / "escenas"
    indices = [i for i, seg in enumerate(g["segmentos"]) if es_escena(seg)]
    vigentes: list[Path] = []
    problemas: list[str] = []
    for i in indices:
        seg = g["segmentos"][i]
        nombre = f"{i:02d}.json"
        ruta = escenas_dir / nombre
        if not ruta.exists():
            problemas.append(f"{nombre}: falta el spec")
            continue
        try:
            spec = json.loads(ruta.read_text())
        except json.JSONDecodeError:
            problemas.append(f"{nombre}: JSON inválido")
            continue
        if spec.get("_voz") != voz_name:
            problemas.append(f"{nombre}: no corresponde a la voz {voz_name!r} "
                             f"(generado para {spec.get('_voz')!r})")
            continue
        if spec.get("_segmento_hash") != _hash_segmento(seg):
            problemas.append(f"{nombre}: desactualizado (el guion cambió)")
            continue
        vigentes.append(ruta)
    return vigentes, problemas


ROLES_VALIDOS = ("gancho", "analogia", "ejemplo", "repaso")


def _normalizar_rol(rol: str) -> str:
    """B7: minúsculas y sin tildes, para que 'Analogía' valga como 'analogia'."""
    sin_tildes = unicodedata.normalize("NFKD", rol.strip().lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def _hallazgos_roles(segmentos: list[dict]) -> list[str]:
    """D4: estructura de clase de profe (gancho, analogía, ejemplo, repaso).

    B7: un rol que no es ninguno de los válidos avisa con su nombre y la lista de
    válidos (y no cuenta como ninguno de ellos); uno que sólo difiere en mayúsculas
    o tildes se normaliza con un aviso aparte.
    """
    crudos = [s.get("rol") for s in segmentos]
    if not any(crudos):
        return ["el guion no declara roles"]
    hallazgos = []
    roles = []
    for crudo in crudos:
        if crudo is None:
            roles.append(None)
            continue
        normalizado = _normalizar_rol(crudo)
        if normalizado != crudo:
            hallazgos.append(f"rol {crudo!r} normalizado a {normalizado!r} (sin tildes/mayúsculas)")
        if normalizado not in ROLES_VALIDOS:
            hallazgos.append(f"rol desconocido {normalizado!r} (válidos: {', '.join(ROLES_VALIDOS)})")
            roles.append(None)
        else:
            roles.append(normalizado)
    if roles[0] != "gancho":
        hallazgos.append(f"el primer segmento no es 'gancho' (rol={roles[0]!r})")
    if roles[-1] != "repaso":
        hallazgos.append(f"el último segmento no es 'repaso' (rol={roles[-1]!r})")
    if "analogia" not in roles:
        hallazgos.append("no hay ningún segmento con rol 'analogia'")
    if "ejemplo" not in roles:
        hallazgos.append("no hay ningún segmento con rol 'ejemplo'")
    return hallazgos


# R-5.8: cada regla Dn de la sección "Director" (SKILL.md) tiene acá su chequeo de
# verdad. `revisar()` llama a cada uno A TRAVÉS de este registro (no por su nombre
# de función directamente): test_docs_director.py lo comprueba reemplazando cada
# entrada por un espía, así que no basta con que el ID aparezca en un comentario.
CHEQUEOS = {
    "D1": _freezes,
    "D2": _huecos_escena,
    "D3": _silencios,
    "D4": _hallazgos_roles,
}


def revisar(vid: str, voz_name: str = "argentina", n: float = N_CAMBIO_VISUAL) -> tuple[list[str], list[str]]:
    """(hallazgos, no_corrio) de revisar el guion y lo ya renderizado de `vid`/`voz_name`.

    `hallazgos` son los problemas que encontró un chequeo que sí pudo correr;
    `no_corrio` dice, de los que no pudieron, cuál y por qué (R-5.6).
    """
    g = load(vid)
    work = ROOT / "videos" / vid
    hallazgos: list[str] = []
    no_corrio: list[str] = []

    # B3a: si NINGÚN artefacto de `voz_name` existe pero sí hay de otra voz, es casi
    # siempre un nombre tipeado mal: error claro en vez de "no corrió" en silencio
    # para cada chequeo. Si no hay artefactos de NINGUNA voz (vNN recién creado),
    # sigue de largo: ahí no hay con qué comparar.
    voces = _voces_con_artefactos(work)
    if voces and voz_name not in voces:
        raise RevisarError(f"no hay ningún artefacto para la voz {voz_name!r} en {vid}; "
                           f"voces con artefactos: {', '.join(sorted(voces))}")

    video = work / f"video-{voz_name}.mp4"
    if video.exists():
        for inicio, fin in CHEQUEOS["D1"](video, n):
            hallazgos.append(f"tiempo muerto: {inicio:.1f}s–{fin:.1f}s sin cambio visual (> {n:.0f}s) en {video.name}")
    else:
        no_corrio.append(f"tiempo muerto: no corrió, falta {video} (correr 'editar.py imagen {vid} {voz_name}')")

    escenas_dir = work / "escenas"
    if any(es_escena(s) for s in g["segmentos"]):
        if not escenas_dir.exists():
            no_corrio.append(f"cambio visual en escenas: no corrió, faltan los specs resueltos en {escenas_dir} "
                             f"(correr 'editar.py escenas {vid} {voz_name}')")
        else:
            vigentes, problemas = _specs_escena_vigentes(g, voz_name, work)
            for ruta in vigentes:
                try:
                    spec = json.loads(ruta.read_text())
                    huecos = CHEQUEOS["D2"](spec, n)
                except (KeyError, ValueError) as e:
                    no_corrio.append(f"cambio visual en escenas: no corrió para {ruta.name}, "
                                     f"{e} (correr 'editar.py escenas {vid} {voz_name}')")
                    continue
                for desde, hasta in huecos:
                    hallazgos.append(f"{ruta.name}: {desde:.1f}s–{hasta:.1f}s sin elemento nuevo (> {n:.0f}s)")
            # B5-bis: cada problema (spec faltante, JSON inválido, de otra voz,
            # desactualizado) se informa, no se saltea en silencio.
            for problema in problemas:
                no_corrio.append(f"cambio visual en escenas: no corrió para {problema} "
                                 f"(correr 'editar.py escenas {vid} {voz_name}')")

    voz_wav = work / f"voz-{voz_name}.wav"
    if voz_wav.exists():
        for inicio, fin in CHEQUEOS["D3"](voz_wav, 0.9):
            hallazgos.append(f"silencio: {inicio:.1f}s–{fin:.1f}s en la voz (> 0.9s) en {voz_wav.name}")
    else:
        no_corrio.append(f"silencios: no corrió, falta {voz_wav} (correr 'editar.py voz {vid} {voz_name}')")

    hallazgos.extend(CHEQUEOS["D4"](g["segmentos"]))

    return hallazgos, no_corrio


def informe_revisar(vid: str, voz_name: str, hallazgos: list[str], no_corrio: list[str]) -> str:
    lineas = [f"director: {vid} ({voz_name})"]
    lineas += [f"  - {h}" for h in hallazgos] if hallazgos else ["  sin hallazgos"]
    if no_corrio:
        lineas.append("chequeos que no corrieron:")
        lineas += [f"  - {c}" for c in no_corrio]
    return "\n".join(lineas)


def _dispatch_revisar(args: list[str]) -> int:
    """CLI de 'revisar' (B8): separa flags de posicionales sin importar el orden
    (B8: '--estricto' puede ir antes del vNN) y da mensajes claros con el uso en
    vez de traceback ante vNN faltante, sin argumentos, o un flag desconocido
    (B3b: no se ignora en silencio)."""
    flags = [a for a in args if a.startswith("--")]
    desconocidos = [f for f in flags if f not in FLAGS_REVISAR]
    if desconocidos:
        print(f"editar.py revisar: flag desconocido {desconocidos[0]!r} (válidos: {', '.join(FLAGS_REVISAR)})",
              file=sys.stderr)
        print(USO_REVISAR, file=sys.stderr)
        return 2
    posicionales = [a for a in args if not a.startswith("--")]
    if not posicionales:
        print("editar.py revisar: falta <vNN>", file=sys.stderr)
        print(USO_REVISAR, file=sys.stderr)
        return 2
    vid = posicionales[0]
    voz_name = posicionales[1] if len(posicionales) > 1 else "argentina"
    estricto = "--estricto" in flags
    try:
        hallazgos, no_corrio = revisar(vid, voz_name)
    except FileNotFoundError:
        print(f"editar.py revisar: no existe {vid} (falta guion/{vid}.json)", file=sys.stderr)
        return 2
    except RevisarError as e:
        print(f"editar.py revisar: {e}", file=sys.stderr)
        return 2
    print(informe_revisar(vid, voz_name, hallazgos, no_corrio))
    return 1 if estricto and _estricto_falla(hallazgos, no_corrio) else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    accion = sys.argv[1]
    if accion == "revisar":
        sys.exit(_dispatch_revisar(sys.argv[2:]))
    vid = sys.argv[2]
    if accion == "imagen":
        imagen(vid, sys.argv[3] if len(sys.argv) > 3 else "argentina")
    elif accion == "voz":
        voz(vid, sys.argv[3])
    elif accion == "exportar":
        exportar(vid)
    elif accion == "escenas":
        rutas = escenas(vid, sys.argv[3] if len(sys.argv) > 3 else "argentina")
        if not rutas:
            print(f"{vid}: el guion no tiene escenas: no hay nada que revisar antes del render")
        else:   # ruta absoluta: el comando se copia y se corre desde la raíz del tutorial
            print(f"hoja de contacto: uv run --with playwright python {Path(__file__).resolve().parent / 'escena.py'} contacto "
                  + " ".join(str(r) for r in rutas) + f" -o {ROOT / 'videos' / vid / 'contacto.png'}")
    else:
        sys.exit(__doc__)

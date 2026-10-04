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
import json
import os
import re
import subprocess
import sys
import threading
import time
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
# QA 04/10/2026 (BLOCKING ronda 3): el TP que se le pide a loudnorm en SUS DOS pasadas (no
# el objetivo final): deliberadamente laxo, así no es loudnorm el que frena la ganancia
# antes de llegar al integrado (ver musica.normalizar_dos_pasadas). El TP real queda
# garantizado por el limitador de TRUE PEAK aparte, apuntando a TP_OBJETIVO_CON_MUSICA.
MARGEN_TP_LOUDNORM = -0.5
# -ar explícito en la salida con música: sin esto, el sample rate que loudnorm usa
# internamente para sobremuestrear (al medir TP) se cuela a la salida (medido: 96000Hz).
SR_SALIDA_CON_MUSICA = 48000


def _timeout_default() -> float:
    return float(os.environ.get("TUT_FFMPEG_TIMEOUT", "120"))


def run(cmd: list[str], timeout: float | None = None, devolver_stderr: bool = False):
    """Corre `cmd` y devuelve stdout; falla (RuntimeError) si el proceso no termina bien.

    QA 04/10/2026 (NOTE, ronda 3): `devolver_stderr=True` devuelve `(stdout, stderr)` en
    vez de sólo `stdout` (default `False`, igual que antes para todo el código existente).
    Hace falta para que musica.py pueda pasar TODOS sus subprocess por este vigía: varios
    de sus filtros (ebur128, loudnorm) escriben el resultado en stderr aun cuando el
    proceso termina bien, y antes de esto no había forma de leerlo pasando por `run()`.

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

    # B2 (QA 04/10/2026): errors="replace" -sin esto, un byte que no es UTF-8 válido en
    # stderr/stdout mata el hilo lector (UnicodeDecodeError silencioso) y el error real
    # que ese proceso iba a reportar se pierde sin dejar causa.
    proc = subprocess.Popen(cmd_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            errors="replace")
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
    if devolver_stderr:
        return "".join(salida["out"]), "".join(salida["err"])
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


def preparar(vid: str, voz_name: str) -> list[tuple[dict, float, list | None]]:
    """Genera (o reusa) la voz de cada segmento y mide su slot: [(seg, slot, palabras)].

    Las palabras sólo se transcriben para los segmentos de escena, que las necesitan
    para resolver sus cues.
    """
    tramos = []
    for i, seg in enumerate(load(vid)["segmentos"]):
        wav = voice_wav(vid, voz_name, i, seg["texto"])
        voice = duration(wav)
        cola = 0.6 if FISH_SPEED.get(voz_name, 0.8) >= 1.0 else (1.0 if voz_name in FISH_LENTAS else TAIL)
        slot = round(max(seg.get("min", 0), voice + LEAD + cola), 2)
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
            r.write_text(json.dumps(spec_de_escena(seg, slot, pal), ensure_ascii=False, indent=1))
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
        # QA 04/10/2026 (decisión del orquestador, ronda 3): el mismo camino de dos pasadas
        # + limitador de TP que con música, también sin ella -antes, loudnorm de una pasada
        # normalizaba por el contenido CON voz, y un slot largo con muy poca voz medía
        # I=-10.3 (voz 0.5s en un slot de 8s): muy por arriba de -16±1. Esto cambia el
        # AUDIO a propósito respecto de antes del Hito 2 (no el video: G3 pasa a ser sólo
        # framemd5, ver tests/fixtures/s0/ y su docstring).
        acotada = work / f"voz-acotada-{name}.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_out), "-af", "apad",
             "-t", f"{duration(video):.6f}", str(acotada)])
        normalizada = work / f"normalizada-{name}.wav"
        musica.normalizar_dos_pasadas(acotada, normalizada, objetivo_i=-16.0,
                                       margen_tp=MARGEN_TP_LOUDNORM,
                                       limite_tp_final=TP_OBJETIVO_CON_MUSICA,
                                       sr=SR_SALIDA_CON_MUSICA)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(normalizada),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-ar", str(SR_SALIDA_CON_MUSICA), "-t", f"{duration(video):.6f}", str(final)])
    else:
        total = sum(slots)
        cruda = work / f"musica-cruda-{name}.wav"
        musica.preparar_pista(m_archivo, total, musica_g.get("fundido", 2.0), cruda)
        vts = musica.ventanas(slots, voces)
        musica_out = work / f"musica-{name}.wav"
        musica.construir_pista(wav_out, cruda, vts, musica_g.get("debajo_de_la_voz_lu", 18), musica_out)
        # QA 04/10/2026 (BLOCKING ronda 3, R-2.3): loudnorm de UNA pasada no llega al
        # integrado cuando el TP restringe la ganancia (medido: I entre -17.1 y -20.2
        # según la música). Se mezcla primero sin loudnorm, y se normaliza con
        # musica.normalizar_dos_pasadas (dos pasadas + limitador de TRUE PEAK aparte),
        # apuntando bien abajo del -1.5 de R-2.3 para que el final MEDIDO (post-encode
        # AAC, que agrega TP de más) lo siga cumpliendo.
        mezcla = work / f"mezcla-{name}.wav"
        # "apad" sin límite genera silencio INDEFINIDAMENTE (QA 04/10/2026: sin el "-t" de
        # abajo, este wav intermedio crece sin fin hasta llenar el disco): acá se trunca
        # a la misma duración que el mux final de más abajo.
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_out), "-i", str(musica_out),
             "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,apad[aout]",
             "-map", "[aout]", "-t", f"{duration(video):.6f}", str(mezcla)])
        normalizada = work / f"normalizada-{name}.wav"
        musica.normalizar_dos_pasadas(mezcla, normalizada, objetivo_i=-16.0,
                                       margen_tp=MARGEN_TP_LOUDNORM,
                                       limite_tp_final=TP_OBJETIVO_CON_MUSICA,
                                       sr=SR_SALIDA_CON_MUSICA)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(normalizada),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-ar", str(SR_SALIDA_CON_MUSICA), "-t", f"{duration(video):.6f}", str(final)])
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


def _freezes(video: Path, n: float) -> list[tuple[float, float]]:
    """D1: [(inicio, fin)] de los tramos de `video` sin cambio visual de >= n segundos."""
    res = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(video), "-vf", f"freezedetect=n=-60dB:d={n:.3f}", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(m) for m in re.findall(r"freeze_start:\s*([\d.]+)", res.stderr)]
    fines = [float(m) for m in re.findall(r"freeze_end:\s*([\d.]+)", res.stderr)]
    return list(zip(inicios, fines))


def _huecos_escena(spec: dict, n: float) -> list[tuple[float, float]]:
    """D2: [(desde, hasta)] entre dos entradas de elementos (o la última y el final)
    con más de n segundos, calculado desde el spec YA RESUELTO (con "t"), sin render."""
    import escena
    tiempos = sorted(e["t"] for e in escena._con_cue(spec, []))
    puntos = [*tiempos, spec["duracion"]]
    return [(a, b) for a, b in zip(puntos, puntos[1:]) if b - a > n]


def _silencios(wav: Path, d: float = 0.9) -> list[tuple[float, float]]:
    """D3: [(inicio, fin)] de los silencios de `wav` de >= d segundos."""
    res = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(wav), "-af", f"silencedetect=noise=-40dB:d={d:.3f}", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", res.stderr)]
    fines = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", res.stderr)]
    return list(zip(inicios, fines))


def _hallazgos_roles(segmentos: list[dict]) -> list[str]:
    """D4: estructura de clase de profe (gancho, analogía, ejemplo, repaso)."""
    roles = [s.get("rol") for s in segmentos]
    if not any(roles):
        return ["el guion no declara roles"]
    hallazgos = []
    if roles[0] != "gancho":
        hallazgos.append(f"el primer segmento no es 'gancho' (rol={roles[0]!r})")
    if roles[-1] != "repaso":
        hallazgos.append(f"el último segmento no es 'repaso' (rol={roles[-1]!r})")
    if "analogia" not in roles:
        hallazgos.append("no hay ningún segmento con rol 'analogia'")
    if "ejemplo" not in roles:
        hallazgos.append("no hay ningún segmento con rol 'ejemplo'")
    return hallazgos


def revisar(vid: str, voz_name: str = "argentina", n: float = N_CAMBIO_VISUAL) -> tuple[list[str], list[str]]:
    """(hallazgos, no_corrio) de revisar el guion y lo ya renderizado de `vid`/`voz_name`.

    `hallazgos` son los problemas que encontró un chequeo que sí pudo correr;
    `no_corrio` dice, de los que no pudieron, cuál y por qué (R-5.6).
    """
    g = load(vid)
    work = ROOT / "videos" / vid
    hallazgos: list[str] = []
    no_corrio: list[str] = []

    video = work / f"video-{voz_name}.mp4"
    if video.exists():
        for inicio, fin in _freezes(video, n):
            hallazgos.append(f"tiempo muerto: {inicio:.1f}s–{fin:.1f}s sin cambio visual (> {n:.0f}s) en {video.name}")
    else:
        no_corrio.append(f"tiempo muerto: no corrió, falta {video} (correr 'editar.py imagen {vid} {voz_name}')")

    escenas_dir = work / "escenas"
    specs = sorted(escenas_dir.glob("*.json")) if escenas_dir.exists() else []
    if specs:
        for ruta in specs:
            spec = json.loads(ruta.read_text())
            for desde, hasta in _huecos_escena(spec, n):
                hallazgos.append(f"{ruta.name}: {desde:.1f}s–{hasta:.1f}s sin elemento nuevo (> {n:.0f}s)")
    elif any(es_escena(s) for s in g["segmentos"]):
        no_corrio.append(f"cambio visual en escenas: no corrió, faltan los specs resueltos en {escenas_dir} "
                         f"(correr 'editar.py escenas {vid} {voz_name}')")

    voz_wav = work / f"voz-{voz_name}.wav"
    if voz_wav.exists():
        for inicio, fin in _silencios(voz_wav, 0.9):
            hallazgos.append(f"silencio: {inicio:.1f}s–{fin:.1f}s en la voz (> 0.9s) en {voz_wav.name}")
    else:
        no_corrio.append(f"silencios: no corrió, falta {voz_wav} (correr 'editar.py voz {vid} {voz_name}')")

    hallazgos.extend(_hallazgos_roles(g["segmentos"]))

    return hallazgos, no_corrio


def informe_revisar(vid: str, voz_name: str, hallazgos: list[str], no_corrio: list[str]) -> str:
    lineas = [f"director: {vid} ({voz_name})"]
    lineas += [f"  - {h}" for h in hallazgos] if hallazgos else ["  sin hallazgos"]
    if no_corrio:
        lineas.append("chequeos que no corrieron:")
        lineas += [f"  - {c}" for c in no_corrio]
    return "\n".join(lineas)


if __name__ == "__main__":
    accion, vid = sys.argv[1], sys.argv[2]
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
    elif accion == "revisar":
        estricto = "--estricto" in sys.argv
        posicionales = [a for a in sys.argv[3:] if not a.startswith("--")]
        voz_name = posicionales[0] if posicionales else "argentina"
        hallazgos, no_corrio = revisar(vid, voz_name)
        print(informe_revisar(vid, voz_name, hallazgos, no_corrio))
        if estricto and hallazgos:
            sys.exit(1)
    else:
        sys.exit(__doc__)

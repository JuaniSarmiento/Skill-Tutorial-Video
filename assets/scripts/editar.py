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
voces: argentina (PRINCIPAL: Fish, femenina argentina, speed 0.80, la mas expresiva medida) | joven (Fish, "Narrador Joven argentino") | profe (Fish, Profesora Argentina, la mas plana) | daniela (Piper local) | juani (wavs importados en videos/<vNN>/juani/NN.wav) | elevenlabs (API, key en ~/.config/elevenlabs/api_key) | fish (Fish Audio, Profesora Argentina, key en ~/.config/fish/api_key)
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(os.environ.get("TUT_ROOT", os.getcwd()))
PIPER_MODEL = Path.home() / ".local/share/piper-voices/es_AR-daniela-high.onnx"
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
RATE = 22050
LEAD = 0.3  # silencio antes de que arranque la voz en cada slot
TAIL = 0.5  # margen después de la voz


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló: {' '.join(cmd)}\n{res.stderr[-2000:]}")
    return res.stdout


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
             ("kb creator", "ka be creator")],
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


def build_segment(vid: str, raw: Path, seg: dict, slot: float, out: Path) -> None:
    """Arma el tramo de video de un segmento y lo deja durando exactamente `slot`.

    El segmento puede traer su propio "raw": un tutorial largo se graba por
    capitulos, y con un solo crudo global regrabar un capitulo obliga a rehacer
    la toma entera. Con `raw` por segmento se regraba solo ese archivo.
    """
    fps = 30
    if seg.get("raw"):
        raw = ROOT / seg["raw"]
    if seg.get("tipo") == "titulo":
        vf = (
            f"drawtext=fontfile={FONT_BOLD}:text='{esc(seg['titulo'])}':fontcolor=white:fontsize=88:x=(w-tw)/2:y=(h/2)-110,"
            f"drawtext=fontfile={FONT}:text='{esc(seg.get('subtitulo', ''))}':fontcolor=0xB8C1EC:fontsize=44:x=(w-tw)/2:y=(h/2)+20"
        )
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x16161D:s=1920x1080:r={fps}:d={slot:.3f}",
             "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)])
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
         "-vf", f"{pre}setpts=N/{fps}/TB", "-r", str(fps), "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(tmp)])
    d = duration(tmp)
    factor = d / slot
    if factor > 1.05:
        vf = f"setpts=PTS/{factor:.4f},fps={fps}"
        if factor >= 1.5:
            vf += (f",drawtext=fontfile={FONT_BOLD}:text='>> x{factor:.0f}':fontcolor=white:fontsize=38:"
                   f"box=1:boxcolor=0x000000AA:boxborderw=14:x=w-tw-40:y=h-th-40")
    else:
        vf = f"tpad=stop_mode=clone:stop_duration={max(slot - d, 0) + 0.2:.3f},fps={fps}"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-vf", vf, "-t", f"{slot:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)])
    tmp.unlink()


def imagen(vid: str, voz_name: str = "argentina") -> None:
    g = load(vid)
    raw = ROOT / g["raw"] if g.get("raw") else None
    # aviso temprano: un crudo que falta recien se nota a mitad del render
    for i, s in enumerate(g["segmentos"]):
        if s.get("tipo") == "titulo":
            continue
        r = ROOT / s["raw"] if s.get("raw") else raw
        if r is None or not r.exists():
            sys.exit(f"  ABORTADO: el segmento {i:02d} apunta a un crudo que no existe: {r}")
    work = ROOT / "videos" / vid
    (work / "seg").mkdir(parents=True, exist_ok=True)
    slots = []
    for i, seg in enumerate(g["segmentos"]):
        wav = voice_wav(vid, voz_name, i, seg["texto"])
        voice = duration(wav)
        cola = 0.6 if FISH_SPEED.get(voz_name, 0.8) >= 1.0 else (1.0 if voz_name in FISH_LENTAS else TAIL)
        slot = round(max(seg.get("min", 0), voice + LEAD + cola), 2)
        slots.append(slot)
        build_segment(vid, raw, seg, slot, work / "seg" / f"{i:02d}.mp4")
        print(f"  seg {i:02d}: voz {voice:5.1f}s -> slot {slot:5.1f}s")
    (work / f"slots-{voz_name}.json").write_text(json.dumps(slots))
    lst = work / "seg" / "lista.txt"
    lst.write_text("".join(f"file '{i:02d}.mp4'\n" for i in range(len(slots))))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(work / f"video-{voz_name}.mp4")])
    print(f"{vid}: video-{voz_name}.mp4 {duration(work / f'video-{voz_name}.mp4'):.1f}s")


def read_pcm(path: Path, max_len: float) -> bytes:
    """Lee un wav, lo normaliza a mono 22050 s16 y lo acelera si no entra en max_len."""
    norm = path.with_suffix(".norm.wav")
    d = duration(path)
    tempo = d / max_len if d > max_len else 1.0
    if tempo > 1.15:
        print(f"  AVISO {path.name}: la voz dura {d:.1f}s y el slot da {max_len:.1f}s (x{tempo:.2f})")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af", f"atempo={tempo:.4f}", "-ac", "1", "-ar", str(RATE),
         "-sample_fmt", "s16", str(norm)])
    with wave.open(str(norm)) as w:
        data = w.readframes(w.getnframes())
    norm.unlink()
    return data


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def voz(vid: str, name: str) -> None:
    g = load(vid)
    work = ROOT / "videos" / vid
    slots = json.loads((work / f"slots-{name}.json").read_text())
    pcm = bytearray()
    srt = []
    t = 0.0
    for i, (seg, slot) in enumerate(zip(g["segmentos"], slots)):
        data = read_pcm(voice_wav(vid, name, i, seg["texto"]), slot - LEAD - 0.1)
        lead = b"\x00\x00" * int(LEAD * RATE)
        body = lead + data
        body += b"\x00\x00" * max(int(slot * RATE) - len(body) // 2, 0)
        pcm += body[: int(slot * RATE) * 2]
        srt.append(f"{i + 1}\n{srt_time(t + LEAD)} --> {srt_time(t + LEAD + len(data) / 2 / RATE)}\n{seg['texto']}\n")
        t += slot
    wav_out = work / f"voz-{name}.wav"
    with wave.open(str(wav_out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    (work / f"final-{name}.srt").write_text("\n".join(srt))
    final = work / f"final-{name}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / f"video-{name}.mp4"), "-i", str(wav_out), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5", "-shortest", str(final)])
    print(f"{vid}: {final.name} {duration(final):.1f}s")


def exportar(vid: str) -> None:
    g = load(vid)
    out = ROOT / "videos" / vid / "textos.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{"archivo": f"{i:02d}.wav", "texto": s["texto"]} for i, s in enumerate(g["segmentos"])],
                              ensure_ascii=False, indent=1))
    print(out)


if __name__ == "__main__":
    accion, vid = sys.argv[1], sys.argv[2]
    if accion == "imagen":
        imagen(vid, sys.argv[3] if len(sys.argv) > 3 else "argentina")
    elif accion == "voz":
        voz(vid, sys.argv[3])
    elif accion == "exportar":
        exportar(vid)
    else:
        sys.exit(__doc__)

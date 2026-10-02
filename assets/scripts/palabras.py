#!/usr/bin/env python3
"""Tiempos por palabra de una voz ya generada, y resolución de cues.

Una escena hace entrar cada elemento EN LA PALABRA QUE LO NOMBRA. Para eso hace
falta saber en qué segundo se dice cada palabra, y eso sale de transcribir la
voz con faster-whisper (`word_timestamps=True`). Se transcribe el audio real y
no se le piden los tiempos al proveedor de TTS: así funciona con cualquier voz
(decisión del PLAN, docs/explicador/PLAN.md).

Una "cue" se escribe de tres formas:
  "base de datos"                 la frase, tal cual se dice
  "cuando dice 'base de datos'"   la misma frase, en la forma larga del guion
  1.5                             un tiempo en segundos, para cuando no hay voz

uso: uv run --with faster-whisper --with "av<19" python palabras.py <audio> [salida.json] [--modelo base]
"""
import json
import re
import unicodedata
from pathlib import Path

# Whisper escribe en dígitos lo que la voz dice en palabras ("2 décadas"). Se
# normalizan los dos lados igual, así que "una" pasa a "1" también como artículo.
NUMEROS = dict(zip(
    "cero uno una un dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce "
    "quince veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa cien".split(),
    "0 1 1 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 20 30 40 50 60 70 80 90 100".split()))
# Whisper oye mal alguna letra ("tembrano" por "temprano", "Hablamos" por "Hagamos").
# Cuánto se tolera depende de si la cue tiene un ANCLA: otra palabra suya de ANCLA
# letras o más que se oyó exacta. "la"/"el" no anclan: "la tasa" no es "la casa".
#   sin ancla: palabra larga (LARGA+ letras) 1 error, palabra corta ninguno
#   con ancla: palabra larga hasta 2 errores, palabra corta 1
# Un número tiene que estar tal cual ("10"/"100" son otro número), y una cue de una
# sola palabra corta también ("sí"/"sin", "banco"/"blanco"): no tiene con qué anclar.
LARGA = 6
ANCLA = 4

MODELO = "base"  # "small" es mejor pero no entra en 1 GB de RAM libre junto a Chrome


def transcribir(audio, modelo=None) -> list[dict]:
    """Audio -> [{palabra, inicio, fin}] con los tiempos redondeados a ms."""
    if modelo is None or isinstance(modelo, str):
        from faster_whisper import WhisperModel
        modelo = WhisperModel(modelo or MODELO, device="cpu", compute_type="int8")
    segmentos, _ = modelo.transcribe(str(audio), language="es", word_timestamps=True)
    return [{"palabra": w.word.strip(), "inicio": round(w.start, 3), "fin": round(w.end, 3)}
            for s in segmentos for w in s.words]


def _sin_tilde(c: str) -> str:
    # la ñ es otra letra, no una n con tilde: "año" no es "ano"
    if c == "ñ":
        return c
    return "".join(x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn")


def _norm(texto: str) -> str:
    sin_tildes = "".join(_sin_tilde(c) for c in unicodedata.normalize("NFC", texto.lower()))
    palabras = re.sub(r"[^a-z0-9ñ]+", " ", sin_tildes).split()
    return " ".join(w for w, _ in _juntar_miles((NUMEROS.get(w, w), None) for w in palabras))


def _juntar_miles(pares) -> list[tuple]:
    """"17 .000", "17.000" y "17000" son el mismo número: Whisper escribe los miles
    con un punto (y a veces un espacio), que al normalizar parte el número en dos.
    Recibe (palabra, origen) y cada número unido conserva el origen de su primera parte."""
    salida = []
    for w, origen in pares:
        if salida and salida[-1][0].isdigit() and w.isdigit() and len(w) == 3:
            salida[-1] = (salida[-1][0] + w, salida[-1][1])
        else:
            salida.append((w, origen))
    return salida


def _distancia(a: str, b: str) -> int:
    """Levenshtein: cuántas letras hay que agregar, sacar o cambiar."""
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        previa, fila[0] = fila[0], i
        for j, cb in enumerate(b, 1):
            previa, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, previa + (ca != cb))
    return fila[-1]


def _es_numero(w: str) -> bool:
    return any(c.isdigit() for c in w)


def _tolera(palabra: str, ancla: bool) -> int:
    if _es_numero(palabra):
        return 0
    if len(palabra) >= LARGA:
        return 2 if ancla else 1
    return 1 if ancla else 0


def _ancla(palabra: str, errores: int) -> bool:
    return errores == 0 and len(palabra) >= ANCLA and not _es_numero(palabra)


def _errores(frase: list[str], oidas: list[str]):
    """Errores entre la frase de la cue y un tramo oído, o None si no es la misma frase."""
    if len(frase) == len(oidas):
        d = [_distancia(f, o) for f, o in zip(frase, oidas)]
        ancla = any(_ancla(f, x) for f, x in zip(frase, d))
        return sum(d) if all(x <= _tolera(f, ancla) for x, f in zip(d, frase)) else None
    # Whisper pegó o partió palabras ("se suma" -> "esuma"): se busca cómo partir lo
    # oído en las palabras de la cue, con la misma regla de ancla palabra por palabra.
    # Los números tienen que estar tal cual, como palabra oída.
    if any(_es_numero(f) and f not in oidas for f in frase):
        return None
    return _partir("".join(oidas), frase)


def _partir(junta: str, frase: list[str]):
    """Menos errores al partir `junta` en las palabras de `frase`, o None si no se puede."""
    mejor = None
    for con_ancla in (False, True):
        estados = {(0, False): 0}   # (letras consumidas, ¿ya hubo ancla?) -> errores
        for f in frase:
            nuevos = {}
            for (pos, hubo), e in estados.items():
                for largo in range(max(0, len(f) - 2), len(f) + 3):
                    if pos + largo > len(junta):
                        break
                    x = _distancia(f, junta[pos:pos + largo])
                    if x > _tolera(f, con_ancla):
                        continue
                    clave = (pos + largo, hubo or _ancla(f, x))
                    nuevos[clave] = min(nuevos.get(clave, x + e), x + e)
            estados = nuevos
        for (pos, hubo), e in estados.items():
            if pos == len(junta) and (hubo or not con_ancla) and (mejor is None or e < mejor):
                mejor = e
    return mejor


def _frase(cue: str) -> list[str]:
    m = re.search(r"cuando dice\s+['\"‘“](.+?)['\"’”]", cue)
    return _norm(m.group(1) if m else cue).split()


def _buscar(palabras: list[dict], cue: str, desde_idx: int) -> int:
    """Índice de la primera palabra de `cue` a partir de desde_idx; ValueError si no está.

    Se queda con el tramo con menos errores (con 1 palabra de más o de menos,
    porque Whisper a veces pega dos: "se suma" -> "esuma"); a igual cantidad, el
    primero. La frase exacta tiene 0 errores, así que siempre le gana a una parecida.
    Ver LARGA para qué error se tolera y cuál no.
    """
    frase = _frase(cue)
    if not frase:
        raise ValueError(f"la cue {cue!r} está vacía: no nombra ninguna palabra")
    # lo oído, normalizado palabra por palabra, recordando de qué palabra salió cada
    # una: "17" y ".000" son dos palabras de Whisper y un solo número
    pares = _juntar_miles((w, i) for i, p in enumerate(palabras) for w in _norm(p["palabra"]).split())
    oidas, origen = [w for w, _ in pares], [i for _, i in pares]
    n = len(frase)
    mejor, idx = None, None
    for j in range(len(oidas)):
        if origen[j] < desde_idx:
            continue
        for k in (n - 1, n, n + 1):
            if k >= 1 and j + k <= len(oidas):
                e = _errores(frase, oidas[j:j + k])
                if e is not None and (mejor is None or e < mejor):
                    mejor, idx = e, origen[j]
    if idx is not None:
        return idx
    dicho = " ".join(p["palabra"] for p in palabras)
    raise ValueError(f"la cue {cue!r} no se dice en la voz. Se oyó: {dicho[:300]!r}")


def resolver_cue(palabras: list[dict], cue, desde: float = 0.0) -> float:
    """Segundo en que empieza la cue (la primera aparición desde `desde`)."""
    if isinstance(cue, (int, float)):
        return float(cue)
    idx = next((i for i, p in enumerate(palabras) if p["inicio"] >= desde), len(palabras))
    return palabras[_buscar(palabras, cue, idx)]["inicio"]


def resolver_cues(palabras: list[dict], cues: list) -> list[float]:
    """Resuelve varias cues. El orden de la lista NO tiene que ser el orden en que se dicen.

    Un diagrama lista sus nodos y después sus flechas, pero la voz los intercala.
    Cada frase se busca sola; si la misma frase se repite ("la base", "la base"),
    cada repetición toma la aparición siguiente a la anterior de ESA frase.
    """
    tiempos, ultima = [], {}
    for cue in cues:
        if isinstance(cue, (int, float)):
            tiempos.append(float(cue))
            continue
        clave = tuple(_frase(cue))
        i = _buscar(palabras, cue, ultima.get(clave, -1) + 1)
        ultima[clave] = i
        tiempos.append(palabras[i]["inicio"])
    return tiempos


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="audio -> palabras.json [{palabra, inicio, fin}]")
    ap.add_argument("audio")
    ap.add_argument("salida", nargs="?", help="sin esto, imprime el JSON")
    ap.add_argument("--modelo", default=MODELO, help="tiny | base | small (default: base)")
    a = ap.parse_args()
    salida = json.dumps(transcribir(a.audio, a.modelo), ensure_ascii=False, indent=1)
    if a.salida:
        Path(a.salida).write_text(salida)
    else:
        print(salida)

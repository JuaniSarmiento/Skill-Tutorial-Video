"""editar.py zonas: detección de momentos clave sobre crudos sintéticos de verdad,
armados con ffmpeg (S7a del Hito 2, docs/explicador/HITO2.md).

Cada test fabrica un crudo de alguno de los casos reales de un screencast (HITO2.md
literal, terminal tipeando, editor con scroll, cursor/reloj parpadeando, diálogo que
aparece) y corre `editar.zonas()` de punta a punta: guion -> videos/<vid>/zonas/NN.json.
"""
import json
import subprocess
import time
from pathlib import Path

import pytest

import editar

FPS = 30


def _crudo(out: Path, filtro: str, d: float, color: str = "0x888888", r: int = FPS) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=1920x1080:r={r}:d={d}",
         "-vf", filtro, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)],
        check=True, timeout=120)


def _guion(tmp_path, nombre: str, raw_rel: str, segmentos: list[dict]) -> None:
    (tmp_path / "guion").mkdir(exist_ok=True)
    (tmp_path / "guion" / f"{nombre}.json").write_text(
        json.dumps({"raw": raw_rel, "segmentos": segmentos}, ensure_ascii=False))


def _momentos(tmp_path, vid: str, seg_idx: int = 0) -> list[dict]:
    ruta = tmp_path / "videos" / vid / "zonas" / f"{seg_idx:02d}.json"
    return json.loads(ruta.read_text())


# --- HITO2.md literal: fondo gris, cuadrado blanco en (1400, 800) en t = 1.0s --------

def test_hito2_cuadrado_en_1400_800_a_los_1s(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v30.mp4",
           "drawbox=x=1400:y=800:w=200:h=150:color=white:t=fill:enable='gte(t,1.0)'", d=3)
    _guion(tmp_path, "v30", "raw/v30.mp4", [{"inicio": 0, "fin": 3, "texto": "pantalla"}])

    rutas = editar.zonas("v30")

    assert [r.name for r in rutas] == ["00.json"]
    momentos = _momentos(tmp_path, "v30")
    assert momentos != [], "no detectó ningún momento"
    m = min(momentos, key=lambda m: abs(m["t"] - 1.0))
    assert m["t"] == pytest.approx(1.0, abs=0.6)
    assert m["x"] == pytest.approx(1400, abs=60)
    assert m["y"] == pytest.approx(800, abs=60)


# --- terminal: se tipea una línea (la zona de cambio es la línea del cursor) --------

def test_terminal_tipeando_genera_al_menos_un_momento_en_la_linea(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # 10 "caracteres" (bloques de 40x50) apareciendo uno cada 0.1s sobre la misma línea:
    # simula tipeo rápido. Cada bloque, una vez que aparece, se queda (enable='gte').
    cajas = ",".join(
        f"drawbox=x={400 + i * 42}:y=500:w=40:h=50:color=white:t=fill:enable='gte(t,{0.3 + i * 0.1:.2f})'"
        for i in range(10)
    )
    _crudo(tmp_path / "raw" / "v31.mp4", cajas, d=3)
    _guion(tmp_path, "v31", "raw/v31.mp4", [{"inicio": 0, "fin": 3, "texto": "pantalla"}])

    editar.zonas("v31")

    momentos = _momentos(tmp_path, "v31")
    assert momentos != [], "tipear en la terminal tiene que dejar al menos un momento"
    # tolerancia por la cuantización de la grilla reducida (escala ~12px en este crudo)
    assert all(400 - 30 <= m["x"] <= 400 + 10 * 42 + 40 + 30 for m in momentos), \
        f"la caja tiene que caer sobre la línea tipeada: {momentos}"


# --- editor con scroll: cambia casi toda la pantalla -> no es un momento clave -----

def test_editor_con_scroll_no_genera_momentos(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # a los 1.5s el "scroll" cambia el 90% de la pantalla de una sola vez (un color
    # distinto y sostenido, como el contenido completo del editor desplazándose).
    _crudo(tmp_path / "raw" / "v32.mp4",
           "drawbox=x=0:y=0:w=1920:h=972:color=0x222222:t=fill:enable='gte(t,1.5)'", d=3)
    _guion(tmp_path, "v32", "raw/v32.mp4", [{"inicio": 0, "fin": 3, "texto": "pantalla"}])

    editar.zonas("v32")

    assert _momentos(tmp_path, "v32") == []


# --- cursor parpadeando / reloj en la barra: ruido, no genera momentos -------------

def test_cursor_parpadeando_es_ruido_no_genera_momentos(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # un bloque que titila on/off cada 0.5s (misma cadencia que el muestreo):
    # aparece y desaparece, nunca se queda.
    _crudo(tmp_path / "raw" / "v33.mp4",
           "drawbox=x=500:y=500:w=24:h=40:color=white:t=fill:"
           "enable='lt(mod(t,1.0),0.5)'", d=4)
    _guion(tmp_path, "v33", "raw/v33.mp4", [{"inicio": 0, "fin": 4, "texto": "pantalla"}])

    editar.zonas("v33")

    assert _momentos(tmp_path, "v33") == []


def test_reloj_en_la_barra_parpadeando_tambien_es_ruido(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # el "reloj" (una esquina chica) cambia de color cada 0.5s pero nunca se sostiene
    # dos muestras seguidas en el mismo estado: reloj.py-like, puro ruido de barra.
    _crudo(tmp_path / "raw" / "v34.mp4",
           "drawbox=x=1850:y=20:w=30:h=20:color=white:t=fill:"
           "enable='lt(mod(t,1.0),0.5)'", d=4)
    _guion(tmp_path, "v34", "raw/v34.mp4", [{"inicio": 0, "fin": 4, "texto": "pantalla"}])

    editar.zonas("v34")

    assert _momentos(tmp_path, "v34") == []


# --- un diálogo aparece y se queda: sí es un momento clave --------------------------

def test_un_dialogo_que_aparece_y_se_queda_es_un_momento(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v35.mp4",
           "drawbox=x=660:y=340:w=600:h=400:color=white:t=fill:enable='gte(t,1.2)'", d=3)
    _guion(tmp_path, "v35", "raw/v35.mp4", [{"inicio": 0, "fin": 3, "texto": "pantalla"}])

    editar.zonas("v35")

    momentos = _momentos(tmp_path, "v35")
    assert momentos != []
    m = min(momentos, key=lambda m: abs(m["t"] - 1.2))
    assert m["t"] == pytest.approx(1.2, abs=0.6)
    assert m["x"] == pytest.approx(660, abs=60)
    assert m["y"] == pytest.approx(340, abs=60)


# --- varios segmentos de pantalla: un NN.json por cada uno (y ninguno para escenas) -

def test_un_json_de_zonas_por_segmento_de_pantalla_ninguno_para_escena_ni_titulo(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v36.mp4",
           "drawbox=x=100:y=100:w=200:h=200:color=white:t=fill:enable='gte(t,1.0)'", d=4)
    _guion(tmp_path, "v36", "raw/v36.mp4", [
        {"inicio": 0, "fin": 2, "texto": "uno"},
        {"tipo": "titulo", "titulo": "Un título", "texto": "titulo"},
        {"inicio": 2, "fin": 4, "texto": "dos"},
    ])

    rutas = editar.zonas("v36")

    assert sorted(r.name for r in rutas) == ["00.json", "02.json"]


# --- rendimiento: un crudo de 10 min a 1080p se analiza en tiempo razonable --------

def test_rendimiento_diez_minutos_a_1080p(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    raw = tmp_path / "raw" / "v37.mp4"
    t0 = time.monotonic()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x888888:s=1920x1080:r=30:d=600",
         "-vf", "drawbox=x=300:y=300:w=300:h=300:color=white:t=fill:enable='lt(mod(t,20),10)'",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(raw)],
        check=True, timeout=300)
    t1 = time.monotonic()
    _guion(tmp_path, "v37", "raw/v37.mp4", [{"inicio": 0, "fin": 600, "texto": "pantalla"}])

    editar.zonas("v37")

    t2 = time.monotonic()
    print(f"\nrendimiento zonas: crudo 10min 1080p generado en {t1 - t0:.1f}s, analizado en {t2 - t1:.1f}s")
    assert t2 - t1 < 120, f"el análisis de 10 min a 1080p tardó {t2 - t1:.1f}s (>120s)"
    assert _momentos(tmp_path, "v37") != []

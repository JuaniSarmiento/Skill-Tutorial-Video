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


# --- B2: tipeo a 14-16px no se puede perder por la reducción a baja resolución -----

def _crudo_tipeo(out: Path, texto: str, x0: int, y0: int, fontsize: int, t0: float = 1.0,
                  intervalo: float = 0.1, d: float = 5) -> None:
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    vf = ",".join(
        f"drawtext=fontfile={font}:text='{c}':x={x0 + i * (fontsize - 2)}:y={y0}:"
        f"fontsize={fontsize}:fontcolor=0xd4d4d4:enable='gte(t,{t0 + i * intervalo:.2f})'"
        for i, c in enumerate(texto) if c != " ")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c=0x1e1e1e:s=1920x1080:r=30:d={d}",
         "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", "-pix_fmt", "yuv444p",
         str(out)],
        check=True, timeout=120)


def test_tipeo_a_16px_se_detecta_cerca_de_su_posicion(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo_tipeo(tmp_path / "raw" / "v41.mp4", "git commit -m fix", 60, 600, 16)
    _guion(tmp_path, "v41", "raw/v41.mp4", [{"inicio": 0, "fin": 5, "texto": "pantalla"}])

    editar.zonas("v41")

    momentos = _momentos(tmp_path, "v41")
    assert momentos != [], "tipear a 16px tiene que dejar al menos un momento"
    assert any(abs(m["y"] - 600) <= 60 and 60 - 60 <= m["x"] <= 60 + 200 + 60 for m in momentos), \
        f"ningún momento cae cerca de la zona tipeada: {momentos}"


def test_tipeo_a_14px_en_otra_posicion_tambien_se_detecta(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo_tipeo(tmp_path / "raw" / "v42.mp4", "git commit -m fix", 400, 300, 14)
    _guion(tmp_path, "v42", "raw/v42.mp4", [{"inicio": 0, "fin": 5, "texto": "pantalla"}])

    editar.zonas("v42")

    momentos = _momentos(tmp_path, "v42")
    assert momentos != [], "tipear a 14px tiene que dejar al menos un momento"
    assert any(abs(m["y"] - 300) <= 60 and 400 - 60 <= m["x"] <= 400 + 200 + 60 for m in momentos), \
        f"ningún momento cae cerca de la zona tipeada: {momentos}"


def test_tipeo_lento_se_detecta_cerca_de_cuando_empieza(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo_tipeo(tmp_path / "raw" / "v43.mp4", "git commit -m fix", 60, 600, 16,
                 t0=1.0, intervalo=0.25, d=9)
    _guion(tmp_path, "v43", "raw/v43.mp4", [{"inicio": 0, "fin": 9, "texto": "pantalla"}])

    editar.zonas("v43")

    momentos = _momentos(tmp_path, "v43")
    assert momentos != [], "el tipeo lento tiene que dejar al menos un momento"
    assert min(m["t"] for m in momentos) <= 2.5, \
        f"el tipeo lento se detectó demasiado tarde: {momentos}"


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


# --- B3: dos cambios simultáneos y separados tienen que dar DOS momentos, no uno ----

def test_aviso_arriba_y_salida_abajo_a_la_vez_dan_dos_momentos(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # un aviso en (1500,40) y una salida de comando en (60,1000), a la vez (t=2): antes
    # se unían en una sola caja (de (60,40) a (1700,1150)) que no pasaba el filtro de área.
    _crudo(tmp_path / "raw" / "v38.mp4",
           "drawbox=x=1500:y=40:w=200:h=100:color=white:t=fill:enable='gte(t,2.0)',"
           "drawbox=x=60:y=1000:w=200:h=60:color=white:t=fill:enable='gte(t,2.0)'", d=4)
    _guion(tmp_path, "v38", "raw/v38.mp4", [{"inicio": 0, "fin": 4, "texto": "pantalla"}])

    editar.zonas("v38")

    momentos = _momentos(tmp_path, "v38")
    assert len(momentos) == 2, f"dos cambios separados tienen que dar dos momentos: {momentos}"
    centros = sorted((m["x"] + m["w"] / 2, m["y"] + m["h"] / 2) for m in momentos)
    assert centros[0] == pytest.approx((160, 1030), abs=80)
    assert centros[1] == pytest.approx((1600, 90), abs=80)


# --- B1: repro literal de QA -- scroll de una terminal, texto alineado a la izquierda -

def test_scroll_de_terminal_con_texto_alineado_a_la_izquierda_no_da_momentos(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    lineas = tmp_path / "lineas.txt"
    lineas.write_text("\n".join(f"[{i:03d}] compilando modulo_{i}.py ... ok" for i in range(160)))
    raw = tmp_path / "raw" / "v40.mp4"
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "color=c=0x1e1e1e:s=1920x3620:r=30:d=12",
         "-vf", f"drawtext=fontfile={font}:textfile={lineas}:x=10:y=10:fontsize=18:"
                "fontcolor=0xd4d4d4:line_spacing=4,crop=1920:1080:0:'floor(t/0.7)*22'",
         "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", "-pix_fmt", "yuv444p", str(raw)],
        check=True, timeout=120)
    _guion(tmp_path, "v40", "raw/v40.mp4", [{"inicio": 0, "fin": 12, "texto": "pantalla"}])

    editar.zonas("v40")

    assert _momentos(tmp_path, "v40") == [], \
        "el scroll de una terminal no tiene que dar ningún momento (cada scroll pasaba antes)"


# --- B4: un cambio chico y persistente (reloj) no deforma la caja del momento vecino -

def test_reloj_que_cambia_no_deforma_la_caja_del_dialogo_que_aparece(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # el "reloj" (esquina) cambia de 00:26 a 00:27 a t=1 y se queda ahí; el diálogo
    # (~400x200, centrado) aparece a t=2 y se queda. Antes el reloj quedaba en todos los
    # diffs siguientes y estiraba la caja del diálogo.
    _crudo(tmp_path / "raw" / "v39.mp4",
           "drawbox=x=1860:y=10:w=20:h=16:color=white:t=fill:enable='gte(t,1.0)',"
           "drawbox=x=760:y=440:w=400:h=200:color=white:t=fill:enable='gte(t,2.0)'", d=4)
    _guion(tmp_path, "v39", "raw/v39.mp4", [{"inicio": 0, "fin": 4, "texto": "pantalla"}])

    editar.zonas("v39")

    momentos = _momentos(tmp_path, "v39")
    dialogo = min(momentos, key=lambda m: abs(m["t"] - 2.0))
    assert dialogo["w"] == pytest.approx(400, abs=80), f"caja deformada: {momentos}"
    assert dialogo["h"] == pytest.approx(200, abs=80), f"caja deformada: {momentos}"


# --- N1: "t" está en el eje del CRUDO, no relativo al segmento ni a -ss ------------

def test_con_inicio_mayor_a_cero_t_queda_en_el_eje_del_crudo_no_del_segmento(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # el segmento de pantalla arranca en el crudo a los 5s; el cambio real pasa a los
    # 6.2s del CRUDO (1.2s relativo al segmento). Si "t" saliera relativo al segmento o
    # sin "-ss" (mirando desde 0 del crudo en vez de desde "inicio"), no caería acá.
    _crudo(tmp_path / "raw" / "v44.mp4",
           "drawbox=x=660:y=340:w=600:h=400:color=white:t=fill:enable='gte(t,6.2)'", d=10)
    _guion(tmp_path, "v44", "raw/v44.mp4", [{"inicio": 5, "fin": 10, "texto": "pantalla"}])

    editar.zonas("v44")

    momentos = _momentos(tmp_path, "v44")
    assert momentos != []
    m = min(momentos, key=lambda m: abs(m["t"] - 6.2))
    assert m["t"] == pytest.approx(6.2, abs=0.6), f"t tiene que estar en el eje del crudo: {momentos}"
    assert m["x"] == pytest.approx(660, abs=60)
    assert m["y"] == pytest.approx(340, abs=60)


# --- N1: resoluciones no 16:9 no corren la caja por usar una sola escala para los ejes -

def test_resolucion_no_16_9_no_corre_la_caja_en_y(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    # 3440x1440 (QA): con una sola escala para los dos ejes, redondear "alto" a un
    # entero par corre la escala vertical real ~1.5% respecto de la horizontal, y a
    # y=1000 eso ya son ~15px de corrida -por encima de la tolerancia del test-.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x888888:s=3440x1440:r=30:d=3",
         "-vf", "drawbox=x=500:y=1250:w=200:h=150:color=white:t=fill:enable='gte(t,1.0)'",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(tmp_path / "raw" / "v45.mp4")],
        check=True, timeout=120)
    _guion(tmp_path, "v45", "raw/v45.mp4", [{"inicio": 0, "fin": 3, "texto": "pantalla"}])

    editar.zonas("v45")

    momentos = _momentos(tmp_path, "v45")
    assert momentos != []
    m = min(momentos, key=lambda m: abs(m["t"] - 1.0))
    assert m["y"] == pytest.approx(1250, abs=8), f"caja corrida en y: {momentos}"
    assert m["x"] == pytest.approx(500, abs=8), f"caja corrida en x: {momentos}"


# --- N2: errores claros nombrando el segmento, sin traceback -----------------------

def test_vid_inexistente_da_error_claro_sin_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)

    with pytest.raises(SystemExit) as exc:
        editar.zonas("v99")

    assert "v99" in str(exc.value)


def test_crudo_faltante_aborta_nombrando_el_segmento(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    _guion(tmp_path, "v46", "raw/no-existe.mp4", [{"inicio": 0, "fin": 3, "texto": "x"}])

    with pytest.raises(SystemExit) as exc:
        editar.zonas("v46")

    assert "00" in str(exc.value)


def test_inicio_mayor_o_igual_a_fin_da_error_claro_con_el_segmento(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v47.mp4", "drawbox=x=0:y=0:w=2:h=2:color=white:t=fill", d=2)
    _guion(tmp_path, "v47", "raw/v47.mp4", [{"inicio": 2, "fin": 1, "texto": "x"}])

    with pytest.raises(SystemExit) as exc:
        editar.zonas("v47")

    assert "00" in str(exc.value)


def test_falta_fin_da_error_claro_con_el_segmento(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v48.mp4", "drawbox=x=0:y=0:w=2:h=2:color=white:t=fill", d=2)
    _guion(tmp_path, "v48", "raw/v48.mp4", [{"inicio": 0, "texto": "x"}])

    with pytest.raises(SystemExit) as exc:
        editar.zonas("v48")

    assert "00" in str(exc.value)


def test_segmento_mas_alla_de_la_duracion_del_crudo_da_aviso_no_aborta(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v49.mp4", "drawbox=x=0:y=0:w=2:h=2:color=white:t=fill", d=2)
    _guion(tmp_path, "v49", "raw/v49.mp4", [{"inicio": 0, "fin": 10, "texto": "x"}])

    rutas = editar.zonas("v49")

    assert rutas != []
    assert "AVISO" in capsys.readouterr().out


def test_zonas_viejos_de_segmentos_que_ya_no_son_pantalla_se_borran(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    _crudo(tmp_path / "raw" / "v50.mp4", "drawbox=x=0:y=0:w=2:h=2:color=white:t=fill", d=2)
    _guion(tmp_path, "v50", "raw/v50.mp4", [{"inicio": 0, "fin": 2, "texto": "x"}])
    out = tmp_path / "videos" / "v50" / "zonas"
    out.mkdir(parents=True)
    viejo = out / "05.json"  # índice de un segmento que ya no existe / no es pantalla
    viejo.write_text("[]")

    editar.zonas("v50")

    assert not viejo.exists()


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

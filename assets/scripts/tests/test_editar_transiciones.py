"""editar.py integra transiciones.py (S6 del Hito 2, docs/explicador/HITO2.md).

G3: sin "transicion" en el guion, byte a byte igual que antes de este cambio -lo
cubre `test_s0_red_de_seguridad.py`, que tiene que seguir en pie sin regenerar su
base-. G1/G2: la transición no mueve ningún slot (cuadros y arranque de la voz
intactos). G4: todos los tramos comparten códec/tamaño/pix_fmt/fps.
"""
import json
import subprocess

import pytest

pytest.importorskip("playwright")
import editar  # noqa: E402
import palabras  # noqa: E402

pytestmark = pytest.mark.integracion


def _raw(tmp_path, dur=4):
    r = tmp_path / "raw" / "v09.mp4"
    r.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=s=1920x1080:r=30:d={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(r)], check=True)
    return r


def _probe(mp4, campos="codec_name,width,height,pix_fmt,r_frame_rate,nb_read_packets"):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                          "-show_entries", f"stream={campos}", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out.split(",")


def _pixel(mp4, t: float):
    """Color (r,g,b) del CENTRO del cuadro en el segundo `t` (NOTE de QA: medir
    en (0,0) es medir una esquina que puede quedar fuera del recuadro real que
    se quiere chequear). Afirma que ffmpeg devolvió un cuadro de verdad: un `t`
    más allá de la duración del archivo da stdout vacío, y `tuple(b"")[:3]`
    es `()`, que `_cerca((), esperado)` compara con `all([])` -> True: un falso
    positivo silencioso que no mide nada (NOTE de QA)."""
    w, h = (int(x) for x in _probe(mp4, "width,height"))
    cx, cy = (w // 2) & ~1, (h // 2) & ~1  # pares: yuv420p submuestrea el croma
    # `-ss` DESPUÉS de `-i` (seek exacto por decodificación, no por keyframe): un
    # `t` a menos de un cuadro del final del archivo puede no devolver NADA con
    # `-ss` antes de `-i` (medido: pasaba en este mismo archivo), que es
    # exactamente el vacío que `_cerca(())` tapaba en silencio (NOTE de QA).
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-ss", str(t), "-frames:v", "1",
                          "-vf", f"crop=2:2:{cx}:{cy}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    assert len(out) >= 3, f"ffmpeg no devolvió ningún cuadro en t={t} para {mp4}"
    return tuple(out[:3])


def _cerca(rgb, esperado, tol=4):
    return all(abs(a - b) <= tol for a, b in zip(rgb, esperado))


# --- NOTE de QA: _pixel(t) más allá de la duración del archivo devuelve stdout
# vacío (`tuple(b"")[:3] == ()`), y `_cerca((), esperado)` da True (`all([])` de
# una lista vacía): un falso positivo silencioso. Y mide (0,0), una esquina que
# puede quedar fuera del recuadro real que se quiere medir.

def test_pixel_falla_si_ffmpeg_no_devuelve_ningun_cuadro(tmp_path):
    r = _raw(tmp_path, dur=1)
    with pytest.raises(Exception):
        _pixel(r, 10.0)  # bien más allá de la duración: ffmpeg no entrega cuadro


def test_pixel_mide_el_centro_del_cuadro_no_la_esquina(tmp_path):
    # acento SÓLO en el centro: si _pixel mide (0,0) (la esquina, gris), no lo ve.
    clip = tmp_path / "centro.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=gray:s=320x240:r=30:d=1",
                    "-vf", "drawbox=x=150:y=110:w=20:h=20:color=0xF2B544:thickness=fill",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(clip)], check=True)
    assert _cerca(_pixel(clip, 0.1), (242, 181, 68))


def _armar_guion(tmp_path, monkeypatch, guion: dict, vid="v09", voz="juani"):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / f"{vid}.json").write_text(json.dumps(guion, ensure_ascii=False))
    voces = tmp_path / "videos" / vid / voz
    voces.mkdir(parents=True)
    for i in range(len(guion["segmentos"])):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=1",
                        str(voces / f"{i:02d}.wav")], check=True)
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None:
                        [{"palabra": "Hola", "inicio": 0.0, "fin": 0.3}])


def test_r67_tipo_desconocido_aborta_antes_de_generar_ningun_seg(tmp_path, monkeypatch):
    # "tipo": "titulo": no necesita crudo, así el único abort posible es el de R-6.7
    guion = {"transicion": "transicon", "segmentos": [
        {"tipo": "titulo", "titulo": "a", "texto": "a"},
        {"tipo": "titulo", "titulo": "b", "texto": "b"}]}
    _armar_guion(tmp_path, monkeypatch, guion)

    with pytest.raises(SystemExit) as e:
        editar.imagen("v09", "juani")

    assert "transicon" in str(e.value)
    seg_dir = tmp_path / "videos" / "v09" / "seg"
    assert not seg_dir.exists() or not list(seg_dir.glob("*.mp4"))


def test_una_paleta_desconocida_en_el_guion_aborta_antes_de_generar_ningun_seg(tmp_path, monkeypatch):
    """H10 (HITO3.md): "paleta" se valida apenas se carga el guion, igual que R-6.7
    con "transicion", y no sólo cuando algo renderiza con el motor de escenas (un
    guion sin escenas ni transición también debe rechazar una paleta inventada)."""
    guion = {"paleta": "fantasia", "segmentos": [
        {"tipo": "titulo", "titulo": "a", "texto": "a"},
        {"tipo": "titulo", "titulo": "b", "texto": "b"}]}
    _armar_guion(tmp_path, monkeypatch, guion)

    with pytest.raises(SystemExit) as e:
        editar.imagen("v09", "juani")

    assert "fantasia" in str(e.value)
    assert "utn" in str(e.value)
    seg_dir = tmp_path / "videos" / "v09" / "seg"
    assert not seg_dir.exists() or not list(seg_dir.glob("*.mp4"))


def test_g1_g4_con_barrido_entre_pantalla_y_escena(tmp_path, monkeypatch):
    _raw(tmp_path)
    guion = {"raw": "raw/v09.mp4", "transicion": {"tipo": "barrido", "duracion": 0.3}, "segmentos": [
        {"inicio": 0, "fin": 2, "texto": "Pantalla."},
        {"escena": {"tipo": "presentacion", "titulo": {"texto": "Hola"}}, "texto": "Escena."},
    ]}
    _armar_guion(tmp_path, monkeypatch, guion)

    editar.imagen("v09", "juani")

    work = tmp_path / "videos" / "v09"
    pantalla = _probe(work / "seg" / "00.mp4")
    escena_ = _probe(work / "seg" / "01.mp4")
    assert pantalla[:5] == escena_[:5] == ["h264", "1920", "1080", "yuv420p", "30/1"]  # G4
    slots = json.loads((work / "slots-juani.json").read_text())
    assert int(pantalla[5]) == round(slots[0] * 30)  # G1: la transición no corrió los cuadros
    assert int(escena_[5]) == round(slots[1] * 30)

    # el barrido pintó el acento del brand cerca del corte en LOS DOS lados.
    # El último cuadro REAL del archivo (no slots[0]-0.02: ese instante cae
    # dentro de la ventana de despliegue del último cuadro y ffmpeg puede no
    # devolver NINGÚN cuadro ahí -medido-, que es justo el vacío que _pixel
    # ahora hace fallar fuerte en vez de dejar pasar en silencio, NOTE de QA).
    acento = (242, 181, 68)  # #F2B544
    ultimo_cuadro_00 = (round(slots[0] * 30) - 1) / 30
    assert _cerca(_pixel(work / "seg" / "00.mp4", ultimo_cuadro_00), acento)
    assert _cerca(_pixel(work / "seg" / "01.mp4", 0.0), acento)
    # y lejos del corte no (no tapa toda la pantalla)
    assert not _cerca(_pixel(work / "seg" / "00.mp4", 0.05), acento)


def test_barrido_con_paleta_elegida_pinta_el_acento_de_esa_paleta(tmp_path, monkeypatch):
    """H10 (HITO3.md): "paleta" arriba del guion también gobierna el color de la
    transición (R-6.3 sale del brand, y el brand ahora puede traer una paleta)."""
    _raw(tmp_path)
    guion = {"raw": "raw/v09.mp4", "paleta": "utn",
             "transicion": {"tipo": "barrido", "duracion": 0.3}, "segmentos": [
                 {"inicio": 0, "fin": 2, "texto": "Pantalla."},
                 {"escena": {"tipo": "presentacion", "titulo": {"texto": "Hola"}}, "texto": "Escena."},
             ]}
    _armar_guion(tmp_path, monkeypatch, guion)

    editar.imagen("v09", "juani")

    work = tmp_path / "videos" / "v09"
    slots = json.loads((work / "slots-juani.json").read_text())
    acento_utn = (181, 71, 8)  # #B54708
    ultimo_cuadro_00 = (round(slots[0] * 30) - 1) / 30
    assert _cerca(_pixel(work / "seg" / "00.mp4", ultimo_cuadro_00), acento_utn)

"""H2 (HITO3.md): `editar.py revisar` suma la puerta de verificar.py sobre los specs
resueltos de cada escena: D5 (contraste) y D6 (textos que se pisan o se salen del
cuadro útil, con la banda de subtítulos libre).
"""
import json

import pytest

import editar
import verificar


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "videos" / "v09").mkdir(parents=True)
    return tmp_path


SEG = {"escena": {"tipo": "presentacion"}, "texto": "uno dos", "rol": "gancho"}


def _con_escena(raiz, **campos):
    (raiz / "guion" / "v09.json").write_text(json.dumps({"segmentos": [SEG]}))
    escenas = raiz / "videos" / "v09" / "escenas"
    escenas.mkdir()
    spec = {"tipo": "presentacion", "titulo": {"texto": "Hola"}, "duracion": 2.0,
            "puntos": [{"texto": "Uno", "cue": "uno", "t": 0.5}],
            "_voz": "argentina", "_segmento_hash": editar._hash_segmento(SEG), **campos}
    (escenas / "00.json").write_text(json.dumps(spec))


def test_d5_y_d6_separan_los_hallazgos_de_la_puerta_por_tipo(raiz, monkeypatch):
    _con_escena(raiz)
    falsos = [verificar.Hallazgo("contraste", "00.json, t=1.00 s: 'nota' tiene contraste 2.00:1"),
              verificar.Hallazgo("solape", "00.json, t=1.00 s: 'a' y 'b' se pisan"),
              verificar.Hallazgo("desborde", "00.json, t=1.00 s: 'c' se sale del cuadro útil"),
              verificar.Hallazgo("cue", "00.json, t=1.00 s: 'd' ya se ve")]
    monkeypatch.setattr(verificar, "verificar_escena", lambda *a, **k: falsos)
    hallazgos, _ = editar.revisar("v09", "argentina")
    legibles = [h for h in hallazgos if "00.json, t=" in h]
    assert legibles == ["contraste: 00.json, t=1.00 s: 'nota' tiene contraste 2.00:1",
                        "desborde: 00.json, t=1.00 s: 'a' y 'b' se pisan",
                        "desborde: 00.json, t=1.00 s: 'c' se sale del cuadro útil"]


def test_si_la_puerta_no_puede_correr_es_no_corrio_nombrando_el_spec(raiz, monkeypatch):
    _con_escena(raiz)

    def rompe(*a, **k):
        raise RuntimeError("Chrome no arrancó")
    monkeypatch.setattr(verificar, "verificar_escena", rompe)
    hallazgos, no_corrio = editar.revisar("v09", "argentina")
    assert not any("00.json, t=" in h for h in hallazgos)
    assert any("00.json" in c and "Chrome no arrancó" in c for c in no_corrio), no_corrio


@pytest.mark.integracion
def test_con_un_brand_de_texto_casi_del_color_del_fondo_d5_lo_encuentra_de_verdad(raiz):
    pytest.importorskip("playwright")
    _con_escena(raiz)
    (raiz / "brand.json").write_text(json.dumps({"colores": {"texto": "#2A2D33"}}))
    hallazgos, _ = editar.revisar("v09", "argentina")
    assert any(h.startswith("contraste: 00.json") for h in hallazgos), hallazgos


@pytest.mark.integracion
def test_con_el_brand_de_la_skill_la_escena_no_tiene_hallazgos_de_legibilidad(raiz):
    pytest.importorskip("playwright")
    _con_escena(raiz)
    hallazgos, no_corrio = editar.revisar("v09", "argentina")
    assert not any(h.startswith(("contraste:", "desborde:")) for h in hallazgos), hallazgos
    assert not any("legibilidad" in c for c in no_corrio), no_corrio


def test_d5_usa_la_paleta_que_eligio_el_guion(raiz, monkeypatch):
    # revisar verificaba con cargar_brand SIN paleta: un guion "utn" (fondo blanco) se medía
    # contra el fondo de "noche" y daba contrastes falsos (serie Prog IV, 12/10/2026).
    _con_escena(raiz)
    (raiz / "guion" / "v09.json").write_text(json.dumps({"paleta": "utn", "segmentos": [SEG]}))
    vistos = []
    monkeypatch.setattr(verificar, "verificar_escena", lambda plantilla, spec, brand, *a, **k: vistos.append(brand) or [])
    editar.revisar("v09", "argentina")
    assert vistos and vistos[0]["colores"]["fondo"] == "#FFFFFF"

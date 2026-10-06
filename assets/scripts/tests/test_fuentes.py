"""H2 (HITO3.md): la tipografía de las escenas viaja con la skill.

El motor bloquea la red, así que una fuente que no está en assets/escenas/fuentes/ no
existe para Chrome. Cada archivo tiene que estar declarado en el LEEME con su sha256
(para saber que es el que se bajó) y la licencia OFL tiene que viajar con él.
"""
import hashlib
import json
import re

import escena

FUENTES = escena.ESCENAS / "fuentes"


def _sha_del_leeme() -> dict[str, str]:
    leeme = FUENTES / "LEEME.md"
    texto = leeme.read_text() if leeme.exists() else ""
    return dict((n, h) for h, n in re.findall(r"`([0-9a-f]{64})`\s+`([^`]+\.woff2)`", texto))


def test_cada_woff2_esta_en_el_leeme_con_su_sha256_real():
    declarados = _sha_del_leeme()
    archivos = sorted(p.name for p in FUENTES.glob("*.woff2"))
    assert archivos, "no hay ninguna fuente en assets/escenas/fuentes/"
    assert sorted(declarados) == archivos
    for nombre, sha in declarados.items():
        assert hashlib.sha256((FUENTES / nombre).read_bytes()).hexdigest() == sha, nombre


def test_cada_familia_trae_su_licencia_ofl():
    for familia in ("Barlow", "IBM-Plex-Mono"):
        ofl = FUENTES / f"OFL-{familia}.txt"
        texto = ofl.read_text() if ofl.exists() else ""
        assert "SIL Open Font License" in texto, familia


def test_el_brand_declara_la_fuente_de_titulos_y_la_mono():
    brand = json.loads((escena.ESCENAS / "brand.json").read_text())
    assert brand.get("fuente_titulos") == "Barlow"
    assert brand.get("fuente_mono") == "IBM Plex Mono"


def test_cada_familia_del_brand_tiene_su_font_face_local_en_base_css():
    css = (escena.ESCENAS / "base.css").read_text()
    caras = re.findall(r'@font-face\s*\{[^}]*font-family:\s*"([^"]+)"[^}]*url\("fuentes/([^"]+)"\)', css)
    assert {f for f, _ in caras} >= {"Barlow", "IBM Plex Mono"}
    for _, archivo in caras:
        assert (FUENTES / archivo).exists(), archivo

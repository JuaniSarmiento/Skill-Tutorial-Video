"""H0 (HITO3.md): GSAP vendorizado en assets/escenas/vendor/gsap/.

El motor bloquea la red, así que GSAP viaja con la skill. Lo que se congela acá:
que los bytes sean los que LEEME.md dice que se bajaron (sha256), y que ninguno
pierda su aviso de licencia (la GSAP Standard License prohíbe quitarlo).
"""
import hashlib
import re

import escena

VENDOR = escena.ESCENAS / "vendor" / "gsap"
ARCHIVOS = ["gsap.min.js", "DrawSVGPlugin.min.js", "MorphSVGPlugin.min.js",
            "SplitText.min.js", "CustomEase.min.js"]


def _shas_del_leeme() -> dict:
    """LEEME.md lista cada archivo como: `<sha256>`  `<archivo>`."""
    leeme = VENDOR / "LEEME.md"
    texto = leeme.read_text() if leeme.exists() else ""
    return {nombre: sha for sha, nombre in re.findall(r"`([0-9a-f]{64})`\s+`([\w.]+)`", texto)}


def test_cada_archivo_de_gsap_coincide_con_el_sha256_del_leeme():
    shas = _shas_del_leeme()
    for archivo in ARCHIVOS:
        assert archivo in shas, f"LEEME.md no declara el sha256 de {archivo}"
        real = hashlib.sha256((VENDOR / archivo).read_bytes()).hexdigest()
        assert real == shas[archivo], f"{archivo} no es el que se bajó: {real}"


def test_cada_archivo_de_gsap_conserva_su_aviso_de_licencia():
    for archivo in ARCHIVOS:
        ruta = VENDOR / archivo
        cabecera = ruta.read_bytes()[:400].decode() if ruta.exists() else ""
        assert "@license" in cabecera and "gsap.com/standard-license" in cabecera, archivo


def test_la_licencia_de_gsap_viaja_junto_al_codigo():
    licencia = VENDOR / "LICENCIA.txt"
    texto = licencia.read_text() if licencia.exists() else ""
    assert "Prohibited Uses" in texto and "Webflow" in texto

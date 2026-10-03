"""Escena "imagen" (HITO2.md S4): partes puras, sin Chrome.

R-4.6: un SVG faltante o con href externo falla ANTES de abrir Chrome. Eso se
decide acá (resolver_dibujos), no en el render: por eso no hace falta
playwright para probarlo.
"""
import pytest

import escena


def test_un_dibujo_con_svg_inexistente_falla_nombrando_la_ruta(tmp_path):
    spec = {"dibujos": [{"id": "a", "svg": str(tmp_path / "no-existe.svg"), "cue": 0.1}]}
    with pytest.raises(ValueError, match="no-existe.svg"):
        escena.resolver_dibujos(spec)


def test_un_svg_con_href_externo_falla_nombrando_la_ruta(tmp_path):
    p = tmp_path / "malo.svg"
    p.write_text('<svg><image href="https://evil.example/foto.png"/></svg>')
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}
    with pytest.raises(ValueError, match="malo.svg"):
        escena.resolver_dibujos(spec)


def test_un_svg_valido_queda_embebido_en_markup(tmp_path):
    p = tmp_path / "bueno.svg"
    p.write_text('<svg viewBox="0 0 10 10"><path d="M0 0L10 10"/></svg>')
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}

    out = escena.resolver_dibujos(spec)

    assert "M0 0L10 10" in out["dibujos"][0]["markup"]


def test_sin_dibujos_no_hace_nada(tmp_path):
    spec = {"titulo": {"texto": "Hola"}}
    assert escena.resolver_dibujos(spec) == spec


def test_resolver_dibujos_no_toca_el_spec_original(tmp_path):
    p = tmp_path / "bueno.svg"
    p.write_text("<svg></svg>")
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}

    escena.resolver_dibujos(spec)

    assert "markup" not in spec["dibujos"][0]

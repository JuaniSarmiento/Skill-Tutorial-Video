"""Escena "imagen" (HITO2.md S4): partes puras, sin Chrome.

R-4.6: un SVG faltante o con href externo falla ANTES de abrir Chrome. Eso se
decide acá (resolver_dibujos), no en el render: por eso no hace falta
playwright para probarlo.

B1 (QA 03/10/2026, repro en /tmp/claude-1000/qa-s4/repro/): el regex viejo
(HREF_EXTERNO) sólo detectaba `https?://` en minúscula y con comillas, y el SVG
entraba por innerHTML (los <script>/on*/foreignObject se ejecutaban). Ahora
`resolver_dibujos` parsea el SVG como XML y lo pasa por una lista blanca de
elementos y atributos (`sanear_svg`): lo que no está en la lista blanca falla
ANTES de abrir Chrome, nombrando archivo/elemento/atributo.
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


# --- N1 (QA 04/10/2026): "markup" es un campo que SÓLO genera resolver_dibujos; un spec
# de usuario que lo traiga de entrada saltea el saneado (sanear_svg) y entra directo a
# innerHTML. Falla claro, nombrando el dibujo, antes de abrir Chrome.

def test_un_dibujo_con_markup_de_usuario_falla_claro(tmp_path):
    spec = {"dibujos": [{"id": "a", "cue": 0.1, "markup": "<svg><script>alert(1)</script></svg>"}]}
    with pytest.raises(ValueError, match="markup"):
        escena.resolver_dibujos(spec)


def test_un_dibujo_con_markup_y_svg_a_la_vez_tambien_falla_claro(tmp_path):
    p = tmp_path / "bueno.svg"
    p.write_text('<svg viewBox="0 0 10 10"><path d="M0 0L10 10" stroke="currentColor" fill="none"/></svg>')
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1, "markup": "<svg></svg>"}]}
    with pytest.raises(ValueError, match="markup"):
        escena.resolver_dibujos(spec)


def test_resolver_dibujos_no_toca_el_spec_original(tmp_path):
    p = tmp_path / "bueno.svg"
    p.write_text("<svg></svg>")
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}

    escena.resolver_dibujos(spec)

    assert "markup" not in spec["dibujos"][0]


# --- B1: lista blanca de elementos/atributos (QA 03/10/2026) -------------------

def _spec_con_svg(tmp_path, contenido, nombre="malo.svg"):
    p = tmp_path / nombre
    p.write_text(contenido)
    return {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}


VECTORES_RECHAZADOS = [
    ("mayusculas", '<svg><image href="HTTP://evil.example/x.png"/></svg>'),
    ("sin_comillas", '<svg><use href=http://evil.example/x></svg>'),
    ("entidad_numerica", '<svg><use href="&#104;ttp://evil.example/x"/></svg>'),
    ("import_css", '<svg><style>@import url(http://evil.example/x.css);</style></svg>'),
    ("font_face", '<svg><style>@font-face{font-family:x;src:url(http://evil.example/f.woff)}</style></svg>'),
    ("fill_url_externo", '<svg><path fill="url(http://evil.example/x)" d="M0 0L1 1"/></svg>'),
    ("foreignobject_img_onerror",
     '<svg><foreignObject><img src=x onerror="alert(1)"></foreignObject></svg>'),
    ("foreignobject_iframe", '<svg><foreignObject><iframe src="http://evil.example"></iframe></foreignObject></svg>'),
    ("foreignobject_background",
     '<svg><foreignObject><div style="background:url(http://evil.example/x)"></div></foreignObject></svg>'),
    ("image_data_uri_foto", '<svg><image href="data:image/png;base64,AAAA"/></svg>'),
    ("file_scheme", '<svg><use href="file:///etc/hostname"/></svg>'),
    ("doctype", '<!DOCTYPE svg [<!ENTITY x "y">]><svg></svg>'),
    ("entity", '<svg><!ENTITY x "y"><text>&x;</text></svg>'),
    ("script_tag", '<svg><script>alert(1)</script></svg>'),
    ("on_atributo", '<svg><path onclick="alert(1)" d="M0 0L1 1"/></svg>'),
    ("smil_animate", '<svg><animate attributeName="x" to="100"/></svg>'),
    ("style_con_url", '<svg><path style="fill:url(http://evil.example/x)" d="M0 0L1 1"/></svg>'),
]


@pytest.mark.parametrize("nombre, contenido", VECTORES_RECHAZADOS, ids=[v[0] for v in VECTORES_RECHAZADOS])
def test_vector_de_qa_rechazado_antes_de_abrir_chrome(tmp_path, nombre, contenido):
    spec = _spec_con_svg(tmp_path, contenido)
    with pytest.raises(ValueError, match="malo.svg"):
        escena.resolver_dibujos(spec)


def test_svg_valido_de_la_convencion_sigue_quedando_embebido(tmp_path):
    contenido = ('<svg viewBox="0 0 10 10">'
                 '<path d="M0 0L10 10" fill="none" stroke="currentColor"/>'
                 '<path class="lleno" fill="currentColor" d="M1 1L2 2L1 2Z"/>'
                 '</svg>')
    spec = _spec_con_svg(tmp_path, contenido, "bueno.svg")

    out = escena.resolver_dibujos(spec)

    assert "M0 0L10 10" in out["dibujos"][0]["markup"]


# --- B3: svg relativo al directorio del spec, no al cwd (QA 03/10/2026) -------

def test_svg_relativo_se_resuelve_contra_el_directorio_del_spec(tmp_path, monkeypatch):
    serie = tmp_path / "serie"
    serie.mkdir()
    (serie / "dibujo.svg").write_text(
        '<svg viewBox="0 0 10 10"><path d="M0 0L10 10" stroke="currentColor" fill="none"/></svg>')
    spec = {"dibujos": [{"id": "a", "svg": "dibujo.svg", "cue": 0.1}]}
    otro_cwd = tmp_path / "otro"
    otro_cwd.mkdir()
    monkeypatch.chdir(otro_cwd)   # el cwd NO tiene el svg: si se resolviera contra él, fallaría

    out = escena.resolver_dibujos(spec, base_dir=serie)

    assert "M0 0L10 10" in out["dibujos"][0]["markup"]


def test_svg_relativo_sin_base_dir_se_resuelve_contra_el_cwd(tmp_path, monkeypatch):
    (tmp_path / "dibujo.svg").write_text("<svg></svg>")
    spec = {"dibujos": [{"id": "a", "svg": "dibujo.svg", "cue": 0.1}]}
    monkeypatch.chdir(tmp_path)

    out = escena.resolver_dibujos(spec)   # sin base_dir: default documentado, cwd

    assert "markup" in out["dibujos"][0]


def test_svg_absoluto_no_se_ve_afectado_por_base_dir(tmp_path):
    p = tmp_path / "bueno.svg"
    p.write_text("<svg></svg>")
    spec = {"dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}

    out = escena.resolver_dibujos(spec, base_dir=tmp_path / "otro-directorio-inexistente")

    assert "markup" in out["dibujos"][0]


# --- B4(b): colores fijos (sin recoloreado al brand) rechazados (QA 03/10/2026) ----

@pytest.mark.parametrize("valor", ["#ff0000", "rgb(255, 0, 0)", "red", "hsl(0, 100%, 50%)"])
def test_fill_con_color_fijo_rechazado(tmp_path, valor):
    contenido = f'<svg viewBox="0 0 10 10"><path d="M0 0L1 1" fill="{valor}"/></svg>'
    spec = _spec_con_svg(tmp_path, contenido)
    with pytest.raises(ValueError, match="malo.svg"):
        escena.resolver_dibujos(spec)


def test_stroke_con_color_fijo_rechazado(tmp_path):
    contenido = '<svg viewBox="0 0 10 10"><path d="M0 0L1 1" stroke="#00ff00" fill="none"/></svg>'
    spec = _spec_con_svg(tmp_path, contenido)
    with pytest.raises(ValueError, match="malo.svg"):
        escena.resolver_dibujos(spec)


@pytest.mark.parametrize("fill, stroke", [("none", "currentColor"), ("currentColor", "none")])
def test_fill_y_stroke_de_la_convencion_se_aceptan(tmp_path, fill, stroke):
    contenido = f'<svg viewBox="0 0 10 10"><path d="M0 0L1 1" fill="{fill}" stroke="{stroke}"/></svg>'
    spec = _spec_con_svg(tmp_path, contenido, "bueno.svg")
    out = escena.resolver_dibujos(spec)
    assert "M0 0L1 1" in out["dibujos"][0]["markup"]


# --- B4(a): <text> es dibujo vectorial válido (QA 03/10/2026) -----------------

def test_svg_con_text_se_acepta(tmp_path):
    contenido = ('<svg viewBox="0 0 200 200">'
                 '<text x="10" y="150" font-size="140" fill="currentColor">OK</text></svg>')
    spec = _spec_con_svg(tmp_path, contenido, "bueno.svg")
    out = escena.resolver_dibujos(spec)
    assert "<text" in out["dibujos"][0]["markup"]


def test_use_con_href_interno_se_acepta(tmp_path):
    contenido = ('<svg viewBox="0 0 10 10">'
                 '<defs><path id="p" d="M0 0L10 10"/></defs>'
                 '<use href="#p" stroke="currentColor"/>'
                 '</svg>')
    spec = _spec_con_svg(tmp_path, contenido, "bueno.svg")

    out = escena.resolver_dibujos(spec)

    assert 'href="#p"' in out["dibujos"][0]["markup"]

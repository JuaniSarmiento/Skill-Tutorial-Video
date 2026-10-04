"""Las plantillas de assets/escenas/ contra Chrome: función pura de t y cues respetadas.

Una plantilla que lee el reloj, usa transiciones CSS o acumula estado entre
cuadros se delata acá: el mismo t tiene que dar el mismo PNG, venga en el orden
que venga. Y un elemento no puede asomar antes de la palabra que lo nombra.
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

DIBUJOS = escena.ESCENAS / "dibujos"

SPECS = {
    "presentacion": {
        "titulo": {"texto": "El interés compuesto"},
        "puntos": [{"texto": "Ganás intereses", "cue": 2.0},
                   {"texto": "sobre intereses ya ganados", "cue": 3.2}],
        "duracion": 4.5,
    },
    "diagrama": {
        "titulo": {"texto": "Cómo crece la plata"},
        "nodos": [{"id": "c", "texto": "Capital", "cue": 0.4},
                  {"id": "i", "texto": "Interés", "cue": 2.0},
                  {"id": "n", "texto": "Capital nuevo", "cue": 3.0}],
        "flechas": [{"de": "c", "a": "i", "texto": "rinde", "cue": 2.4},
                    {"de": "i", "a": "n", "cue": 3.4}],
        "duracion": 4.5,
    },
    "datos": {
        "titulo": {"texto": "1.000 pesos al 10 % anual"},
        "barras": [{"etiqueta": "Año 0", "valor": 1000, "cue": 0.4},
                   {"etiqueta": "Año 10", "valor": 2594, "cue": 2.0},
                   {"etiqueta": "Año 30", "valor": 17449, "cue": 3.0, "destacar": True}],
        "nota": "Interés compuesto anual, sin aportes extra",
        "duracion": 4.5,
    },
    "imagen": {
        "titulo": {"texto": "Una idea que crece"},
        "dibujos": [{"id": "lampara", "svg": str(DIBUJOS / "lampara.svg"), "cue": 0.4},
                    {"id": "semilla", "svg": str(DIBUJOS / "semilla.svg"), "cue": 2.0}],
        "rotulos": [{"texto": "Idea", "cue": 0.4, "de": "lampara"},
                    {"texto": "Crece", "cue": 2.0, "de": "semilla"}],
        "duracion": 4.5,
    },
}
SPECS["imagen"] = escena.resolver_dibujos(SPECS["imagen"])  # el markup se embebe ANTES de abrir Chrome
# t en el que entra un elemento con cue, para cada plantilla
CUE = {"presentacion": 2.0, "diagrama": 2.0, "datos": 2.0, "imagen": 2.0}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


@pytest.mark.parametrize("tipo", SPECS)
def test_el_mismo_t_da_el_mismo_cuadro(chrome, tipo):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, _):
        assert _hash(page, 2.3) == _hash(page, 2.3)


@pytest.mark.parametrize("tipo", SPECS)
def test_el_orden_de_los_cuadros_no_cambia_ningun_cuadro(chrome, tipo):
    ts = [0.3, 2.2, 3.6, 1.1]
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo], brand) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo], brand) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts), "cuatro momentos distintos tienen que verse distintos"


@pytest.mark.parametrize("tipo", SPECS)
def test_nada_entra_antes_de_su_cue_y_entra_en_su_cue(chrome, tipo):
    cue = CUE[tipo]
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, _):
        justo_antes, un_poco_antes = _hash(page, cue - 0.02), _hash(page, cue - 0.4)
        despues = _hash(page, cue + 0.3)
    assert un_poco_antes == justo_antes, "algo se movió antes de la cue"
    assert despues != justo_antes, "el elemento no entró en su cue"


AIRE = 16  # px mínimos entre dos cajas: pegadas se leen como una sola


@pytest.mark.parametrize("tipo", SPECS)
def test_al_final_ningun_elemento_se_superpone_ni_queda_pegado_a_otro(chrome, tipo):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, d):
        page.evaluate("t => window.seek(t)", d - 0.05)
        cajas = page.evaluate("""() => [...document.querySelectorAll('[data-caja]')].map(e => {
            const r = e.getBoundingClientRect();
            return {n: e.dataset.caja, x: r.left, y: r.top, w: r.width, h: r.height};
        })""")
    assert len(cajas) >= 3
    for i, a in enumerate(cajas):
        assert a["x"] >= 0 and a["y"] >= 0 and a["x"] + a["w"] <= 1920 and a["y"] + a["h"] <= 1080, a
        for b in cajas[i + 1:]:
            solapan = (a["x"] < b["x"] + b["w"] + AIRE and b["x"] < a["x"] + a["w"] + AIRE
                       and a["y"] < b["y"] + b["h"] + AIRE and b["y"] < a["y"] + a["h"] + AIRE)
            assert not solapan, f"{a['n']} se pisa o queda pegado a {b['n']}"


@pytest.mark.parametrize("n", [2, 5])
def test_los_puntos_quedan_centrados_bajo_el_titulo_y_no_amontonados_arriba(chrome, n):
    # con 2 puntos arriba quedaba media pantalla vacía abajo (visto en la hoja de contacto)
    spec = {"titulo": {"texto": "Para llevarte"}, "duracion": 3.0,
            "puntos": [{"texto": f"Punto número {i + 1}", "cue": 0.2 * i} for i in range(n)]}
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), spec,
                                 escena.cargar_brand(None)) as (page, d):
        page.evaluate("t => window.seek(t)", d - 0.05)
        arriba, abajo = page.evaluate("""() => {
            const r = [...document.querySelectorAll('.punto')].map(e => e.getBoundingClientRect());
            return [Math.min(...r.map(x => x.top)), Math.max(...r.map(x => x.bottom))];
        }""")
    assert abs((arriba + abajo) / 2 - 670) <= 40, (arriba, abajo)


# --- casos de borde: lo que muestra la escena tiene que ser el dato ----------

def _al_final(chrome, tipo, spec, js):
    """Lleva la escena a su último cuadro, por el mismo camino que el render (un error
    de la plantilla sale como ContratoError), y devuelve lo que calcule `js`."""
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), {"duracion": 2.0, **spec},
                                 escena.cargar_brand(None)) as (page, d):
        escena._cuadro(page, d - 0.05)
        return page.evaluate(js)


CAJAS = """() => [...document.querySelectorAll('[data-caja]')].map(e => {
    const r = e.getBoundingClientRect();
    return {n: e.dataset.caja, x: r.left, y: r.top, w: r.width, h: r.height,
            px: parseFloat(getComputedStyle(e).fontSize), txt: e.textContent};
})"""

BARRAS = """() => [...document.querySelectorAll('.barra')].map(e => {
    const r = e.getBoundingClientRect();
    return {top: r.top, bottom: r.bottom, h: r.height};
})"""

PISO_PX = 24  # menos que esto no se lee a 1080p


def _choques(cajas):
    """Cajas fuera de pantalla o a menos de AIRE de otra."""
    malos = []
    for i, a in enumerate(cajas):
        if a["x"] < 0 or a["y"] < 0 or a["x"] + a["w"] > 1920 or a["y"] + a["h"] > 1080:
            malos.append(f"FUERA {a['n']}")
        for b in cajas[i + 1:]:
            if (a["x"] < b["x"] + b["w"] + AIRE and b["x"] < a["x"] + a["w"] + AIRE
                    and a["y"] < b["y"] + b["h"] + AIRE and b["y"] < a["y"] + a["h"] + AIRE):
                malos.append(f"PISA {a['n']} / {b['n']}")
    return malos


def _datos(barras, **extra):
    return {"titulo": {"texto": "Datos"}, "barras": barras, **extra}


def _valores(chrome, spec):
    return [c["txt"] for c in _al_final(chrome, "datos", spec, CAJAS) if c["n"].startswith("valor")]


def test_datos_muestra_los_decimales_del_dato_con_coma(chrome):
    spec = _datos([{"etiqueta": "Plazo fijo", "valor": 3.5, "cue": 0.1},
                   {"etiqueta": "Inflación", "valor": 0.4, "cue": 0.2},
                   {"etiqueta": "Dólar", "valor": 1234.56, "cue": 0.3}], sufijo=" %")
    assert _valores(chrome, spec) == ["3,5 %", "0,4 %", "1.234,56 %"]


def test_datos_un_entero_sigue_sin_decimales_y_con_punto_de_miles(chrome):
    spec = _datos([{"etiqueta": "A", "valor": 1000, "cue": 0.1},
                   {"etiqueta": "B", "valor": 17449, "cue": 0.2}], prefijo="$")
    assert _valores(chrome, spec) == ["$1.000", "$17.449"]


def test_datos_un_negativo_cuelga_debajo_de_la_linea_de_cero_y_el_cero_no_tiene_barra(chrome):
    spec = _datos([{"etiqueta": "Cero", "valor": 0, "cue": 0.1},
                   {"etiqueta": "Neg", "valor": -500, "cue": 0.2},
                   {"etiqueta": "Pos", "valor": 1000, "cue": 0.3}])
    cero, neg, pos = _al_final(chrome, "datos", spec, BARRAS)
    linea = _al_final(chrome, "datos", spec,
                      "() => document.querySelector('.base').getBoundingClientRect().top")
    assert cero["h"] == 0
    assert pos["bottom"] == pytest.approx(linea, abs=2), "la positiva se apoya en el cero"
    assert neg["top"] == pytest.approx(linea, abs=2), "la negativa sale del cero"
    assert neg["bottom"] > linea + 50, "y crece hacia abajo"
    assert neg["h"] == pytest.approx(pos["h"] / 2, rel=0.02), "-500 mide la mitad que 1000"
    assert "-500" in _valores(chrome, spec)


def test_datos_el_ruido_de_coma_flotante_no_se_muestra_como_decimales(chrome):
    spec = _datos([{"etiqueta": "A", "valor": 0.1 + 0.2, "cue": 0.1},       # 0.30000000000000004
                   {"etiqueta": "B", "valor": 1.1 + 2.2, "cue": 0.2},       # 3.3000000000000003
                   {"etiqueta": "C", "valor": 0.000001, "cue": 0.3}])
    assert _valores(chrome, spec) == ["0,3", "3,3", "0,000001"]


def test_datos_un_valor_que_se_veria_como_cero_falla_en_vez_de_mostrar_cero(chrome):
    spec = _datos([{"etiqueta": "Chico", "valor": 1e-7, "cue": 0.1},
                   {"etiqueta": "B", "valor": 0.3, "cue": 0.2}])
    with pytest.raises(escena.ContratoError, match="Chico.*se vería como 0"):
        _al_final(chrome, "datos", spec, CAJAS)


@pytest.mark.parametrize("prefijo, esperado", [("$", "-$500,5"), ("$ ", "-$ 500,5")])
def test_datos_el_signo_de_un_negativo_va_antes_del_prefijo(chrome, prefijo, esperado):
    spec = _datos([{"etiqueta": "Pérdida", "valor": -500.5, "cue": 0.1},
                   {"etiqueta": "Ganancia", "valor": 1200, "cue": 0.2}], prefijo=prefijo)
    assert _valores(chrome, spec)[0] == esperado


def test_datos_valores_menores_que_uno_usan_toda_la_altura(chrome):
    spec = _datos([{"etiqueta": "A", "valor": 0.4, "cue": 0.1},
                   {"etiqueta": "B", "valor": 0.2, "cue": 0.2}])
    a, b = _al_final(chrome, "datos", spec, BARRAS)
    assert a["h"] > 400, "la barra más alta no puede quedar aplastada por un piso de 1"
    assert b["h"] == pytest.approx(a["h"] / 2, rel=0.02)


@pytest.mark.parametrize("barra", [{"etiqueta": "Sin valor", "cue": 0.1},
                                   {"etiqueta": "Sin valor", "valor": "10", "cue": 0.1}])
def test_datos_una_barra_sin_valor_numerico_falla_nombrandola(chrome, barra):
    spec = _datos([barra, {"etiqueta": "B", "valor": 10, "cue": 0.2}])
    with pytest.raises(escena.ContratoError, match="Sin valor.*valor"):
        _al_final(chrome, "datos", spec, CAJAS)


@pytest.mark.parametrize("barras", [
    [{"etiqueta": f"{2000 + i}", "valor": 1000 * (i + 1), "cue": 0.05 * i} for i in range(12)],
    [{"etiqueta": c, "valor": v, "cue": 0.1 * i} for i, (c, v) in
     enumerate(zip("ABCDE", [123456789012, 987654321098, 555555555555, 999999999999, 999999999999]))],
], ids=["doce-barras", "doce-cifras"])
def test_datos_muchas_barras_o_numeros_largos_no_se_pisan_y_se_leen(chrome, barras):
    cajas = _al_final(chrome, "datos", _datos(barras, prefijo="$"), CAJAS)
    assert _choques(cajas) == []
    assert min(c["px"] for c in cajas) >= PISO_PX


def test_datos_si_los_numeros_no_entran_ni_al_piso_falla_claro(chrome):
    barras = [{"etiqueta": str(i), "valor": 999999999999, "cue": 0.01 * i} for i in range(30)]
    with pytest.raises(escena.ContratoError, match="no entran"):
        _al_final(chrome, "datos", _datos(barras), CAJAS)


def test_datos_un_rotulo_largo_no_achica_todo_por_debajo_del_piso(chrome):
    largo = "Administración Federal de Ingresos Públicos de la Nación"
    spec = _datos([{"etiqueta": largo, "valor": 10, "cue": 0.1},
                   {"etiqueta": "Señal añeja", "valor": 20, "cue": 0.2},
                   {"etiqueta": "Corto", "valor": 30, "cue": 0.3}])
    cajas = _al_final(chrome, "datos", spec, CAJAS)
    cats = [c for c in cajas if c["n"].startswith("categoria")]
    assert min(c["px"] for c in cats) >= PISO_PX
    assert _choques(cajas) == []


# --- desbordes: muchos elementos o textos largos ------------------------------

PX_NODOS = "() => [...document.querySelectorAll('.nodo .txt')].map(e => parseFloat(getComputedStyle(e).fontSize))"
LARGO = "Administración Federal de Ingresos Públicos de la Nación"


def _cadena(textos, flecha="rinde"):
    nodos = [{"id": str(i), "texto": t, "cue": 0.1 * i} for i, t in enumerate(textos)]
    flechas = [{"de": str(i), "a": str(i + 1), "texto": flecha, "cue": 0.5 + 0.1 * i}
               for i in range(len(textos) - 1)]
    return {"titulo": {"texto": "Flujo"}, "nodos": nodos, "flechas": flechas}


@pytest.mark.parametrize("spec", [
    _cadena([f"Nodo {i}" for i in range(4)]),
    _cadena([f"Nodo {i}" for i in range(6)]),
    _cadena([f"Paso {i}" for i in range(4)], flecha="se transforma en"),
    _cadena([LARGO, "Contribuyente monotributista", "Banco Central"]),
], ids=["4-nodos", "6-nodos", "4-etiquetas-largas", "3-con-texto-largo"])
def test_diagrama_con_muchos_nodos_o_texto_largo_entra_sin_pisar_flechas(chrome, spec):
    assert _choques(_al_final(chrome, "diagrama", spec, CAJAS)) == []
    assert min(_al_final(chrome, "diagrama", spec, PX_NODOS)) >= PISO_PX


LINEAS = """() => [...document.querySelectorAll('svg line')].map(l =>
    ['x1', 'y1', 'x2', 'y2'].map(k => +l.getAttribute(k)))"""


@pytest.mark.parametrize("textos", [
    # la fila de abajo arranca con un nodo más ancho que el último de arriba (QA2, D_S6)
    ["Ahorro", "Plazo fijo", "Intereses", "Capital nuevo", "Reinversión", "Patrimonio"],
    ["Sueldo", "Gastos fijos", "Ahorro", "Plazo fijo", "Intereses", "Capital nuevo", "Patrimonio"],
], ids=["S-6", "S-7"])
def test_diagrama_en_s_toda_flecha_es_horizontal_o_baja_derecho(chrome, textos):
    lineas = _al_final(chrome, "diagrama", _cadena(textos), LINEAS)
    torcidas = [l for l in lineas if abs(l[0] - l[2]) > 0.5 and abs(l[1] - l[3]) > 0.5]
    assert any(abs(l[1] - l[3]) > 0.5 for l in lineas), "no salió en dos filas"
    assert torcidas == []


def test_diagrama_que_no_entra_ni_en_dos_filas_falla_claro(chrome):
    with pytest.raises(escena.ContratoError, match="no entra"):
        _al_final(chrome, "diagrama", _cadena([f"Etapa número {i}" for i in range(14)]), CAJAS)


def test_diagrama_con_coordenadas_en_el_borde_queda_dentro_de_la_pantalla(chrome):
    spec = {"titulo": {"texto": "Coords"},
            "nodos": [{"id": "a", "texto": "Izquierda", "x": 0.02, "y": 0.5, "cue": 0.1},
                      {"id": "b", "texto": "Derecha", "x": 0.98, "y": 0.98, "cue": 0.2}]}
    nodos = [c for c in _al_final(chrome, "diagrama", spec, CAJAS) if c["n"].startswith("nodo")]
    assert len(nodos) == 2, "sin nodos, el chequeo de abajo pasa vacío"
    assert [c for c in _choques(nodos) if c.startswith("FUERA")] == []


TITULO_LARGO = "Cómo circula la plata entre el ahorro, el plazo fijo y los intereses compuestos"


@pytest.mark.parametrize("x, y, titulo", [
    (0.1, 0.0, "Cómo circula la plata"), (0.3, 0.12, "Cómo circula la plata"),
    (0.5, 0.2, "Cómo circula la plata"), (0.5, 0.0, TITULO_LARGO)],
    ids=["arriba-izquierda", "sobre-el-titulo", "pegado-abajo-del-titulo", "titulo-en-dos-renglones"])
def test_diagrama_con_coordenadas_arriba_no_tapa_el_titulo(chrome, x, y, titulo):
    spec = {"kicker": "Finanzas", "titulo": {"texto": titulo},
            "nodos": [{"id": "a", "texto": "Ahorro", "x": x, "y": y, "cue": 0.1},
                      {"id": "b", "texto": "Plazo fijo", "x": 0.7, "y": 0.7, "cue": 0.2}]}
    cajas = _al_final(chrome, "diagrama", spec, CAJAS)
    assert {c["n"] for c in cajas} >= {"titulo", "kicker", "nodo a"}
    assert [c for c in _choques(cajas) if "nodo a" in c] == []


# QA3 (02/10): 159 caracteres + kicker son 4 renglones de título, y el contenido
# arrancaba en una altura fija que la cabecera ya había pasado.
TITULO_4 = ("Cómo circula la plata cuando la dejás quieta en un plazo fijo durante treinta años "
            "seguidos y sin tocar nada de nada para ver cuánto crece de verdad el capital")


@pytest.mark.parametrize("tipo, spec", [
    ("diagrama", _cadena(["Capital inicial ahorrado", "Interés del primer año", "Capital nuevo",
                          "Interés sobre interés", "Patrimonio"])),
    ("diagrama", _cadena(["Ahorro mensual constante", "Plazo fijo tradicional", "Intereses cobrados",
                          "Capital nuevo acumulado", "Reinversión total", "Patrimonio"])),
    ("presentacion", {"puntos": [{"texto": f"Punto número {i + 1}", "cue": 0.1 * i} for i in range(6)]}),
    ("datos", _datos([{"etiqueta": "Año 0", "valor": 1000, "cue": 0.1},
                      {"etiqueta": "Año 30", "valor": 17449, "cue": 0.2, "destacar": True}])),
], ids=["diagrama-una-fila", "diagrama-en-s", "presentacion", "datos"])
def test_un_titulo_de_cuatro_renglones_no_queda_tapado_por_el_contenido(chrome, tipo, spec):
    spec = {**spec, "kicker": "Interés compuesto", "titulo": {"texto": TITULO_4}}
    cajas = _al_final(chrome, tipo, spec, CAJAS)
    titulo = next(c for c in cajas if c["n"] == "titulo")
    assert titulo["h"] > 3 * 76, "el título no salió en 4 renglones: el caso no se armó"
    assert [c for c in _choques(cajas) if "titulo" in c or "kicker" in c] == []


@pytest.mark.parametrize("tipo, spec", [
    ("diagrama", _cadena(["Capital", "Interés", "Capital nuevo"])),
    ("presentacion", {"puntos": [{"texto": "Uno", "cue": 0.1}, {"texto": "Dos", "cue": 0.2}]}),
    ("datos", _datos([{"etiqueta": "A", "valor": 1, "cue": 0.1}, {"etiqueta": "B", "valor": 2, "cue": 0.2}])),
], ids=["diagrama", "presentacion", "datos"])
def test_un_titulo_que_no_deja_lugar_al_contenido_falla_nombrando_el_titulo(chrome, tipo, spec):
    # 3 veces el de QA3: la cabecera sola llega al pie de la pantalla. Con 2 veces (8
    # renglones, hasta y=830) el contenido todavía entra achicado sin pisar: eso no es error.
    spec = {**spec, "kicker": "K", "titulo": {"texto": " ".join([TITULO_4] * 3)}}
    with pytest.raises(escena.ContratoError, match="título"):
        _al_final(chrome, tipo, spec, CAJAS)


@pytest.mark.parametrize("n", [8, 12])
def test_presentacion_con_muchos_puntos_entra_entera_y_se_lee(chrome, n):
    spec = {"titulo": {"texto": "Para llevarte"},
            "puntos": [{"texto": f"Punto número {i + 1}", "cue": 0.1 * i} for i in range(n)]}
    cajas = _al_final(chrome, "presentacion", spec, CAJAS)
    assert _choques(cajas) == []
    assert min(c["px"] for c in cajas) >= PISO_PX


def test_presentacion_con_demasiados_puntos_falla_claro(chrome):
    spec = {"titulo": {"texto": "Todo"},
            "puntos": [{"texto": f"Punto número {i + 1}", "cue": 0.05 * i} for i in range(30)]}
    with pytest.raises(escena.ContratoError, match="no entran"):
        _al_final(chrome, "presentacion", spec, CAJAS)


# --- imagen: varios dibujos y rótulos (R-4.7) ---------------------------------

def _imagen(dibujos, rotulos=(), **extra):
    specs = {"lampara": DIBUJOS / "lampara.svg", "semilla": DIBUJOS / "semilla.svg",
             "escudo": DIBUJOS / "escudo.svg"}
    return escena.resolver_dibujos({
        "titulo": {"texto": "Metáforas"},
        "dibujos": [{"id": d, "svg": str(specs[d]), "cue": 0.1 * i} for i, d in enumerate(dibujos)],
        "rotulos": [{"texto": t, "cue": 0.1 * i, "de": d} for i, (t, d) in enumerate(rotulos)],
        **extra,
    })


def test_imagen_con_tres_dibujos_y_rotulos_entra_sin_pisar_y_se_lee(chrome):
    spec = _imagen(["lampara", "semilla", "escudo"],
                   [("Idea", "lampara"), ("Crece", "semilla"), ("Protege", "escudo")])
    cajas = _al_final(chrome, "imagen", spec, CAJAS)
    assert _choques(cajas) == []
    # ".dibujo" es un contenedor de SVG, no texto propio (como ".nodo" en diagrama):
    # el piso de legibilidad aplica a lo que sí se lee (título, kicker, rótulos).
    con_texto = [c for c in cajas if not c["n"].startswith("dibujo")]
    assert len(con_texto) >= 4, "se armó mal el caso: faltan título/kicker/rótulos"
    assert min(c["px"] for c in con_texto) >= PISO_PX


def test_imagen_con_demasiados_dibujos_falla_claro(chrome):
    iconos = ["lampara", "semilla", "escudo"] * 4
    spec = _imagen(iconos)
    # B7: ids únicos (el caso ya repetía "lampara"/"semilla"/"escudo" como id antes de la
    # validación nueva; lo que se quiere ejercitar acá es la cantidad, no el id).
    for i, d in enumerate(spec["dibujos"]):
        d["id"] = f"{d['id']}{i}"
    with pytest.raises(escena.ContratoError, match="no entran"):
        _al_final(chrome, "imagen", spec, CAJAS)


# B2 (QA 03/10/2026, repro rotulos-largos.json): imagen.html nunca medía el ancho del
# rótulo; con texto largo se pisaba en silencio. Ahora se intenta acomodar en dos
# renglones dentro del ancho del dibujo; si ni así entra, falla nombrando el rótulo.

def test_imagen_con_rotulo_largo_se_acomoda_en_dos_renglones_sin_pisar(chrome):
    # dos dibujos: cada uno queda con una caja ancha (lado ~420 px), así un rótulo de
    # ~29 caracteres entra de sobra en dos renglones.
    spec = _imagen(["lampara", "semilla"],
                   [("Una idea que aparece de golpe", "lampara"),
                    ("Una idea que crece despacito", "semilla")])
    cajas = _al_final(chrome, "imagen", spec, CAJAS)
    assert _choques(cajas) == []
    rotulos = [c for c in cajas if c["n"].startswith("rotulo")]
    assert len(rotulos) == 2
    assert all("\n" in c["txt"] for c in rotulos), "un rótulo de 29 caracteres tiene que partirse en dos renglones"


# B5 (QA 03/10/2026, repro xy.json): "x"/"y" mixto (algunos dibujos con posición y otros
# sin ella) caía en el layout automático e ignoraba la posición dada en silencio; y con
# posiciones, dos dibujos podían pisarse sin que nada lo avisara.

def test_imagen_con_posicion_mixta_falla_claro(chrome):
    spec = _imagen(["lampara", "semilla"])
    spec["dibujos"][0]["x"] = spec["dibujos"][0]["y"] = 0.5
    # el segundo dibujo se queda SIN x/y: mixto
    with pytest.raises(escena.ContratoError, match="posici"):
        _al_final(chrome, "imagen", spec, CAJAS)


def test_imagen_con_dos_posiciones_que_se_pisan_falla_claro(chrome):
    # repro xy.json: dos dibujos casi en el mismo punto (x=0.5/y=0.6 y x=0.55/y=0.62)
    spec = _imagen(["lampara", "semilla"])
    spec["dibujos"][0]["x"], spec["dibujos"][0]["y"] = 0.5, 0.6
    spec["dibujos"][1]["x"], spec["dibujos"][1]["y"] = 0.55, 0.62
    with pytest.raises(escena.ContratoError, match="pisa"):
        _al_final(chrome, "imagen", spec, CAJAS)


def test_imagen_con_dos_posiciones_separadas_no_falla(chrome):
    spec = _imagen(["lampara", "semilla"])
    spec["dibujos"][0]["x"], spec["dibujos"][0]["y"] = 0.2, 0.6
    spec["dibujos"][1]["x"], spec["dibujos"][1]["y"] = 0.8, 0.6
    cajas = _al_final(chrome, "imagen", spec, CAJAS)
    assert _choques(cajas) == []


# Mejora de diseño (QA 03/10/2026): el rótulo era lo más chico de las cuatro plantillas
# (32 px, diagrama/datos 36 px) y siempre tenue, incluso el del dibujo en foco.

def test_imagen_el_rotulo_mide_al_menos_36px(chrome):
    spec = _imagen(["lampara", "semilla"], [("Idea", "lampara"), ("Crece", "semilla")])
    cajas = _al_final(chrome, "imagen", spec, CAJAS)
    rotulos = [c for c in cajas if c["n"].startswith("rotulo")]
    assert len(rotulos) == 2
    assert min(c["px"] for c in rotulos) >= 36


def test_imagen_el_rotulo_del_dibujo_en_foco_usa_el_color_principal(chrome):
    spec = _imagen(["lampara", "semilla"], [("Idea", "lampara"), ("Crece", "semilla")])
    # "semilla" entra después (cue mayor): es el foco al final.
    colores = _al_final(chrome, "imagen", spec,
                        "() => [...document.querySelectorAll('.rotulo')].map(e => getComputedStyle(e).color)")
    assert len(colores) == 2
    assert colores[0] != colores[1], "el rótulo del foco tiene que distinguirse del resto"


def test_imagen_con_id_de_dibujo_duplicado_falla_claro(chrome):
    # B7 (QA 03/10/2026): dos dibujos con el mismo id se pisaban en silencio en porId.
    spec = _imagen(["lampara", "semilla"])
    spec["dibujos"][1]["id"] = spec["dibujos"][0]["id"]
    with pytest.raises(escena.ContratoError, match="duplicad"):
        _al_final(chrome, "imagen", spec, CAJAS)


def test_imagen_con_rotulo_que_no_entra_ni_en_dos_renglones_falla_nombrandolo(chrome):
    # una sola palabra larga: no se puede partir en dos renglones, y no entra en una
    # caja de 420 px (la más generosa posible, un solo dibujo).
    texto = "Superextraordinariamenteelectromagnetico"
    spec = _imagen(["lampara"], [(texto, "lampara")])
    with pytest.raises(escena.ContratoError, match="Superextraordinariamenteelectromagnetico"):
        _al_final(chrome, "imagen", spec, CAJAS)


# --- determinismo en TODOS los cuadros, no sólo en cuatro tiempos -------------

CORTAS = {
    "portada": ("presentacion", {"kicker": "Finanzas", "titulo": {"texto": "El interés compuesto", "cue": 0.1},
                                 "subtitulo": {"texto": "Por qué la plata crece sola", "cue": 0.6},
                                 "duracion": 1.8}),
    "presentacion": ("presentacion", {**SPECS["presentacion"], "duracion": 1.8,
                                      "puntos": [{"texto": "Ganás intereses", "cue": 0.3},
                                                 {"texto": "sobre intereses", "cue": 0.9}]}),
    "diagrama": ("diagrama", {**SPECS["diagrama"], "duracion": 1.8,
                              "nodos": [{"id": "c", "texto": "Capital", "cue": 0.1},
                                        {"id": "i", "texto": "Interés", "cue": 0.5},
                                        {"id": "n", "texto": "Capital nuevo", "cue": 0.9}],
                              "flechas": [{"de": "c", "a": "i", "texto": "rinde", "cue": 0.3},
                                          {"de": "i", "a": "n", "cue": 0.7}]}),
    "datos": ("datos", {**SPECS["datos"], "duracion": 1.8,
                        "barras": [{"etiqueta": "Año 0", "valor": 1000, "cue": 0.1},
                                   {"etiqueta": "Año 10", "valor": 2594, "cue": 0.4},
                                   {"etiqueta": "Año 30", "valor": 17449.5, "cue": 0.7, "destacar": True}]}),
    "imagen": ("imagen", {**SPECS["imagen"], "duracion": 1.8,
                          "dibujos": [{"id": "lampara", "svg": str(DIBUJOS / "lampara.svg"), "cue": 0.1},
                                      {"id": "semilla", "svg": str(DIBUJOS / "semilla.svg"), "cue": 0.6}],
                          "rotulos": [{"texto": "Idea", "cue": 0.1, "de": "lampara"},
                                      {"texto": "Crece", "cue": 0.6, "de": "semilla"}]}),
}
CORTAS["imagen"] = (CORTAS["imagen"][0], escena.resolver_dibujos(CORTAS["imagen"][1]))


@pytest.mark.parametrize("nombre", CORTAS)
def test_todos_los_cuadros_salen_iguales_en_orden_y_mezclados(chrome, nombre):
    import random
    tipo, spec = CORTAS[nombre]
    ts = escena.tiempos_de_cuadros(spec["duracion"], 15)
    mezclados = list(ts)
    random.Random(7).shuffle(mezclados)
    brand = escena.cargar_brand(None)
    hashes = []
    for orden in (ts, mezclados):
        with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), spec, brand) as (page, _):
            hashes.append({t: _hash(page, t) for t in orden})
    distintos = [t for t in ts if hashes[0][t] != hashes[1][t]]
    assert distintos == [], f"{len(distintos)} de {len(ts)} cuadros dependen del orden"

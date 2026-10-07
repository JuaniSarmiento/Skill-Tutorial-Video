"""H5 (HITO3.md): la escena `arbol` contra Chrome.

Recursión que se ve: el árbol de llamadas crece llamada por llamada, y una llamada que
repite los mismos argumentos que una anterior entra directo resaltada en el acento (es
trabajo que se recalcula). Los nodos salen de una traza real de `fibonacci(5)`
(recursion.resolver + diagramas.trazar).
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import recursion  # noqa: E402

pytestmark = pytest.mark.integracion

FIBONACCI = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)\n"


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    d = tmp_path_factory.mktemp("arbol")
    (d / "fibonacci.py").write_text(FIBONACCI)
    return d


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _pasos(n, paso=0.4, desde=0.3):
    return [{"t": desde + paso * i} for i in range(n)]


def _spec(carpeta, n=5, duracion=8.0, **extra):
    spec = {"tipo": "arbol", "archivo": "fibonacci.py", "llamada": f"fibonacci({n})",
            "formato": "fib({n})", "titulo": {"texto": "Cuánto se repite fibonacci(5)"},
            "pasos": _pasos(15 if n == 5 else 5), "duracion": duracion, **extra}
    return recursion.resolver(spec, carpeta)


def _abrir(chrome, spec):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("arbol"), spec, escena.cargar_brand(None))


def _nodos(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('[data-caja^=nodo]')].map(e => {
        let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
        return {n: e.dataset.caja, op: o, txt: e.querySelector('.txt').textContent,
                color: getComputedStyle(e.querySelector('.txt')).color,
                borde: getComputedStyle(e).borderColor};
    })""")


def _visibles(page, t):
    return [n for n in _nodos(page, t) if n["op"] > 0.5]


# --- crece de a uno ------------------------------------------------------------------

def test_antes_de_la_primera_llamada_no_hay_ningun_nodo(carpeta, chrome):
    with _abrir(chrome, _spec(carpeta)) as (page, _):
        assert _visibles(page, 0.1) == []


def test_al_final_estan_los_quince_nodos_de_fibonacci_de_5(carpeta, chrome):
    spec = _spec(carpeta)
    with _abrir(chrome, spec) as (page, d):
        visibles = _visibles(page, d - 0.05)
    assert len(visibles) == 15


def test_el_arbol_crece_de_a_uno_con_cada_cue(carpeta, chrome):
    spec = _spec(carpeta)
    nodos = sorted(spec["nodos"], key=lambda n: n["t"])
    with _abrir(chrome, spec) as (page, _):
        antes = len(_visibles(page, nodos[4]["t"] - 0.02))
        despues = len(_visibles(page, nodos[4]["t"] + 0.25))
    assert despues == antes + 1


# --- resalta lo repetido --------------------------------------------------------------

def test_fibonacci_de_3_marca_la_segunda_llamada_a_fibonacci_de_1_en_el_acento(carpeta, chrome):
    spec = _spec(carpeta, n=3, duracion=4.0)
    brand = escena.cargar_brand(None)
    with _abrir(chrome, spec) as (page, d):
        finales = _visibles(page, d - 0.05)
    repetidos = [n for n in finales if n["txt"] == "fib(1)"]
    assert len(repetidos) == 2
    colores = sorted(n["color"] for n in repetidos)
    # la primera vez que se calcula fib(1) es trabajo nuevo (texto normal); la segunda es
    # trabajo que se recalcula, y entra directo resaltada en el acento
    assert colores == sorted([_rgb(brand["colores"]["texto"]), _rgb(brand["colores"]["acento"])])
    otros = [n for n in finales if n["txt"] != "fib(1)"]
    assert all(n["color"] != _rgb(brand["colores"]["acento"]) for n in otros)


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


# --- llena el área: tan grande como entre (H5 ronda 2, HITO3.md) --------------------

def test_con_pocas_hojas_los_nodos_son_mas_anchos_que_el_limite_viejo(carpeta, chrome):
    # fibonacci(3): 5 llamadas, 3 hojas -> antes el ancho de nodo tenía un tope fijo de 190px
    spec = _spec(carpeta, n=3, duracion=4.0)
    with _abrir(chrome, spec) as (page, d):
        escena._cuadro(page, d - 0.05)
        anchos = page.evaluate("() => [...document.querySelectorAll('.nodo')].map(e => e.getBoundingClientRect().width)")
    assert max(anchos) > 190, anchos


def test_con_menos_nodos_el_texto_es_mas_grande_que_con_muchos(carpeta, chrome):
    chico = _spec(carpeta, n=3, duracion=4.0)      # 5 llamadas
    grande = _spec(carpeta, n=5, duracion=8.0)     # 15 llamadas
    with _abrir(chrome, chico) as (page, d):
        escena._cuadro(page, d - 0.05)
        px_chico = page.evaluate(
            "() => parseFloat(getComputedStyle(document.querySelector('.nodo .txt')).fontSize)")
    with _abrir(chrome, grande) as (page, d):
        escena._cuadro(page, d - 0.05)
        px_grande = page.evaluate(
            "() => parseFloat(getComputedStyle(document.querySelector('.nodo .txt')).fontSize)")
    assert px_chico > px_grande, (px_chico, px_grande)


# --- determinismo ---------------------------------------------------------------------

def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(carpeta, chrome):
    spec = _spec(carpeta)
    ts = [0.2, 1.8, 3.9, 6.5]
    with _abrir(chrome, spec) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with _abrir(chrome, spec) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts)


def test_un_arbol_con_textos_que_no_entran_falla_claro(carpeta, chrome):
    spec = _spec(carpeta, formato="fibonacci de n = {n}, tardando mucho tiempo en volver")
    with pytest.raises(escena.ContratoError, match="no entra"):
        with _abrir(chrome, spec) as (page, d):
            escena._cuadro(page, d - 0.05)


# --- piso legible: nunca por debajo de 24 px (H9b, HITO3.md) -------------------------

def test_un_arbol_que_no_entra_legible_a_24px_falla_en_vez_de_achicarse_mas(carpeta, chrome):
    # fibonacci(6): 25 llamadas, 13 hojas. Con el piso viejo (14 px) esto renderizaba texto
    # a 20 px: se veía, pero no se leía en celular. El piso sube a 24 px (mismo mínimo que
    # D7 en verificar.py); si no entra legible a esa altura, la escena tiene que fallar en
    # vez de seguir achicando el texto.
    spec = recursion.resolver({"tipo": "arbol", "archivo": "fibonacci.py", "llamada": "fibonacci(6)",
                               "formato": "fib({n})", "titulo": {"texto": "x"},
                               "pasos": _pasos(25, paso=0.15), "duracion": 12.0}, carpeta)
    with pytest.raises(escena.ContratoError, match="no entra legible"):
        with _abrir(chrome, spec) as (page, d):
            escena._cuadro(page, d - 0.05)


def test_un_arbol_que_entra_a_24px_lo_hace_y_no_falla(carpeta, chrome):
    # fibonacci(5), el caso de referencia del resto del archivo, entra sin problema a 24 px.
    spec = _spec(carpeta, n=5, duracion=8.0)
    with _abrir(chrome, spec) as (page, d):
        escena._cuadro(page, d - 0.05)
        px = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.nodo .txt')).fontSize)")
    assert px >= 24, px

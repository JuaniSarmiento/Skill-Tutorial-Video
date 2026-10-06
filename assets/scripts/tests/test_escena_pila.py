"""H5 (HITO3.md): la escena `pila` contra Chrome.

Recursión que se ve: un marco por llamada que se apila en su cue y se desapila (con su
valor de retorno) poco después de la cue de su retorno. Los marcos salen de una traza
real de `factorial(4)` (recursion.resolver + diagramas.trazar), no de un spec inventado.
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import recursion  # noqa: E402

pytestmark = pytest.mark.integracion

FACTORIAL = "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n"


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    d = tmp_path_factory.mktemp("pila")
    (d / "factorial.py").write_text(FACTORIAL)
    return d


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _pasos(n, paso=0.5, desde=0.4):
    return [{"t": desde + paso * i} for i in range(n)]


def _spec(carpeta, n=4, duracion=8.0, **extra):
    pasos = _pasos(10)   # factorial(4): 5 llamadas + 5 retornos = 10 eventos
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": f"factorial({n})",
            "titulo": {"texto": "Cómo se desarma factorial(4)"}, "pasos": pasos,
            "duracion": duracion, **extra}
    return recursion.resolver(spec, carpeta)


def _abrir(chrome, spec):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("pila"), spec, escena.cargar_brand(None))


def _marcos(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('[data-caja^=marco]')].map(e => {
        let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
        return {n: e.dataset.caja, op: o, txt: e.querySelector('.txt').textContent,
                val: e.querySelector('.val').textContent, valOp: +getComputedStyle(e.querySelector('.val')).opacity};
    })""")


def _visibles(page, t):
    return [m for m in _marcos(page, t) if m["op"] > 0.5]


# --- se apila y se desapila ---------------------------------------------------------

def test_antes_de_la_primera_llamada_no_hay_ningun_marco(carpeta, chrome):
    with _abrir(chrome, _spec(carpeta)) as (page, _):
        assert _visibles(page, 0.1) == []


def test_en_el_fondo_de_la_recursion_los_cinco_marcos_estan_apilados(carpeta, chrome):
    spec = _spec(carpeta)
    marcos = spec["marcos"]
    t_fondo = max(m["tPush"] for m in marcos) + 0.1   # justo después de que entró el último (n=0)
    with _abrir(chrome, spec) as (page, _):
        visibles = _visibles(page, t_fondo)
    assert len(visibles) == 5
    assert {m["txt"] for m in visibles} == {"n = 4", "n = 3", "n = 2", "n = 1", "n = 0"}


def test_al_volver_el_marco_mas_profundo_muestra_su_valor_y_desaparece_primero(carpeta, chrome):
    spec = _spec(carpeta)
    marcos = {m["profundidad"]: m for m in spec["marcos"]}
    mas_hondo = marcos[4]   # n = 0, devuelve 1
    with _abrir(chrome, spec) as (page, _):
        justo_al_volver = next(m for m in _marcos(page, mas_hondo["tPop"] + 0.1) if m["n"] == "marco 4")
        ya_desapilado = _visibles(page, mas_hondo["tPop"] + 1.0)
    assert "1" in justo_al_volver["val"] and justo_al_volver["valOp"] > 0.5
    assert not any(m["n"] == "marco 4" for m in ya_desapilado)


def test_el_marco_raiz_desapila_ultimo_y_devuelve_24(carpeta, chrome):
    spec = _spec(carpeta)
    raiz = next(m for m in spec["marcos"] if m["profundidad"] == 0)
    with _abrir(chrome, spec) as (page, _):
        al_volver = next(m for m in _marcos(page, raiz["tPop"] + 0.1) if m["n"] == "marco 0")
    assert "24" in al_volver["val"]


# --- triangulación: otra llamada da otra cantidad y otros valores -------------------

def test_con_factorial_de_2_hay_tres_marcos_y_otros_valores(carpeta, chrome):
    spec_f = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(2)",
              "titulo": {"texto": "factorial(2)"}, "pasos": _pasos(6), "duracion": 6.0}
    spec = recursion.resolver(spec_f, carpeta)
    assert len(spec["marcos"]) == 3
    t_fondo = max(m["tPush"] for m in spec["marcos"]) + 0.1
    with _abrir(chrome, spec) as (page, _):
        visibles = _visibles(page, t_fondo)
    assert {m["txt"] for m in visibles} == {"n = 2", "n = 1", "n = 0"}


# --- llena el área y queda el resultado al terminar (H5 ronda 2, HITO3.md) ----------

def _resultado(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => {
        const e = document.querySelector('[data-caja=resultado]');
        if (!e) return null;
        let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
        return {texto: e.textContent, op: o, px: parseFloat(getComputedStyle(e).fontSize)};
    }""")


def test_el_marco_usa_casi_todo_el_ancho_disponible(carpeta, chrome):
    spec = _spec(carpeta)
    t_fondo = max(m["tPush"] for m in spec["marcos"]) + 0.1
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, t_fondo)
        ancho = page.evaluate("() => document.querySelector('.marco').getBoundingClientRect().width")
    # antes era un ancho fijo de 560px, muy por debajo del área disponible (~1920 - márgenes)
    assert ancho > 900, ancho


def test_el_texto_principal_del_marco_mide_al_menos_36px(carpeta, chrome):
    spec = _spec(carpeta)
    t_fondo = max(m["tPush"] for m in spec["marcos"]) + 0.1
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, t_fondo)
        px = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.marco .txt')).fontSize)")
    assert px >= 36, px


def test_el_valor_de_retorno_mide_al_menos_24px(carpeta, chrome):
    spec = _spec(carpeta)
    raiz = next(m for m in spec["marcos"] if m["profundidad"] == 0)
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, raiz["tPop"] + 0.1)
        px = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.marco .val')).fontSize)")
    assert px >= 24, px


def test_al_terminar_la_pila_queda_el_resultado_grande(carpeta, chrome):
    spec = _spec(carpeta)
    raiz = next(m for m in spec["marcos"] if m["profundidad"] == 0)
    with _abrir(chrome, spec) as (page, d):
        antes = _resultado(page, raiz["tPop"] + 0.1)
        despues = _resultado(page, d - 0.05)
    assert antes is None or antes["op"] < 0.5
    assert despues is not None and despues["op"] > 0.9
    assert "factorial(4)" in despues["texto"] and "24" in despues["texto"]
    assert despues["px"] >= 64, despues


def test_con_otra_llamada_el_resultado_final_cambia(carpeta, chrome):
    spec_f = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(2)",
              "titulo": {"texto": "factorial(2)"}, "pasos": _pasos(6), "duracion": 6.0}
    spec = recursion.resolver(spec_f, carpeta)
    with _abrir(chrome, spec) as (page, d):
        despues = _resultado(page, d - 0.05)
    assert "factorial(2)" in despues["texto"] and "2" in despues["texto"]
    assert "factorial(4)" not in despues["texto"]


# --- determinismo, igual que el resto de las plantillas -----------------------------

def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(carpeta, chrome):
    spec = _spec(carpeta)
    ts = [0.3, 1.5, 3.2, 5.8]
    with _abrir(chrome, spec) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with _abrir(chrome, spec) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts)


def test_una_pila_demasiado_alta_falla_claro(carpeta, chrome):
    # factorial(15): 16 llamadas, justo en el límite de recursion.py (MAX_MARCOS); no
    # entran 16 marcos legibles en una sola columna de 1080p, así que la propia escena
    # tiene que avisarlo (no recursion.resolver, que ya los deja pasar).
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(15)",
            "pasos": _pasos(32), "duracion": 20.0}
    resuelto = recursion.resolver(spec, carpeta)
    assert len(resuelto["marcos"]) == 16
    with pytest.raises(escena.ContratoError, match="no entra"):
        with _abrir(chrome, resuelto) as (page, d):
            escena._cuadro(page, d - 0.05)

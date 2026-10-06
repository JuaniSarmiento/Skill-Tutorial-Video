"""H4 (HITO3.md): la escena `codigo` contra Chrome.

Un tutorial de código sin grabar VS Code: el código real del archivo, tipeado a un ritmo
que entra antes de la cue siguiente, una línea resaltada, un diff por líneas y la salida
real del programa, todo función de t.
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import codigo  # noqa: E402
import escena  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

MEMO = ("memo = {}\n\n\ndef fibonacci_memo(n):\n    if n in memo:\n        return memo[n]\n"
        "    if n <= 1:\n        memo[n] = n\n    else:\n"
        "        memo[n] = fibonacci_memo(n - 1) + fibonacci_memo(n - 2)\n    return memo[n]\n")
SIMPLE = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)\n"
CON_MEMO = "def fib(n):\n    if n in memo:\n        return memo[n]\n    if n <= 1:\n        return n\n    memo[n] = fib(n - 1) + fib(n - 2)\n    return memo[n]\n"
LLAMADAS = "for n in [5, 10, 30]:\n    print(f'fibonacci({n}) -> {n * 89753} llamadas')\n"


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    d = tmp_path_factory.mktemp("codigo")
    (d / "fibonacci_memo.py").write_text(MEMO)
    (d / "simple.py").write_text(SIMPLE)
    (d / "con_memo.py").write_text(CON_MEMO)
    (d / "llamadas.py").write_text(LLAMADAS)
    (d / "larga.py").write_text("x = " + " + ".join(["valor_muy_largo"] * 12) + "\n")
    return d


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _spec(carpeta, **extra):
    spec = {"tipo": "codigo", "archivo": "fibonacci_memo.py", "desde": 4, "hasta": 11, "duracion": 9.0, **extra}
    return codigo.resolver(spec, carpeta)


def _abrir(chrome, spec):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("codigo"), spec, escena.cargar_brand(None))


# lo que se lee en el editor en t: los renglones de código que se ven (opacidad efectiva y alto)
LEER = """sel => [...document.querySelectorAll(sel)].map(e => {
    let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
    const r = e.getBoundingClientRect(), fila = e.closest('.fila') || e;
    return {texto: e.textContent, op: o, alto: fila.getBoundingClientRect().height,
            top: r.top, bottom: r.bottom, px: parseFloat(getComputedStyle(e).fontSize)};
})"""


def _leer(page, t, sel="[data-caja^='código']"):
    escena._cuadro(page, t)
    return page.evaluate(LEER, sel)


def _se_ve(page, t, sel="[data-caja^='código']"):
    return [x["texto"] for x in _leer(page, t, sel) if x["op"] > 0.5 and x["alto"] > 1]


def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


# --- el código es el del archivo -------------------------------------------------------

def test_sin_pasos_el_codigo_que_se_ve_es_identico_al_archivo(chrome, carpeta):
    with _abrir(chrome, _spec(carpeta)) as (page, d):
        assert _se_ve(page, d - 0.05) == [l for _, l in codigo.fragmento(carpeta / "fibonacci_memo.py", 4, 11)]


def test_el_codigo_es_grande_28_px_o_mas(chrome, carpeta):
    with _abrir(chrome, _spec(carpeta)) as (page, d):
        assert min(x["px"] for x in _leer(page, d - 0.05)) >= 28


def test_un_renglon_que_no_entra_ni_a_28_px_falla_nombrando_la_linea(chrome, carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "larga.py", "duracion": 3.0}, carpeta)
    with pytest.raises(escena.ContratoError, match="línea 1"):
        with _abrir(chrome, spec) as (page, _):
            escena._cuadro(page, 1.0)


# --- tipeo -----------------------------------------------------------------------------

TIPEO = [{"modo": "tipeo", "cue": 1.0, "t": 1.0}, {"modo": "resaltar", "lineas": "5", "cue": 4.0, "t": 4.0}]


def test_antes_del_tipeo_no_hay_codigo_y_al_empezar_va_por_la_mitad(chrome, carpeta):
    with _abrir(chrome, _spec(carpeta, pasos=TIPEO)) as (page, _):
        antes = "".join(_se_ve(page, 0.95))
        empezando = "".join(_se_ve(page, 1.6))
    assert antes == ""
    assert 0 < len(empezando) < len(MEMO)


def test_el_tipeo_termina_antes_de_la_cue_siguiente(chrome, carpeta):
    with _abrir(chrome, _spec(carpeta, pasos=TIPEO)) as (page, _):
        assert _se_ve(page, 3.95) == [l for _, l in codigo.fragmento(carpeta / "fibonacci_memo.py", 4, 11)]


def test_con_poco_tiempo_el_tipeo_se_apura_para_entrar_igual(chrome, carpeta):
    pasos = [{"modo": "tipeo", "cue": 1.0, "t": 1.0}, {"modo": "resaltar", "lineas": "5", "cue": 2.2, "t": 2.2}]
    with _abrir(chrome, _spec(carpeta, pasos=pasos)) as (page, _):
        assert _se_ve(page, 2.15) == [l for _, l in codigo.fragmento(carpeta / "fibonacci_memo.py", 4, 11)]


def test_por_renglon_cada_renglon_aparece_entero(chrome, carpeta):
    pasos = [{"modo": "tipeo", "por": "renglon", "cue": 1.0, "t": 1.0}]
    completo = [l for _, l in codigo.fragmento(carpeta / "fibonacci_memo.py", 4, 11)]
    with _abrir(chrome, _spec(carpeta, pasos=pasos)) as (page, _):
        a_medias = _se_ve(page, 1.5)
    assert 0 < len([x for x in a_medias if x]) < len([x for x in completo if x])
    assert a_medias == completo[:len(a_medias)]


# --- resaltar --------------------------------------------------------------------------

def _marca(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => { const m = document.querySelector('.marca'), r = m.getBoundingClientRect();
        return {op: +getComputedStyle(m).opacity, top: r.top, bottom: r.bottom}; }""")


def test_el_resaltado_entra_en_su_cue_y_cubre_las_lineas_pedidas(chrome, carpeta):
    pasos = [{"modo": "resaltar", "lineas": "5-6", "cue": 2.0, "t": 2.0}]
    with _abrir(chrome, _spec(carpeta, pasos=pasos)) as (page, _):
        antes = _marca(page, 1.95)
        marca = _marca(page, 2.8)
        filas = {x["texto"]: x for x in _leer(page, 2.8)}
    assert antes["op"] == 0
    assert marca["op"] == 1
    arriba, abajo = filas["    if n in memo:"], filas["        return memo[n]"]
    assert marca["top"] <= arriba["top"] + 2 and marca["bottom"] >= abajo["bottom"] - 2
    assert marca["bottom"] - marca["top"] < (abajo["bottom"] - arriba["top"]) * 1.6


def test_un_segundo_resaltado_se_mueve_a_sus_lineas(chrome, carpeta):
    pasos = [{"modo": "resaltar", "lineas": "5", "cue": 1.0, "t": 1.0},
             {"modo": "resaltar", "lineas": "11", "cue": 3.0, "t": 3.0}]
    with _abrir(chrome, _spec(carpeta, pasos=pasos)) as (page, _):
        marca = _marca(page, 4.0)
        ultima = {x["texto"]: x for x in _leer(page, 4.0)}["    return memo[n]"]
    assert abs(marca["top"] - ultima["top"]) <= 12


# --- diff ------------------------------------------------------------------------------

def test_el_diff_pasa_del_archivo_viejo_al_nuevo(chrome, carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "simple.py", "duracion": 6.0,
                            "pasos": [{"modo": "diff", "archivo": "con_memo.py", "cue": 1.5, "t": 1.5}]}, carpeta)
    with _abrir(chrome, spec) as (page, d):
        antes = _se_ve(page, 1.45)
        despues = _se_ve(page, d - 0.05)
        pestana = page.evaluate("() => document.querySelector('[data-caja=archivo]').textContent")
    assert antes == SIMPLE.splitlines()
    assert despues == CON_MEMO.splitlines()
    assert pestana == "con_memo.py"


def test_en_el_diff_lo_que_se_va_se_pone_rojo_antes_de_irse(chrome, carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "simple.py", "duracion": 6.0,
                            "pasos": [{"modo": "diff", "archivo": "con_memo.py", "cue": 1.5, "t": 1.5}]}, carpeta)
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, 1.8)
        clases = page.evaluate("""() => [...document.querySelectorAll('.fila')]
            .filter(f => f.textContent.includes('return fib(n - 1)')).map(f => f.className)""")
    assert clases and "quitada" in clases[0]


# --- salida ----------------------------------------------------------------------------

def _salida(carpeta, **paso):
    return _spec(carpeta, pasos=[{"modo": "salida", "ejecutar": "llamadas.py", "cue": 2.0, "t": 2.0, **paso}])


def test_la_salida_entra_en_su_cue_y_es_la_real(chrome, carpeta):
    real = codigo.ejecutar(carpeta / "llamadas.py")
    with _abrir(chrome, _salida(carpeta)) as (page, d):
        antes = _se_ve(page, 1.95, "[data-caja^='salida'], [data-caja=comando]")
        despues = _se_ve(page, d - 0.05, "[data-caja^='salida'], [data-caja=comando]")
    assert antes == []
    assert despues == ["$ python3 llamadas.py", *real["lineas"]]


def test_con_contar_el_ultimo_numero_de_cada_renglon_cuenta_hasta_el_real(chrome, carpeta):
    with _abrir(chrome, _salida(carpeta, contar=True)) as (page, d):
        contando = _se_ve(page, 3.0, "[data-caja^='salida']")
        final = _se_ve(page, d - 0.05, "[data-caja^='salida']")
    assert final == codigo.ejecutar(carpeta / "llamadas.py")["lineas"]
    ultimo = int(contando[-1].split()[-2])
    assert 0 < ultimo < 30 * 89753


# --- determinismo y la puerta ----------------------------------------------------------

COMPLETO = [{"modo": "tipeo", "cue": 0.5, "t": 0.5},
            {"modo": "resaltar", "lineas": "5-6", "cue": 3.5, "t": 3.5},
            {"modo": "salida", "ejecutar": "llamadas.py", "contar": True, "cue": 5.0, "t": 5.0}]


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(chrome, carpeta):
    spec = _spec(carpeta, pasos=COMPLETO)
    ts = [0.9, 2.1, 3.9, 5.6, 7.5]
    with _abrir(chrome, spec) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
        otra_vez = {t: _hash(page, t) for t in ts}
    with _abrir(chrome, spec) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == otra_vez == al_reves
    assert len(set(en_orden.values())) == len(ts)


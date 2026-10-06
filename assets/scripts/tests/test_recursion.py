"""H5 (HITO3.md): lo que las escenas `pila` y `arbol` preparan en Python antes de abrir
Chrome, desde una traza REAL (reusa `presentaciones/scripts/diagramas.trazar`).

No se inventa qué pasos tiene la recursión: se ejecuta la función y el dibujo sale del
registro. Si `pasos` no tiene un elemento por cada evento de la traza, falla claro.
"""
import pytest

import recursion

FACTORIAL = "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n"
FIBONACCI = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)\n"


@pytest.fixture
def carpeta(tmp_path):
    (tmp_path / "factorial.py").write_text(FACTORIAL)
    (tmp_path / "fibonacci.py").write_text(FIBONACCI)
    return tmp_path


def _pasos(n):
    return [{"t": 0.3 * i} for i in range(n)]


# --- pila --------------------------------------------------------------------------

def test_pila_de_factorial_de_4_tiene_un_marco_por_llamada_con_su_profundidad(carpeta):
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(4)", "pasos": _pasos(10)}
    out = recursion.resolver(spec, carpeta)
    marcos = out["marcos"]
    assert [m["profundidad"] for m in marcos] == [0, 1, 2, 3, 4]
    assert [m["texto"] for m in marcos] == ["n = 4", "n = 3", "n = 2", "n = 1", "n = 0"]


def test_pila_de_factorial_cada_marco_se_desapila_con_su_valor_de_retorno(carpeta):
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(4)", "pasos": _pasos(10)}
    marcos = recursion.resolver(spec, carpeta)["marcos"]
    por_profundidad = {m["profundidad"]: m for m in marcos}
    assert por_profundidad[4]["valor"] == "1"
    assert por_profundidad[0]["valor"] == "24"
    # cada marco entra (tPush) antes de salir (tPop), y el que entró último sale primero
    assert all(m["tPush"] < m["tPop"] for m in marcos)
    assert por_profundidad[4]["tPop"] < por_profundidad[3]["tPop"] < por_profundidad[0]["tPop"]


def test_pila_con_otra_llamada_triangula_otra_cantidad_de_marcos(carpeta):
    # factorial(2) desapila distinto que factorial(4): sin esto un Fake It (constante
    # "5 marcos") pasaría igual
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(2)", "pasos": _pasos(6)}
    marcos = recursion.resolver(spec, carpeta)["marcos"]
    assert len(marcos) == 3
    assert [m["texto"] for m in marcos] == ["n = 2", "n = 1", "n = 0"]


def test_pila_con_formato_propio_usa_ese_formato(carpeta):
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(2)",
            "formato": "factorial({n})", "pasos": _pasos(6)}
    marcos = recursion.resolver(spec, carpeta)["marcos"]
    assert [m["texto"] for m in marcos] == ["factorial(2)", "factorial(1)", "factorial(0)"]


def test_pila_con_menos_pasos_que_eventos_falla_nombrando_las_cantidades(carpeta):
    spec = {"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(4)", "pasos": _pasos(3)}
    with pytest.raises(ValueError, match="10.*3|3.*10"):
        recursion.resolver(spec, carpeta)


# --- arbol -------------------------------------------------------------------------

def test_arbol_de_fibonacci_de_5_tiene_quince_nodos(carpeta):
    spec = {"tipo": "arbol", "archivo": "fibonacci.py", "llamada": "fibonacci(5)", "pasos": _pasos(15)}
    nodos = recursion.resolver(spec, carpeta)["nodos"]
    assert len(nodos) == 15
    assert nodos[0]["texto"] == "n = 5"
    assert nodos[0]["padre"] is None
    assert nodos[0]["profundidad"] == 0


def test_arbol_de_fibonacci_de_3_marca_la_llamada_repetida(carpeta):
    # fibonacci(3) llama a fibonacci(1) dos veces (una bajo fibonacci(2), otra directo):
    # la segunda vez es trabajo repetido y tiene que distinguirse de la primera
    spec = {"tipo": "arbol", "archivo": "fibonacci.py", "llamada": "fibonacci(3)",
            "formato": "fib({n})", "pasos": _pasos(5)}
    nodos = recursion.resolver(spec, carpeta)["nodos"]
    assert len(nodos) == 5
    repetidos = [n for n in nodos if n["texto"] == "fib(1)"]
    assert len(repetidos) == 2
    assert [n["repetido"] for n in repetidos] == [False, True]


def test_arbol_con_menos_pasos_que_llamadas_falla_nombrando_las_cantidades(carpeta):
    spec = {"tipo": "arbol", "archivo": "fibonacci.py", "llamada": "fibonacci(5)", "pasos": _pasos(4)}
    with pytest.raises(ValueError, match="15.*4|4.*15"):
        recursion.resolver(spec, carpeta)


def test_otro_tipo_de_escena_no_se_toca(carpeta):
    spec = {"tipo": "diagrama", "nodos": []}
    assert recursion.resolver(spec, carpeta) == spec

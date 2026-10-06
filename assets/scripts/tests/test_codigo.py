"""H4 (HITO3.md): lo que la escena `codigo` prepara en Python antes de abrir Chrome.

El código sale de un archivo real (nunca tipeado en el spec), se tokeniza acá (no en el
navegador), el diff es por líneas (LCS) y la salida es la de ejecutar el programa de verdad.
"""
import pytest

import codigo

FUENTE = "memo = {}\n\n\ndef fib(n):\n    if n in memo:\n        return memo[n]\n    return n\n"


@pytest.fixture
def archivo(tmp_path):
    p = tmp_path / "fib.py"
    p.write_text(FUENTE)
    return p


# --- el fragmento ----------------------------------------------------------------------

def test_sin_rango_el_fragmento_es_el_archivo_entero_con_sus_numeros_de_linea(archivo):
    assert codigo.fragmento(archivo) == [(n, l) for n, l in enumerate(FUENTE.splitlines(), 1)]


def test_desde_y_hasta_recortan_y_conservan_los_numeros_reales(archivo):
    assert codigo.fragmento(archivo, desde=4, hasta=5) == [(4, "def fib(n):"), (5, "    if n in memo:")]


def test_lineas_es_un_atajo_de_desde_hasta(archivo):
    assert codigo.fragmento(archivo, lineas="5-6") == codigo.fragmento(archivo, desde=5, hasta=6)


@pytest.mark.parametrize("rango", [{"desde": 0}, {"hasta": 99}, {"desde": 6, "hasta": 5}, {"lineas": "5"}])
def test_un_rango_fuera_del_archivo_falla_nombrando_el_archivo(archivo, rango):
    with pytest.raises(ValueError, match="fib.py"):
        codigo.fragmento(archivo, **rango)


def test_un_archivo_que_no_existe_falla_con_su_ruta(tmp_path):
    with pytest.raises(ValueError, match="no_esta.py"):
        codigo.fragmento(tmp_path / "no_esta.py")


# --- tokens ----------------------------------------------------------------------------

def _texto(fila):
    return "".join(t for _, t in fila)


def test_cada_renglon_tokenizado_rearma_exacto_el_renglon_original():
    renglones = FUENTE.splitlines()
    filas = codigo.tokenizar(renglones, "fib.py")
    assert [_texto(f) for f in filas] == renglones


def test_las_palabras_clave_y_el_nombre_de_la_funcion_llevan_su_clase():
    (fila,) = codigo.tokenizar(["def fib(n):"], "fib.py")
    assert ["kw", "def"] in fila and ["fn", "fib"] in fila


def test_texto_numeros_comentarios_y_builtins_llevan_su_clase():
    (fila,) = codigo.tokenizar(['print("hola", 42)  # saludo'], "a.py")
    clases = {t: c for c, t in fila}
    assert clases["print"] == "bi"
    assert clases['"hola"'] == "str"
    assert clases["42"] == "num"
    assert clases["# saludo"] == "com"


def test_in_dentro_de_un_if_es_palabra_clave():
    (fila,) = codigo.tokenizar(["if n in memo:"], "a.py")
    assert ["kw", "in"] in fila


def test_un_renglon_vacio_no_tiene_tokens():
    assert codigo.tokenizar(["x = 1", "", "y = 2"], "a.py")[1] == []


def test_el_pseudocodigo_va_sin_resaltar():
    filas = codigo.tokenizar(["si n está en memo:", "    devolver memo[n]"], None)
    assert filas == [[["", "si n está en memo:"]], [["", "    devolver memo[n]"]]]


def test_los_renglones_vacios_del_final_se_conservan():
    renglones = ["x = 1", "", ""]
    filas = codigo.tokenizar(renglones, "a.py")
    assert [_texto(f) for f in filas] == renglones

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


# --- diff por líneas -------------------------------------------------------------------

def test_el_diff_marca_las_que_se_van_las_que_entran_y_las_que_quedan():
    antes = ["def f(n):", "    return g(n)", "fin"]
    despues = ["def f(n):", "    if n in memo:", "        return memo[n]", "    return g(n)"]
    assert codigo.diff_lineas(antes, despues) == [
        ("=", 0, 0), ("+", None, 1), ("+", None, 2), ("=", 1, 3), ("-", 2, None)]


def test_el_diff_de_dos_iguales_no_cambia_nada():
    assert codigo.diff_lineas(["a", "b"], ["a", "b"]) == [("=", 0, 0), ("=", 1, 1)]


def test_el_diff_contra_vacio_saca_todo_y_desde_vacio_agrega_todo():
    assert codigo.diff_lineas(["a", "b"], []) == [("-", 0, None), ("-", 1, None)]
    assert codigo.diff_lineas([], ["a"]) == [("+", None, 0)]


def test_un_renglon_cambiado_se_va_antes_de_que_entre_su_reemplazo():
    assert codigo.diff_lineas(["x = 1", "y"], ["x = 2", "y"]) == [("-", 0, None), ("+", None, 0), ("=", 1, 1)]


# --- la salida real --------------------------------------------------------------------

def test_la_salida_es_la_de_ejecutar_el_programa_de_verdad(tmp_path):
    p = tmp_path / "p.py"
    p.write_text("for n in [5, 10]:\n    print(f'{n} -> {n * n}')\n")
    assert codigo.ejecutar(p) == {"comando": "$ python3 p.py", "lineas": ["5 -> 25", "10 -> 100"]}


def test_corre_desde_una_carpeta_neutra_con_sus_vecinos_y_sin_rutas_personales(tmp_path):
    (tmp_path / "vecino.py").write_text("VALOR = 7\n")
    p = tmp_path / "p.py"
    p.write_text("import os, vecino\nprint(vecino.VALOR)\nprint(os.getcwd())\nprint(__file__)\n")
    lineas = codigo.ejecutar(p)["lineas"]
    assert lineas[0] == "7"
    assert str(tmp_path) not in "\n".join(lineas) and "/tmp" not in "\n".join(lineas)


def test_un_programa_que_no_termina_falla_en_vez_de_colgar(tmp_path):
    p = tmp_path / "p.py"
    p.write_text("while True:\n    pass\n")
    with pytest.raises(ValueError, match="p.py"):
        codigo.ejecutar(p, timeout=1)

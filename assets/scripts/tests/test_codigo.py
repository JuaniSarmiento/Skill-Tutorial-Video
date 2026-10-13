"""H4 (HITO3.md): lo que la escena `codigo` prepara en Python antes de abrir Chrome.

El código sale de un archivo real (nunca tipeado en el spec), se tokeniza acá (no en el
navegador), el diff es por líneas (LCS) y la salida es la de ejecutar el programa de verdad.
"""
import shutil

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


# --- la salida real de JavaScript y TypeScript ----------------------------------------
# Programación IV es React + TypeScript: una salida de un .ts mostrada como
# "$ python3 x.py" le miente al alumno. Cada lenguaje corre con su intérprete y la
# terminal muestra el comando que el alumno escribiría.

necesita_node = pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")


def _tsx_falso(proyecto):
    """Un `node_modules/.bin/tsx` que corre el archivo con node: prueba que se encuentra y
    se usa el tsx DEL PROYECTO (no uno global ni `npx` bajando de la red)."""
    bin_ = proyecto / "node_modules" / ".bin"
    bin_.mkdir(parents=True)
    tsx = bin_ / "tsx"
    tsx.write_text('#!/bin/sh\nexec node "$@"\n')
    tsx.chmod(0o755)


@necesita_node
def test_un_js_corre_con_node_y_la_terminal_lo_dice(tmp_path):
    p = tmp_path / "p.js"
    p.write_text("for (const n of [5, 10]) console.log(`${n} -> ${n * n}`);\n")
    assert codigo.ejecutar(p) == {"comando": "$ node p.js", "lineas": ["5 -> 25", "10 -> 100"]}


@necesita_node
def test_un_ts_corre_con_el_tsx_del_proyecto_y_la_terminal_dice_npx_tsx(tmp_path):
    _tsx_falso(tmp_path)
    codigo_dir = tmp_path / "src"
    codigo_dir.mkdir()
    p = codigo_dir / "cache.ts"
    p.write_text("console.log('pedidos:', 1);\n")
    assert codigo.ejecutar(p) == {"comando": "$ npx tsx cache.ts", "lineas": ["pedidos: 1"]}


@necesita_node
def test_node_modules_no_se_copia_pero_se_resuelve_y_no_quedan_rutas_personales(tmp_path):
    _tsx_falso(tmp_path)
    (tmp_path / "node_modules" / "libreria").mkdir()
    (tmp_path / "node_modules" / "libreria" / "index.js").write_text("module.exports = 42;\n")
    p = tmp_path / "p.js"
    p.write_text("console.log(require('libreria'));\nconsole.log(process.cwd());\n")
    lineas = codigo.ejecutar(p)["lineas"]
    assert lineas[0] == "42"
    assert str(tmp_path) not in "\n".join(lineas) and "/tmp" not in "\n".join(lineas)


def test_un_ts_sin_tsx_instalado_falla_diciendo_como_instalarlo(tmp_path):
    p = tmp_path / "p.ts"
    p.write_text("console.log(1);\n")
    with pytest.raises(ValueError, match="tsx"):
        codigo.ejecutar(p)


def test_un_lenguaje_que_no_sabe_correr_falla_nombrando_la_extension(tmp_path):
    p = tmp_path / "p.rb"
    p.write_text("puts 1\n")
    with pytest.raises(ValueError, match=r"\.rb"):
        codigo.ejecutar(p)


# --- el spec de la escena --------------------------------------------------------------

NUEVO = "memo = {}\n\n\ndef fib(n):\n    if n in memo:\n        return memo[n]\n    memo[n] = n\n    return n\n"


@pytest.fixture
def carpeta(archivo):
    (archivo.parent / "nuevo.py").write_text(NUEVO)
    (archivo.parent / "corre.py").write_text("print('hola')\nprint(2692537, 'llamadas')\n")
    return archivo.parent


def _texto_filas(spec, cual):
    return [(f[cual], _texto(f["tokens"])) for f in spec["_codigo"]["filas"] if f[cual] is not None]


def test_el_codigo_de_la_escena_es_el_del_archivo_con_sus_numeros(carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fib.py", "desde": 4, "hasta": 6}, carpeta)
    assert spec["_codigo"]["archivo"] == "fib.py"
    assert _texto_filas(spec, "antes") == codigo.fragmento(carpeta / "fib.py", 4, 6)
    assert _texto_filas(spec, "despues") == codigo.fragmento(carpeta / "fib.py", 4, 6)


def test_con_diff_las_filas_son_la_union_y_cada_lado_es_su_archivo(carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fib.py",
                            "pasos": [{"modo": "diff", "archivo": "nuevo.py", "cue": 1.0}]}, carpeta)
    assert _texto_filas(spec, "antes") == codigo.fragmento(carpeta / "fib.py")
    assert _texto_filas(spec, "despues") == codigo.fragmento(carpeta / "nuevo.py")
    assert spec["pasos"][0]["_archivo"] == "nuevo.py"


def test_resaltar_apunta_a_las_filas_de_lo_que_se_ve_en_ese_momento(carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fib.py", "pasos": [
        {"modo": "resaltar", "lineas": "7", "cue": 0.5},                  # "    return n" del original
        {"modo": "diff", "archivo": "nuevo.py", "cue": 1.0},
        {"modo": "resaltar", "lineas": "7-8", "cue": 2.0}]}, carpeta)     # "memo[n] = n" y "return n" del nuevo
    filas = spec["_codigo"]["filas"]
    a0, a1 = spec["pasos"][0]["_filas"]
    b0, b1 = spec["pasos"][2]["_filas"]
    assert [_texto(f["tokens"]) for f in filas[a0:a1 + 1]] == ["    return n"]
    assert [_texto(f["tokens"]) for f in filas[b0:b1 + 1]] == ["    memo[n] = n", "    return n"]


def test_un_resaltado_fuera_de_lo_que_se_ve_falla(carpeta):
    with pytest.raises(ValueError, match="9"):
        codigo.resolver({"tipo": "codigo", "archivo": "fib.py", "desde": 4, "hasta": 6,
                         "pasos": [{"modo": "resaltar", "lineas": "9", "cue": 0.5}]}, carpeta)


def test_la_salida_es_la_real_del_programa_que_nombra_el_paso(carpeta):
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fib.py",
                            "pasos": [{"modo": "salida", "ejecutar": "corre.py", "cue": 1.0}]}, carpeta)
    assert spec["pasos"][0]["_salida"] == {"comando": "$ python3 corre.py", "lineas": ["hola", "2692537 llamadas"]}


def test_el_pseudocodigo_explicito_va_sin_archivo_y_sin_resaltar(carpeta):
    spec = codigo.resolver({"tipo": "codigo", "pseudocodigo": "si n en memo:\n    devolver memo[n]"}, carpeta)
    assert spec["_codigo"]["archivo"] == "pseudocódigo"
    assert [f["tokens"] for f in spec["_codigo"]["filas"]] == [[["", "si n en memo:"]], [["", "    devolver memo[n]"]]]


@pytest.mark.parametrize("spec, dice", [
    ({"tipo": "codigo"}, "archivo"),
    ({"tipo": "codigo", "archivo": "fib.py", "pseudocodigo": "x"}, "pseudocodigo"),
    ({"tipo": "codigo", "archivo": "fib.py", "_codigo": {}}, "_codigo"),
    ({"tipo": "codigo", "archivo": "fib.py", "pasos": [{"modo": "bailar", "cue": 1}]}, "tipeo"),
    ({"tipo": "codigo", "archivo": "fib.py", "pasos": [{"modo": "diff", "archivo": "nuevo.py", "cue": 1},
                                                       {"modo": "tipeo", "cue": 2}]}, "antes del diff"),
    ({"tipo": "codigo", "archivo": "fib.py", "pasos": [{"modo": "resaltar", "lineas": "1", "cue": 2, "t": 2},
                                                       {"modo": "resaltar", "lineas": "1", "cue": 1, "t": 1}]}, "orden"),
])
def test_un_spec_mal_armado_falla_diciendo_que_falta(carpeta, spec, dice):
    with pytest.raises(ValueError, match=dice):
        codigo.resolver(spec, carpeta)


def test_resolver_no_toca_el_spec_original(carpeta):
    spec = {"tipo": "codigo", "archivo": "fib.py", "pasos": [{"modo": "resaltar", "lineas": "1", "cue": 1}]}
    codigo.resolver(spec, carpeta)
    assert spec == {"tipo": "codigo", "archivo": "fib.py", "pasos": [{"modo": "resaltar", "lineas": "1", "cue": 1}]}


# --- el ejemplo documentado ------------------------------------------------------------

def test_el_guion_de_ejemplo_trae_codigo_y_contador_y_sus_cues_se_dicen():
    import json
    from pathlib import Path
    ejemplo = Path(__file__).resolve().parents[2] / "guion-ejemplo"
    g = json.loads((ejemplo / "tutorial-memoizacion.json").read_text())
    escenas = [(s["escena"], s["texto"].lower()) for s in g["segmentos"] if "escena" in s]
    assert {"codigo", "contador"} <= {e["tipo"] for e, _ in escenas}
    for e, texto in escenas:
        cues = [p["cue"] for p in e.get("pasos", [])] + ([e["cue"]] if "cue" in e else [])
        assert all(c.lower() in texto for c in cues if isinstance(c, str)), (cues, texto)
        if e["tipo"] == "codigo":   # las rutas del guion son relativas a la raíz del tutorial
            assert codigo.resolver(e, ejemplo)["_codigo"]["filas"]

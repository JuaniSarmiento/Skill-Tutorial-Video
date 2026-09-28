"""term-vscode.py usa `Path(__file__).parent` para agregar la carpeta de
scripts a sys.path, pero le falta el `from pathlib import Path`. Eso rompe
con NameError apenas se importa el módulo, antes de llegar a main().
"""
import importlib.util
from pathlib import Path


def _cargar_term_vscode():
    spec = importlib.util.spec_from_file_location(
        "term_vscode", Path(__file__).parent.parent / "term-vscode.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_el_modulo_se_importa_sin_nameerror():
    mod = _cargar_term_vscode()
    assert hasattr(mod, "main")

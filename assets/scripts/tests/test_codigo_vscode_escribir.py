"""Escape antes de cada Return al tipear código, para que el popup de
autocompletado (IntelliSense) de VS Code no se coma el salto de línea y
pegue dos líneas de código sin separador entre ellas.

No es un bug exclusivo de Windows -el popup también existe en Linux- pero
se encontró durante las pruebas de adaptación a Windows.
"""
import importlib.util
from pathlib import Path

# El script se llama "codigo-vscode.py" (con guion): no es un nombre de
# módulo válido para `import`, así que se carga por ruta.
_spec = importlib.util.spec_from_file_location(
    "codigo_vscode", Path(__file__).parent.parent / "codigo-vscode.py",
)
cv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cv)


def test_escribe_escape_antes_de_cada_return_entre_lineas(monkeypatch):
    teclas = []
    monkeypatch.setattr(cv, "tecla", lambda *combo, pausa=0.25: teclas.append(combo))
    monkeypatch.setattr(cv, "tipear", lambda texto, delay_ms=22: None)
    monkeypatch.setattr(cv.time, "sleep", lambda s: None)

    cv.escribir(["primera linea", "segunda linea"], ms=10)

    # Antes de cada Return que separa líneas tiene que haber un Escape,
    # para cerrar el popup de autocompletado si está abierto.
    idx_return = teclas.index(("Return",))
    assert teclas[idx_return - 1] == ("Escape",)


def test_una_sola_linea_no_manda_ni_escape_ni_return(monkeypatch):
    teclas = []
    monkeypatch.setattr(cv, "tecla", lambda *combo, pausa=0.25: teclas.append(combo))
    monkeypatch.setattr(cv, "tipear", lambda texto, delay_ms=22: None)
    monkeypatch.setattr(cv.time, "sleep", lambda s: None)

    cv.escribir(["unica linea"], ms=10)

    assert ("Return",) not in teclas
    assert ("Escape",) not in teclas

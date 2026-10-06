"""H5: la escena `arbol` en la puerta `check` de verificar.py.

Aparte de test_escena_arbol.py porque verificar_escena abre su propio Chrome (Playwright
sync no se anida con el Chrome de módulo de ese archivo; ver test_escena_codigo_render.py).
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import recursion  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

FIBONACCI = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)\n"


def test_el_arbol_de_fibonacci_5_pasa_la_puerta_de_verificar(tmp_path):
    (tmp_path / "fibonacci.py").write_text(FIBONACCI)
    pasos = [{"t": 0.3 + 0.4 * i} for i in range(15)]
    spec = recursion.resolver({"tipo": "arbol", "archivo": "fibonacci.py", "llamada": "fibonacci(5)",
                              "formato": "fib({n})", "titulo": {"texto": "Cuánto se repite fibonacci(5)"},
                              "pasos": pasos, "duracion": 8.0}, tmp_path)
    hallazgos = verificar.verificar_escena(escena.ruta_plantilla("arbol"), spec, nombre="arbol")
    assert hallazgos == [], verificar.informe(hallazgos)

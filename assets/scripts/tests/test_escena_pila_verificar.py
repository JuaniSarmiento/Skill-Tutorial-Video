"""H5: la escena `pila` en la puerta `check` de verificar.py.

Aparte de test_escena_pila.py porque verificar_escena abre su propio Chrome (Playwright
sync no se anida con el Chrome de módulo de ese archivo; ver test_escena_codigo_render.py).
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import recursion  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

FACTORIAL = "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n"


def test_la_pila_de_factorial_4_pasa_la_puerta_de_verificar(tmp_path):
    (tmp_path / "factorial.py").write_text(FACTORIAL)
    pasos = [{"t": 0.4 + 0.5 * i} for i in range(10)]
    spec = recursion.resolver({"tipo": "pila", "archivo": "factorial.py", "llamada": "factorial(4)",
                              "titulo": {"texto": "Cómo se desarma factorial(4)"},
                              "pasos": pasos, "duracion": 8.0}, tmp_path)
    hallazgos = verificar.verificar_escena(escena.ruta_plantilla("pila"), spec, nombre="pila")
    assert hallazgos == [], verificar.informe(hallazgos)

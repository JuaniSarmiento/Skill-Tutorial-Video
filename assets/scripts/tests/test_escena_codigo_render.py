"""H4: la escena `codigo` en la puerta `check` de verificar.py (H2), el render y los CLI.

Aparte de test_escena_codigo.py porque verificar_escena y render abren su propio Chrome (Playwright
sync no se anida con el Chrome de módulo de ese archivo).
"""
import pytest

pytest.importorskip("playwright")
import codigo  # noqa: E402
import escena  # noqa: E402
import verificar  # noqa: E402
from test_escena_codigo import COMPLETO, LLAMADAS, MEMO  # noqa: E402

pytestmark = pytest.mark.integracion


# con título, 8 líneas de código más 4 de terminal no entran a 28 px (falla a propósito):
# el caso con título va sin salida
SIN_SALIDA = [p for p in COMPLETO if p["modo"] != "salida"]


@pytest.mark.parametrize("cabecera, pasos", [({}, COMPLETO),
                                             ({"titulo": {"texto": "Memoización"}, "kicker": "Recursividad"}, SIN_SALIDA)])
def test_la_escena_completa_pasa_la_puerta_de_verificar(tmp_path, cabecera, pasos):
    (tmp_path / "fibonacci_memo.py").write_text(MEMO)
    (tmp_path / "llamadas.py").write_text(LLAMADAS)
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fibonacci_memo.py", "desde": 4, "hasta": 11,
                            "duracion": 9.0, "pasos": pasos, **cabecera}, tmp_path)
    assert verificar.verificar_escena(escena.ruta_plantilla("codigo"), spec) == []

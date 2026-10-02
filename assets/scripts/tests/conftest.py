"""Deja los scripts de assets/scripts/ importables desde los tests.

No hay infraestructura de tests previa en este repo (skill instalada como
carpeta de scripts sueltos, no como paquete). Esto es lo mínimo para poder
importar plataforma.py, rec.py, editar.py, etc. con pytest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integracion: abre Chrome de verdad y renderiza (necesita playwright: "
        "uv run --with pytest --with playwright ...). Filtrar con -m 'not integracion'.",
    )

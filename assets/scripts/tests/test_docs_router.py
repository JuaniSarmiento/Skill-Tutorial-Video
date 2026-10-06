"""H3 del Hito 3: SKILL.md pasó a ser un router corto, con guías en `references/`
que se cargan bajo demanda. Esto prueba que el router cumple lo que promete:

- tiene una tabla de ruteo con filas reales ("si vas a hacer X, leé references/Y.md"),
- cada archivo que esa tabla nombra existe de verdad (ningún link roto), y
- el archivo se mantiene corto (<=200 líneas): si crece de nuevo, deja de cumplir
  el objetivo de la rebanada (que cada agente lea ~120-180 líneas en vez de ~800).
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SKILL = RAIZ / "SKILL.md"

# una fila de la tabla de ruteo es "| ... algo ... | `references/archivo.md` |"
_RE_FILA_RUTEO = re.compile(r"^\|.+\|\s*`(references/[\w\-]+\.md)`\s*\|\s*$", re.MULTILINE)


def _archivos_de_la_tabla_de_ruteo(texto: str) -> list[str]:
    return _RE_FILA_RUTEO.findall(texto)


def test_la_tabla_de_ruteo_tiene_filas():
    archivos = _archivos_de_la_tabla_de_ruteo(SKILL.read_text())
    assert len(archivos) >= 5, (
        "SKILL.md no tiene una tabla de ruteo reconocible "
        "(filas '| ... | `references/archivo.md` |')"
    )


def test_cada_archivo_de_la_tabla_de_ruteo_existe():
    texto = SKILL.read_text()
    archivos = _archivos_de_la_tabla_de_ruteo(texto)
    faltantes = [a for a in archivos if not (RAIZ / a).exists()]
    assert faltantes == [], f"la tabla de ruteo nombra archivos que no existen: {faltantes}"


def test_skill_md_tiene_a_lo_sumo_200_lineas():
    n = len(SKILL.read_text().splitlines())
    assert n <= 200, f"SKILL.md tiene {n} líneas; el router debe quedar en <=200"

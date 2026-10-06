"""Los comandos que da la documentación tienen que andar copiados tal cual.

faster-whisper 1.2.1 rompe con av 19 (`TypeError: open() got an unexpected keyword
argument 'metadata_errors'`, medido por QA el 02/10/2026). Todo comando documentado
que la instala tiene que fijar av<19, si no el que lo copia se come ese error.

Desde H3 del Hito 3, SKILL.md es un router corto y los comandos de ejemplo viven
repartidos en `references/*.md` (escenas, grabación, edición...): hay que barrerlos
también, si no un comando sin pin en una referencia se escapa del chequeo.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DOCUMENTOS = [
    RAIZ / "SKILL.md",
    RAIZ / "README.md",
    *sorted((RAIZ / "references").glob("*.md")),
    *sorted((RAIZ / "assets" / "scripts").glob("*.py")),
]


def test_todo_comando_que_instala_faster_whisper_fija_av_menor_que_19():
    sin_pin = [f"{p.relative_to(RAIZ)}:{i}: {linea.strip()}"
               for p in DOCUMENTOS
               for i, linea in enumerate(p.read_text().splitlines(), 1)
               if "--with faster-whisper" in linea and "av<19" not in linea]
    assert sin_pin == []

"""R-5.8: cada regla numerada de la sección Director (references/director.md) tiene
su chequeo en `editar.py revisar` — se referencian con el mismo ID (D1, D2, ...)
como comentario, igual que test_docs_comandos.py compara documentación con código.

Desde H3 del Hito 3, SKILL.md es un router corto y la sección Director completa
vive en `references/director.md` (ver la tabla de ruteo en SKILL.md).

R-5.8 más fuerte: no alcanza con que el ID aparezca en un docstring o comentario
(eso lo cumple cualquier mención de paso). Cada Dn tiene que estar en
`editar.CHEQUEOS`, el registro que `revisar()` recorre de verdad para correr los
chequeos — se comprueba reemplazando cada entrada por un espía y viendo que
`revisar()` lo llama.
"""
import json
import re
from pathlib import Path

import pytest

import editar

RAIZ = Path(__file__).resolve().parents[3]
SKILL = RAIZ / "references" / "director.md"
EDITAR = RAIZ / "assets" / "scripts" / "editar.py"

_RE_REGLA = re.compile(r"^- \*\*(D\d+)\*\*", re.MULTILINE)


def _seccion_director(texto: str) -> str:
    fin = texto.find("\n## ", texto.find("## Director") + 1)
    return texto[texto.find("## Director"):fin if fin != -1 else len(texto)]


def test_la_seccion_director_existe_en_skill_md():
    assert "## Director" in SKILL.read_text(), "references/director.md no tiene una sección '## Director'"


def test_la_seccion_director_declara_reglas_numeradas():
    seccion = _seccion_director(SKILL.read_text())
    reglas = _RE_REGLA.findall(seccion)
    assert reglas != [], "la sección Director no declaró ninguna regla numerada (- **D1** ...)"


def _reglas_sin_check(seccion: str, codigo: str) -> list[str]:
    return [r for r in _RE_REGLA.findall(seccion) if r not in codigo]


def test_una_regla_con_su_id_como_comentario_en_el_codigo_tiene_check():
    seccion = "- **D1**: no hay tiempo muerto.\n"
    codigo = "def _freezes():  # D1: mide el tiempo muerto\n    pass\n"
    assert _reglas_sin_check(seccion, codigo) == []


def test_una_regla_sin_su_id_en_el_codigo_se_reporta_sin_check():
    seccion = "- **D1**: no hay tiempo muerto.\n- **D9**: regla inventada sin implementar.\n"
    codigo = "def _freezes():  # D1: mide el tiempo muerto\n    pass\n"
    assert _reglas_sin_check(seccion, codigo) == ["D9"]


def test_cada_regla_del_director_tiene_su_check_en_revisar():
    """R-5.8 más fuerte: no alcanza con que el ID aparezca en un comentario o
    docstring (eso lo cumple cualquier mención de paso, sin atar nada). Cada Dn
    de SKILL.md tiene que ser una clave de `editar.CHEQUEOS`, el registro que
    `revisar()` usa de verdad (ver test_revisar_llama_a_cada_chequeo_del_registro,
    más abajo, para la prueba de que lo ejecuta)."""
    seccion = _seccion_director(SKILL.read_text())
    reglas = _RE_REGLA.findall(seccion)
    sin_check = [r for r in reglas if r not in editar.CHEQUEOS]
    assert sin_check == [], f"reglas sin chequeo registrado en editar.CHEQUEOS: {sin_check}"


# --- la prueba de que CHEQUEOS no es sólo una lista: revisar() lo recorre de verdad ---

@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "videos" / "v09").mkdir(parents=True)
    return tmp_path


def test_revisar_usa_el_resultado_de_cada_chequeo_del_registro(raiz, monkeypatch):
    """NOTE 9 (QA): no alcanza con probar que revisar() LLAMA a cada entrada de
    CHEQUEOS (un mutante puede llamarla y descartar el resultado). Cada espía
    devuelve una marca bien distinguible, y el test comprueba que esa marca
    llega de verdad a `hallazgos` (lo que termina en el informe)."""
    (raiz / "videos" / "v09" / "video-argentina.mp4").write_bytes(b"")
    (raiz / "videos" / "v09" / "voz-argentina.wav").write_bytes(b"")
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a", "rol": "gancho"}
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir()
    (escenas_dir / "00.json").write_text(json.dumps({
        "duracion": 1.0, "_voz": "argentina", "_segmento_hash": editar._hash_segmento(seg)}))
    (raiz / "guion" / "v09.json").write_text(json.dumps({"segmentos": [seg]}))

    marcadores = {
        "D1": lambda *a, **k: [(123.0, 456.0)],
        "D2": lambda *a, **k: [(123.0, 456.0)],
        "D3": lambda *a, **k: [(123.0, 456.0)],
        "D4": lambda *a, **k: ["MARCA-D4"],
        "D5": lambda *a, **k: ["MARCA-D5"],
        "D6": lambda *a, **k: ["MARCA-D6"],
    }
    for id_regla, espia in marcadores.items():
        monkeypatch.setitem(editar.CHEQUEOS, id_regla, espia)

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("tiempo muerto" in h and "123.0s" in h and "456.0s" in h for h in hallazgos), hallazgos
    assert any("00.json" in h and "123.0s" in h and "456.0s" in h for h in hallazgos), hallazgos
    assert any("silencio" in h and "123.0s" in h and "456.0s" in h for h in hallazgos), hallazgos
    assert "MARCA-D4" in hallazgos
    assert any("MARCA-D5" in h for h in hallazgos), hallazgos
    assert any("MARCA-D6" in h for h in hallazgos), hallazgos

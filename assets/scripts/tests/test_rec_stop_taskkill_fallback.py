"""taskkill /F sólo se usa como ÚLTIMO RECURSO, si el corte prolijo no alcanzó.

taskkill /F corrompe el .mkv (visto en la práctica: "invalid as first byte
of an EBML number"), así que stop() no debe llamarlo si el proceso ya
terminó solo con el corte prolijo.
"""
from pathlib import Path

import rec


def test_no_llama_a_taskkill_si_el_corte_prolijo_alcanzo(monkeypatch, tmp_path):
    monkeypatch.setattr(rec, "SISTEMA", "windows")

    nombre = "toma1"
    raiz = tmp_path
    monkeypatch.setattr(rec, "RAIZ", raiz)
    (raiz / f"{nombre}.pid").write_text("999")

    monkeypatch.setattr(rec, "_matar_prolijo", lambda pid: None)
    monkeypatch.setattr(rec, "_vive", lambda pid: False)  # termina apenas se pide el corte

    llamadas = []
    monkeypatch.setattr(rec.subprocess, "run",
                        lambda cmd, **kw: llamadas.append(cmd) or _FakeProc())
    monkeypatch.setattr(rec, "_ffprobe_duracion", lambda destino: "12.3")
    monkeypatch.setattr(rec, "_ffprobe_frames", lambda destino: "")

    rec.stop(nombre)

    assert not any("taskkill" in c for c in llamadas)


def test_llama_a_taskkill_si_el_proceso_no_responde(monkeypatch, tmp_path):
    monkeypatch.setattr(rec, "SISTEMA", "windows")

    nombre = "toma1"
    raiz = tmp_path
    monkeypatch.setattr(rec, "RAIZ", raiz)
    (raiz / f"{nombre}.pid").write_text("999")

    monkeypatch.setattr(rec, "_matar_prolijo", lambda pid: None)
    monkeypatch.setattr(rec, "_vive", lambda pid: True)  # nunca responde al corte prolijo
    monkeypatch.setattr(rec.time, "sleep", lambda s: None)

    llamadas = []
    monkeypatch.setattr(rec.subprocess, "run",
                        lambda cmd, **kw: llamadas.append(cmd) or _FakeProc())
    monkeypatch.setattr(rec, "_ffprobe_duracion", lambda destino: "12.3")
    monkeypatch.setattr(rec, "_ffprobe_frames", lambda destino: "")

    rec.stop(nombre)

    assert any("taskkill" in c for c in llamadas)


class _FakeProc:
    stdout = ""

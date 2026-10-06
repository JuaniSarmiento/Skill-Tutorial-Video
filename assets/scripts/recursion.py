#!/usr/bin/env python3
"""H5 (HITO3.md): escenas `pila` y `arbol`, recursión que se ve, desde una traza REAL.

Reusa `presentaciones/scripts/diagramas.trazar`: se ejecuta la función de verdad y el
dibujo sale de lo que pasó, no de lo que alguien cree que pasa. Si el código cambia, la
escena cambia con él.

spec `pila`:
  {"tipo": "pila", "archivo": "codigo/factorial.py", "llamada": "factorial(4)",
   "formato": "factorial({n})",                                      (opcional)
   "pasos": [{"cue": "arranca"}, {"cue": "baja a tres"}, ...]}

  Un `paso` por cada evento de la traza (llamada Y retorno, en el orden en que ocurren:
  ver `diagramas.trazar`), ya con su cue resuelta a "t" por `escena.resolver_spec`. El
  marco de cada llamada se apila en su cue de llamada y se desapila (mostrando su valor
  de retorno) en la cue de su retorno.

spec `arbol`:
  {"tipo": "arbol", "archivo": "codigo/fibonacci.py", "llamada": "fibonacci(5)",
   "pasos": [{"cue": "primera llamada"}, ...]}

  El árbol nunca se achica, así que lleva un `paso` por cada LLAMADA (no por retorno). Una
  llamada con los mismos argumentos que una anterior entra marcada "repetido" (en el
  acento) desde su propia cue: trabajo que se recalcula, visible apenas aparece.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PRESENTACIONES = Path(__file__).resolve().parent.parent.parent / "presentaciones" / "scripts"

MAX_MARCOS = 16   # misma cota que diagramas.dibujar_pila: más alto no entra legible
MAX_NODOS = 60    # la misma de diagramas.dibujar_arbol


def _diagramas():
    if str(_PRESENTACIONES) not in sys.path:
        sys.path.insert(0, str(_PRESENTACIONES))
    import diagramas
    return diagramas


def _formatear(args: dict, formato: str | None) -> str:
    if formato:
        return formato.format(**args)
    return ", ".join(f"{k} = {v!r}" for k, v in args.items())


def _trazar(spec: dict, base_dir: Path):
    archivo = spec.get("archivo")
    llamada = spec.get("llamada")
    tipo = spec["tipo"]
    if not archivo or not llamada:
        raise ValueError(f'la escena {tipo!r} necesita "archivo" y "llamada" '
                         f"(vino archivo={archivo!r}, llamada={llamada!r})")
    ruta = Path(archivo)
    if not ruta.is_absolute():
        ruta = base_dir / ruta
    return _diagramas().trazar(ruta, llamada, spec.get("funcion"))


def _marcos_pila(eventos: list[dict], spec: dict) -> list[dict]:
    pasos = spec.get("pasos") or []
    if len(pasos) != len(eventos):
        raise ValueError(f'"pasos" tiene que tener un elemento por cada llamada y retorno de la '
                         f'traza de {spec["llamada"]!r} ({len(eventos)} en total); vinieron {len(pasos)}')
    llamadas = [e for e in eventos if e["tipo"] == "llamada"]
    if len(llamadas) > MAX_MARCOS:
        raise ValueError(f"{len(llamadas)} llamadas: demasiadas para una pila legible "
                         f"(máx. {MAX_MARCOS}). Usá una llamada más chica.")
    formato = spec.get("formato")
    por_id: dict[int, dict] = {}
    marcos: list[dict] = []
    for e, paso in zip(eventos, pasos):
        if "t" not in paso:
            raise ValueError(f'el paso {paso!r} no tiene "t" resuelto: ¿pasaste las cues '
                             "por escena.resolver_spec antes de llamar a recursion.resolver?")
        if e["tipo"] == "llamada":
            m = {"id": e["id"], "profundidad": len(e["pila"]) - 1,
                 "texto": _formatear(e["args"], formato), "tPush": paso["t"], "tPop": None, "valor": None}
            por_id[e["id"]] = m
            marcos.append(m)
        else:
            m = por_id[e["id"]]
            m["tPop"], m["valor"] = paso["t"], repr(e["valor"])
    return marcos


def _nodos_arbol(eventos: list[dict], spec: dict) -> list[dict]:
    llamadas = [e for e in eventos if e["tipo"] == "llamada"]
    pasos = spec.get("pasos") or []
    if len(pasos) != len(llamadas):
        raise ValueError(f'"pasos" tiene que tener un elemento por cada llamada de la traza de '
                         f'{spec["llamada"]!r} ({len(llamadas)} llamadas); vinieron {len(pasos)}')
    if len(llamadas) > MAX_NODOS:
        raise ValueError(f"{len(llamadas)} llamadas: el árbol no entra en una escena "
                         f"(máx. {MAX_NODOS}). Usá una llamada más chica.")
    formato = spec.get("formato")
    marcar_repetidos = spec.get("marcar_repetidos", True)
    por_id = {e["id"]: e for e in llamadas}
    hijos: dict[int, list[int]] = {e["id"]: [] for e in llamadas}
    raiz = None
    for e in llamadas:
        if e["padre"] is None:
            raiz = e["id"] if raiz is None else raiz
        else:
            hijos[e["padre"]].append(e["id"])

    vistos: set = set()
    siguiente_hoja = [0]
    nodos_por_id: dict[int, dict] = {}

    def ubicar(i: int, d: int) -> None:
        e = por_id[i]
        clave = tuple(sorted(e["args"].items(), key=str))
        repetido = marcar_repetidos and clave in vistos
        vistos.add(clave)
        for h in hijos[i]:
            ubicar(h, d + 1)
        if hijos[i]:
            x = sum(nodos_por_id[h]["x"] for h in hijos[i]) / len(hijos[i])
        else:
            x = siguiente_hoja[0]
            siguiente_hoja[0] += 1
        nodos_por_id[i] = {"id": i, "padre": e["padre"], "x": x, "profundidad": d,
                           "texto": _formatear(e["args"], formato), "repetido": repetido}

    ubicar(raiz, 0)
    hojas = siguiente_hoja[0]
    profundidad_total = max(n["profundidad"] for n in nodos_por_id.values()) + 1
    # en el orden en que se llamaron: es el orden de "pasos" (y de la voz que las narra)
    nodos = [nodos_por_id[e["id"]] for e in llamadas]
    for e, paso, n in zip(llamadas, pasos, nodos):
        if "t" not in paso:
            raise ValueError(f'el paso {paso!r} no tiene "t" resuelto: ¿pasaste las cues '
                             "por escena.resolver_spec antes de llamar a recursion.resolver?")
        n["t"] = paso["t"]
        n["hojas"] = hojas
        n["profundidad_total"] = profundidad_total
    return nodos


def resolver(spec: dict, base_dir=None) -> dict:
    """Copia de `spec` con "marcos" (pila) o "nodos" (arbol) resueltos desde la traza real.

    Otro tipo de escena: `spec` tal cual (igual que `escena.resolver_codigo`).
    """
    if spec.get("tipo") not in ("pila", "arbol"):
        return spec
    base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    eventos = _trazar(spec, base_dir)
    out = dict(spec)
    if spec["tipo"] == "pila":
        out["marcos"] = _marcos_pila(eventos, spec)
    else:
        out["nodos"] = _nodos_arbol(eventos, spec)
    return out

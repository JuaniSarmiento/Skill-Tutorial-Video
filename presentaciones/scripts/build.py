#!/usr/bin/env python3
"""Genera una presentación .pptx (y opcionalmente .pdf y hoja de contactos) desde una especificación.

Uso:
    python build.py especificacion.yaml                 # -> <salida>/<nombre>.pptx
    python build.py especificacion.yaml --pdf --hoja    # + PDF con LibreOffice + hoja PNG
    python build.py especificacion.yaml -o carpeta/

La especificación es YAML (o JSON si no hay PyYAML). Formato completo y un ejemplo de cada tipo
de diapositiva en references/especificacion.md. Todas las rutas son relativas al archivo de la
especificación.

Lo que hace en cada corrida, sin preguntar:
- ejecuta de nuevo cada programa referenciado por un bloque `salida` (salidas siempre reales);
- vuelve a trazar cada diagrama (`imagen: {diagrama: ...}`);
- lee el código de los .py en el momento (nunca hay código copiado en la especificación).
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deck as D  # noqa: E402
import diagramas  # noqa: E402
from ejecutar_codigo import bitacora, ejecutar, recortar  # noqa: E402


# ---------------------------------------------------------------- carga
def cargar_spec(ruta: Path) -> dict:
    texto = Path(ruta).read_text(encoding="utf-8")
    if Path(ruta).suffix == ".json":
        return json.loads(texto)
    try:
        import yaml
    except ImportError:
        sys.exit("La especificación es YAML y falta PyYAML: `pip install PyYAML` o usá JSON.")
    return yaml.safe_load(texto)


def _recorrer(nodo):
    """Todos los dict anidados (para encontrar bloques dentro de filas y tipos)."""
    if isinstance(nodo, dict):
        yield nodo
        for v in nodo.values():
            yield from _recorrer(v)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from _recorrer(v)


def programas_de(spec: dict, base: Path):
    vistos = set()
    for d in _recorrer(spec.get("diapositivas", [])):
        s = d.get("salida")
        if isinstance(s, dict) and s.get("archivo"):
            clave = (s["archivo"], s.get("entrada"))
            if clave not in vistos:
                vistos.add(clave)
                yield _ruta(spec, base, s["archivo"]), s.get("entrada")


def _ruta(spec, base, archivo):
    p = base / spec.get("codigo", ".") / archivo
    return p if p.exists() else base / archivo


# ---------------------------------------------------------------- resolución de bloques
class Resolutor:
    def __init__(self, spec, base: Path, salida: Path):
        self.spec, self.base, self.out = spec, base, salida
        self.ejecuciones: dict = {}
        self.n_diagrama = 0

    def leer(self, c: dict) -> tuple[str, str]:
        """{archivo, bloque?, lineas?, desde?, cantidad?} -> (código, rótulo)."""
        if "texto" in c:
            D.avisar("código tipeado en la especificación (`texto`): verificá que no sea un "
                     "programa; los programas se leen de un .py.")
            return c["texto"], c.get("rotulo", "")
        ruta = _ruta(self.spec, self.base, c["archivo"])
        src = ruta.read_text(encoding="utf-8").rstrip("\n")
        frag = False
        if "bloque" in c:                      # n-ésimo bloque separado por líneas en blanco
            partes = [p for p in src.split("\n\n") if p.strip()]
            idx = c["bloque"] if isinstance(c["bloque"], list) else [c["bloque"]]
            src = "\n\n".join(partes[i - 1] for i in idx)
            frag = True
        if "lineas" in c:                      # "3-9" (1-based, inclusive)
            a, _, b = str(c["lineas"]).partition("-")
            ls = src.split("\n")
            src = "\n".join(ls[int(a) - 1:int(b or a)])
            frag = True
        if "desde" in c:                       # primera línea que empieza con `desde`
            ls = src.split("\n")
            k = next(i for i, l in enumerate(ls) if l.startswith(c["desde"]))
            src = "\n".join(ls[k:k + c.get("cantidad", len(ls))])
            frag = True
        rot = c.get("rotulo") or (ruta.name + (" (fragmento)" if frag else ""))
        return src, rot

    def correr(self, s: dict) -> tuple[str, str]:
        if "texto" in s:
            D.avisar("salida tipeada en la especificación: preferí `archivo:` para que sea real.")
            return s["texto"], s.get("rotulo", "Salida")
        ruta = _ruta(self.spec, self.base, s["archivo"])
        clave = (str(ruta), s.get("entrada"))
        if clave not in self.ejecuciones:
            self.ejecuciones[clave] = ejecutar(ruta, s.get("entrada"), s.get("timeout", 60))
        r = self.ejecuciones[clave]
        txt = recortar(r["salida"], s.get("primeras"), s.get("ultimas"),
                       s.get("marca", "… ({n} líneas omitidas)"))
        if s.get("comando", True):
            txt = r["comando"] + "\n" + txt
        abrev = s.get("primeras") or s.get("ultimas")
        return txt, s.get("rotulo", "Salida (abreviada)" if abrev else "Salida")

    def imagen(self, im) -> str:
        if isinstance(im, dict):
            self.n_diagrama += 1
            (self.out / "img").mkdir(parents=True, exist_ok=True)
            destino = self.out / "img" / f"diagrama-{self.n_diagrama:02d}-{im.get('diagrama', 'pila')}.png"
            base = (self.base / self.spec.get("codigo", ".")) if (
                self.base / self.spec.get("codigo", ".") / im["archivo"]).exists() else self.base
            return str(diagramas.generar(im, base, destino))
        p = self.base / im
        if not p.exists():
            sys.exit(f"No existe la imagen {p}")
        return str(p)

    def bloque(self, b: dict) -> dict:
        b = dict(b)
        if "fila" in b:
            b["fila"] = [dict(c, bloques=[self.bloque(x) for x in c["bloques"]]) for c in b["fila"]]
        if isinstance(b.get("codigo"), (dict, str)) and not isinstance(b.get("codigo"), bool):
            c = b["codigo"] if isinstance(b["codigo"], dict) else {"archivo": b["codigo"]}
            b["codigo"], rot = self.leer(c)
            b.setdefault("titulo", rot)
        if isinstance(b.get("salida"), (dict, str)):
            s = b["salida"] if isinstance(b["salida"], dict) else {"archivo": b["salida"]}
            b["salida"], rot = self.correr(s)
            b.setdefault("titulo", rot)
        if "imagen" in b:
            b["imagen"] = self.imagen(b["imagen"])
        return b


# ---------------------------------------------------------------- tipos -> bloques
def _tarjeta(t, tam=None):
    b = {("aviso" if t.get("aviso") else "tarjeta"): t.get("titulo", ""), "texto": t.get("texto")}
    for k in ("acento", "alto", "tamano", "tamano_titulo"):
        if k in t:
            b[k] = t[k]
    if tam and "tamano" not in b:
        b["tamano"] = tam
    return b


def _nota(d):
    return [{"texto": d["nota"], "tamano": d.get("tamano_nota", 14), "color": "gris"}] if d.get("nota") else []


def bloques_de(d: dict) -> list:
    t = d["tipo"]
    tam = d.get("tamano")
    if t == "libre":
        return d["bloques"]
    if t in ("vinetas", "viñetas"):
        items = [f"•  {x}" for x in d["items"]]
        txt = {"texto": items, "tamano": tam or 22, "separacion": 14}
        nota = ([{"aviso": d.get("encabezado_nota", ""), "texto": d["nota"], "fijo": True,
                  "tamano": d.get("tamano_nota", 16)}] if d.get("nota") else [])
        if d.get("imagen"):
            return [{"fila": [{"ancho": d.get("ancho_texto", 1.2), "bloques": [txt]},
                              {"bloques": [{"imagen": d["imagen"], "epigrafe": d.get("epigrafe")}]}]}] + nota
        return [txt] + nota
    if t == "tarjetas":
        filas = d.get("filas")
        if not filas:
            ts, nc = d["tarjetas"], d.get("columnas") or min(3, len(d["tarjetas"]))
            filas = [ts[i:i + nc] for i in range(0, len(ts), nc)]
        out = [{"fila": [{"bloques": [_tarjeta(x, tam)]} for x in f]} if len(f) > 1
               else _tarjeta(f[0], tam) for f in filas]
        return out + _nota(d)
    if t == "numerados":
        pasos = [_tarjeta(dict(p, titulo=f"{i}. {p['titulo']}"), tam or 16)
                 for i, p in enumerate(d["pasos"], 1)]
        if d.get("imagen"):
            im = {"imagen": d["imagen"]}
            if d.get("fondo_imagen"):
                im["fondo"] = d["fondo_imagen"]
            return [{"fila": [{"ancho": d.get("ancho_imagen", 0.72), "bloques": [im]},
                              {"bloques": pasos}]}] + _nota(d)
        return pasos + _nota(d)
    if t == "codigo":
        cod = {"codigo": d["codigo"], "tamano": d.get("tamano_codigo", 15)}
        lado = [_tarjeta(x, tam) for x in d.get("tarjetas", [])] + _nota(d)
        if not lado:
            return [cod]
        cols = [{"ancho": 1.1, "bloques": [cod]}, {"bloques": lado}]
        return [{"fila": cols[::-1] if d.get("codigo_a_la_derecha") else cols}]
    if t == "codigo_salida":
        cod = {"codigo": d["codigo"], "tamano": d.get("tamano_codigo", 15)}
        sal = {"salida": d["salida"], "tamano": d.get("tamano_salida", 12)}
        lado = [_tarjeta(x, tam) for x in d.get("tarjetas", [])] + _nota(d)
        if not lado:
            return [{"fila": [{"bloques": [cod]}, {"bloques": [sal]}]}]
        return [{"fila": [{"bloques": [cod, sal]}, {"bloques": lado}]}]
    if t == "imagen":
        pre = [{"texto": d["texto"], "tamano": tam or 16}] if d.get("texto") else []
        im = {"imagen": d["imagen"], "epigrafe": d.get("epigrafe")}
        return pre + [im] + _nota(d)
    if t == "tabla":
        return [{"tabla": d["tabla"], "titulo": d.get("rotulo"), "tamano": tam or 14}] + _nota(d)
    if t in ("cita", "aviso"):
        tit = d.get("encabezado", "")
        cuerpo = [d["texto"]] if isinstance(d["texto"], str) else d["texto"]
        if d.get("fuente"):
            cuerpo = cuerpo + [f"{{gris}}— {d['fuente']}{{/}}"]
        b = {("aviso" if t == "aviso" else "tarjeta"): tit, "texto": cuerpo, "tamano": tam or 24,
             "fijo": True}
        return [b] + _nota(d)
    raise ValueError(f"tipo de diapositiva desconocido: {t}")


def _limpiar(b):
    """Saca claves con None (p. ej. epigrafe: None) para que el motor no las tome como presentes."""
    if isinstance(b, dict):
        return {k: _limpiar(v) for k, v in b.items() if v is not None}
    if isinstance(b, list):
        return [_limpiar(x) for x in b]
    return b


# ---------------------------------------------------------------- armado
def construir(spec: dict, base: Path, out: Path, nombre: str) -> Path:
    D.AVISOS.clear()
    res = Resolutor(spec, base, out)
    dk = D.Deck(spec.get("pie", ""), autor=spec.get("autor") or spec.get("revisor"),
                titulo=spec.get("titulo"), numeracion=spec.get("numeracion", True))
    for n, d in enumerate(spec["diapositivas"], 1):
        d = copy.deepcopy(d)
        t = d.get("tipo")
        if t == "portada":
            faltan = [k for k in ("titulo", "materia", "unidad") if not d.get(k)]
            revisor = d.get("revisor", spec.get("revisor"))
            if not revisor and not d.get("sin_revisor"):
                faltan.append("revisor")
            if faltan:
                sys.exit(f"Portada (diapositiva {n}): faltan {', '.join(faltan)}. La portada "
                         "lleva materia, unidad, tema y revisor.")
            sub = d.get("subtitulo") or " · ".join(
                x for x in (d["materia"], d["unidad"], d.get("actividad")) if x)
            dk.portada(d["titulo"], sub, d.get("descripcion", []), revisor,
                       d.get("rol_revisor", "Revisor de la unidad"), _decor(d, base))
        elif t == "seccion":
            dk.seccion(d["titulo"], d.get("subtitulo"), _decor(d, base))
        elif t == "sintesis":
            dk.sintesis(d.get("titulo", "Síntesis"), d.get("botones", []), d.get("texto", []),
                        _decor(d, base))
        else:
            bl = _limpiar([res.bloque(b) for b in bloques_de(d)])
            dk.bloques(d["titulo"], bl)
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / f"{nombre}.pptx"
    dk.guardar(pptx)
    if res.ejecuciones:
        (out / f"{nombre}_salidas.txt").write_text(bitacora(list(res.ejecuciones.values())),
                                                   encoding="utf-8")
    return pptx


def _decor(d, base):
    v = d.get("decoracion", True)
    return str(base / v) if isinstance(v, str) else v


def a_pdf(pptx: Path) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        sys.exit("Falta LibreOffice (soffice). Corré scripts/preflight.py.")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent),
                    str(pptx)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=300)
    pdf = pptx.with_suffix(".pdf")
    if not pdf.exists():
        sys.exit("LibreOffice no generó el PDF (¿hay otra instancia abierta con la misma sesión?).")
    return pdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--salida", type=Path, help="carpeta de salida (por defecto: la de la spec)")
    ap.add_argument("--nombre", help="nombre base de los archivos (por defecto: `nombre` de la spec)")
    ap.add_argument("--pdf", action="store_true", help="exportar a PDF con LibreOffice headless")
    ap.add_argument("--hoja", action="store_true", help="hoja de contactos PNG (implica --pdf)")
    a = ap.parse_args()
    spec = cargar_spec(a.spec)
    base = a.spec.resolve().parent
    out = (a.salida or base / spec.get("carpeta_salida", ".")).resolve()
    nombre = a.nombre or spec.get("nombre", a.spec.stem)
    pptx = construir(spec, base, out, nombre)
    print(pptx, flush=True)
    if a.pdf or a.hoja:
        pdf = a_pdf(pptx)
        print(pdf, flush=True)
        if a.hoja:
            subprocess.run([sys.executable, str(Path(__file__).with_name("revisar.py")), str(pdf)],
                           check=True)
    if D.AVISOS:
        print(f"\n{len(D.AVISOS)} aviso(s): revisalos en la hoja de contactos.", file=sys.stderr)


if __name__ == "__main__":
    main()

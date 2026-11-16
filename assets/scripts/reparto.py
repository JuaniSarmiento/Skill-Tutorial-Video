"""Biblioteca de personajes, vestuarios y fondos del formato «clase» (ver references/clase.md).

La biblioteca vive FUERA del repo de la skill (las imágenes pesan): `TUT_REPARTO`, por defecto
`~/.local/share/tutorial-video/reparto/`. Su índice es `catalogo.json`, con rutas relativas a la
biblioteca:

    {"personajes": {"<id>": {"referencia": "personajes/<id>/referencia.png", "descripcion": "...",
        "vestuarios": {"<nombre>": {"descripcion": "...", "poses": {"<pose>": {
            "cerrada": "...png", "abierta": "...png", "boca": [x, y, w, h], "prompt": "..."}}}}}},
     "fondos": {"<nombre>": {"archivo": "fondos/<nombre>.png", "prompt": "...", "pizarra": [x, y, w, h]}}}

Lo que el guion pide y no está se dibuja UNA vez con el generador (`TUT_GENERADOR`, un comando
`<cmd> --prompt <texto> --salida <png> [--referencia <png>]...`) y queda guardado para reusar.
La generación es transaccional: todo se arma en un directorio temporal y sólo al final, si nada
falló, se mueven los archivos y se reescribe el catálogo. Si el generador falla o no existe, la
biblioteca queda como estaba y el error nombra lo que faltaba.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# Lienzo común de todas las poses: los pies siempre en la misma línea, el mismo alto de figura.
LIENZO = (960, 1440)
PISO = 1400
ALTO_FIGURA = 1260
# Fondo: vertical 2:3, como lo usa la composición (1080 de ancho).
FONDO = (1080, 1620)
# Interior de la pizarra del fondo por defecto (coordenadas del fondo de 1080×1620); se usa si la
# detección automática no encuentra una pizarra blanca razonable.
PIZARRA_DEFECTO = [54, 103, 972, 764]

# Descripción de cada pose conocida; una pose que no está acá se pide con descripción en el guion
# (`"poses": {"bailar": "baila con los brazos arriba"}`).
POSES_CONOCIDAS = {
    "parado": "parado, relajado, los brazos al costado del cuerpo",
    "senalar": "un brazo extendido señalando hacia un costado, el otro al costado del cuerpo",
    "pensar": "una mano en el mentón, mirando hacia arriba, pensativo",
    "tipear": "parado, tipeando con las dos manos en una notebook que sostiene a la altura de la cintura",
    "sorprenderse": "las dos manos levantadas junto a la cara, los ojos muy abiertos",
    "festejar": "los dos brazos levantados, festejando contento",
}

ESTILO_PERSONAJE = ("Personaje de dibujo animado 2D vectorial para videos educativos verticales: cuerpo entero, "
                    "de frente, centrado, contorno oscuro uniforme, colores planos pastel. Fondo blanco liso, "
                    "sin sombra en el piso, sin texto, sin logos, sin objetos extra.")
ESTILO_FONDO = ("Ilustración 2D vectorial, formato vertical 2:3 (1024×1536), vista frontal y despejada, para "
                "un video educativo. Una PIZARRA BLANCA grande domina el centro y la parte de arriba: casi de "
                "borde a borde horizontal, desde cerca del borde superior hasta un poco más abajo de la mitad. "
                "La superficie de la pizarra está completamente blanca y vacía, sin nada escrito. La mitad de "
                "abajo queda despejada para que un personaje grande se pare adelante. Paleta pastel clara "
                "(crema, lavanda, menta, durazno, celeste suaves), contorno oscuro uniforme. Sin texto, sin "
                "letras, sin números, sin personas, sin personajes, sin logos y sin marcas de agua.")


class ErrorReparto(SystemExit):
    """Error con mensaje para la persona (sale con 1, nunca con un traceback)."""

    def __init__(self, mensaje: str):
        super().__init__(f"reparto: {mensaje}")


def biblioteca() -> Path:
    return Path(os.environ.get("TUT_REPARTO") or Path.home() / ".local/share/tutorial-video/reparto")


def leer_catalogo(bib: Path) -> dict:
    ruta = bib / "catalogo.json"
    if not ruta.exists():
        return {"personajes": {}, "fondos": {}}
    cat = json.loads(ruta.read_text())
    cat.setdefault("personajes", {})
    cat.setdefault("fondos", {})
    return cat


# ---------- qué pide el guion ----------

def _nombre(valor, clave: str, campo_id: str = "nombre") -> tuple[str, str | None]:
    """(nombre, descripción) de `personaje`/`vestuario`/`fondo`: un texto o {nombre|id, descripcion}."""
    if isinstance(valor, str) and valor:
        return valor, None
    if isinstance(valor, dict) and isinstance(valor.get(campo_id), str) and valor[campo_id]:
        return valor[campo_id], valor.get("descripcion") or None
    raise ErrorReparto(f"«{clave}» tiene que ser un nombre o {{\"{campo_id}\": ..., \"descripcion\": ...}} (vino {valor!r})")


def poses_del_guion(g: dict) -> list[str]:
    """Poses que usa el guion, en orden de aparición y sin repetir (incluye los cambios `luego`)."""
    vistas: list[str] = []
    for i, s in enumerate(g.get("segmentos", [])):
        for p in [s.get("pose", "parado"), *[x.get("pose") for x in s.get("luego", [])]]:
            if not isinstance(p, str) or not p:
                raise ErrorReparto(f"segmento {i}: pose inválida {p!r}")
            if p not in vistas:
                vistas.append(p)
    return vistas


@dataclass
class Pedido:
    """Lo que hay que generar para que el guion tenga todo su reparto."""
    personaje: str
    vestuario: str
    fondo: str
    referencia_nueva: str | None = None          # descripción del personaje nuevo
    vestuario_desc: str | None = None
    poses_nuevas: list[str] = field(default_factory=list)
    fondo_desc: str | None = None                 # descripción del fondo nuevo (si hay que generarlo)

    def vacio(self) -> bool:
        return not (self.referencia_nueva or self.poses_nuevas or self.fondo_desc)

    def que_falta(self) -> str:
        partes = []
        if self.referencia_nueva:
            partes.append(f"el personaje «{self.personaje}»")
        if self.poses_nuevas:
            partes.append(f"el vestuario «{self.vestuario}» de «{self.personaje}» (poses: {', '.join(self.poses_nuevas)})")
        if self.fondo_desc:
            partes.append(f"el fondo «{self.fondo}»")
        return " y ".join(partes)


def planear(g: dict, cat: dict) -> Pedido:
    """Resuelve el guion contra el catálogo SIN generar nada. Falla (ErrorReparto) si algo falta y
    el guion no trae con qué generarlo: una pose desconocida sin descripción, un vestuario o un fondo
    nuevo sin descripción, un personaje nuevo sin descripción."""
    pid, pdesc = _nombre(g.get("personaje"), "personaje", "id")
    vnom, vdesc = _nombre(g.get("vestuario", "base"), "vestuario")
    fnom, fdesc = _nombre(g.get("fondo"), "fondo")
    extra = g.get("poses") or {}
    if not isinstance(extra, dict):
        raise ErrorReparto("«poses» tiene que ser {\"pose\": \"descripción\"}")
    pedido = Pedido(pid, vnom, fnom)

    ficha = cat["personajes"].get(pid)
    if ficha is None:
        if not pdesc:
            raise ErrorReparto(f"el personaje «{pid}» no está en la biblioteca y el guion no trae su descripción "
                               f"(\"personaje\": {{\"id\": \"{pid}\", \"descripcion\": \"...\"}})")
        pedido.referencia_nueva = pdesc
    vest = (ficha or {}).get("vestuarios", {}).get(vnom)
    if vest is None:
        if not vdesc and not (ficha is None and vnom == "base"):
            raise ErrorReparto(f"el vestuario «{vnom}» de «{pid}» no está en la biblioteca y el guion no trae su "
                               f"descripción (\"vestuario\": {{\"nombre\": \"{vnom}\", \"descripcion\": \"...\"}})")
        pedido.vestuario_desc = vdesc
        tiene = set()
    else:
        pedido.vestuario_desc = vest.get("descripcion") or vdesc
        tiene = set(vest.get("poses", {}))
    for p in poses_del_guion(g):
        if p in tiene:
            continue
        if p not in POSES_CONOCIDAS and p not in extra:
            raise ErrorReparto(f"la pose «{p}» no existe en el vestuario «{vnom}» de «{pid}» y el guion no trae su "
                               f"descripción para generarla (\"poses\": {{\"{p}\": \"...\"}}). "
                               f"Poses disponibles: {', '.join(sorted(tiene)) or 'ninguna'}")
        pedido.poses_nuevas.append(p)

    if fnom not in cat["fondos"]:
        if not fdesc:
            raise ErrorReparto(f"el fondo «{fnom}» no está en la biblioteca y el guion no trae su descripción "
                               f"(\"fondo\": {{\"nombre\": \"{fnom}\", \"descripcion\": \"...\"}})")
        pedido.fondo_desc = fdesc
    return pedido


# ---------- prompts ----------

def prompt_referencia(desc: str) -> str:
    return (f"{ESTILO_PERSONAJE} El personaje: {desc}. Parado en pose neutra, contento, con la boca cerrada en "
            "una sonrisa suave. Si hay una imagen adjunta, usala SÓLO como referencia de estilo (trazo, colores, "
            "proporciones); no copies a ese personaje.")


def prompt_pose(pid: str, desc_pose: str, vestuario: str | None, abierta: bool) -> str:
    ropa = f" Vestuario: {vestuario}; todo lo demás del personaje queda igual." if vestuario else ""
    boca = ("Boca abierta, hablando (la boca abierta es lo ÚNICO que cambia respecto de la versión con la boca "
            "cerrada adjunta: mismos píxeles en todo lo demás)." if abierta else
            "Boca cerrada en una sonrisa suave.")
    return (f"Con la referencia adjunta: el MISMO personaje exacto ({pid}: misma cara, mismo peinado, mismos "
            f"colores, mismo trazo y proporciones).{ropa} Pose: {desc_pose}. {boca} Cuerpo entero, de frente, "
            "centrado, mismo tamaño y los pies en el mismo lugar que la referencia. Fondo blanco liso, sin sombra "
            "en el piso, sin texto, sin objetos extra.")


def prompt_fondo(desc: str) -> str:
    return f"{ESTILO_FONDO} El lugar: {desc}."


# ---------- generador ----------

def comando_generador() -> list[str]:
    cmd = os.environ.get("TUT_GENERADOR")
    if cmd:
        return shlex.split(cmd)
    return [sys.executable, str(AQUI / "generar_imagen.py")]


def generar(prompt: str, salida: Path, referencias: list[Path], que: str) -> None:
    cmd = comando_generador()
    if not cmd or (shutil.which(cmd[0]) is None and not Path(cmd[0]).is_file()):
        raise ErrorReparto(f"no existe el generador de imágenes ({cmd[0] if cmd else 'vacío'}): no se pudo generar {que}")
    args = [*cmd, "--prompt", prompt, "--salida", str(salida)]
    for r in referencias:
        args += ["--referencia", str(r)]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=int(os.environ.get("TUT_GENERADOR_TIMEOUT", "1200")))
    except FileNotFoundError:
        raise ErrorReparto(f"no existe el generador de imágenes ({cmd[0]}): no se pudo generar {que}")
    except subprocess.TimeoutExpired:
        raise ErrorReparto(f"el generador de imágenes no terminó a tiempo: no se pudo generar {que}")
    if r.returncode != 0 or not salida.is_file():
        detalle = (r.stderr or r.stdout).strip()[-400:]
        raise ErrorReparto(f"el generador de imágenes falló (código {r.returncode}): no se pudo generar {que}. {detalle}")


# ---------- procesado de imágenes ----------

def recortar(path: Path):
    """PNG RGBA con el fondo transparente: el fondo es el blanco CONECTADO con el borde (flood-fill),
    nunca todo el blanco (los ojos o la camisa blanca no se borran)."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    rgb = np.array(Image.open(path).convert("RGB"))
    blanco = rgb.min(axis=2) > 205
    semilla = np.zeros_like(blanco)
    semilla[0], semilla[-1], semilla[:, 0], semilla[:, -1] = blanco[0], blanco[-1], blanco[:, 0], blanco[:, -1]
    fondo = ndi.binary_propagation(semilla, mask=blanco)
    mascara = ~fondo
    etiquetas, n = ndi.label(mascara)
    if n == 0:
        raise ErrorReparto(f"{path.name}: la imagen no tiene figura sobre el fondo blanco")
    cuentas = np.bincount(etiquetas.ravel())
    cuentas[0] = 0
    # La figura puede venir en partes separadas por un hilo de blanco (cabeza y cuerpo de un dibujo
    # simple): se queda todo lo que no sea una mota suelta frente a la parte más grande.
    mascara = np.isin(etiquetas, np.where(cuentas >= max(200, cuentas.max() * 0.01))[0])
    for _ in range(4):  # la franja antialias mezclada con el blanco, hasta el contorno oscuro
        borde = mascara & ndi.binary_dilation(~mascara)
        mascara[borde & (rgb.min(axis=2) > 160)] = False
    rgba = np.dstack((rgb, mascara.astype(np.uint8) * 255))
    rgba[~mascara, :3] = 0
    return Image.fromarray(rgba)


def geometria(img):
    """(arriba, abajo, centro de los pies, izquierda, derecha) de la figura."""
    import numpy as np
    a = np.array(img)[..., 3] > 0
    ys, xs = np.where(a)
    y0, y1 = ys.min(), ys.max()
    pies = a[y1 - int(.12 * (y1 - y0)):y1 + 1]
    fx = np.where(pies.any(axis=0))[0]
    return int(y0), int(y1), (fx.min() + fx.max()) / 2, int(xs.min()), int(xs.max())


def ajuste(cerradas) -> float:
    """Factor común para que la pose más ancha entre en el lienzo (todas se achican por igual)."""
    f = 1.0
    for img in cerradas:
        y0, y1, cx, x0, x1 = geometria(img)
        ancho = 2 * max(cx - x0, x1 - cx) * ALTO_FIGURA / max(1, y1 - y0)
        f = min(f, (LIENZO[0] - 40) / ancho)
    return f


def normalizar(img, escala: float, centro: float, abajo: int):
    """La figura en el lienzo común, con los pies centrados en PISO."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    chica = img.resize((max(1, round(img.width * escala)), max(1, round(img.height * escala))), Image.Resampling.LANCZOS)
    lienzo = Image.new("RGBA", LIENZO)
    lienzo.paste(chica, (round(LIENZO[0] / 2 - centro * escala), round(PISO - abajo * escala)))
    arr = np.array(lienzo)
    m = arr[..., 3] >= 100
    borde = m & ndi.binary_dilation(~m)
    m[borde & (arr[..., :3].min(axis=2) > 230)] = False
    arr[~m] = 0
    arr[m, 3] = 255
    return Image.fromarray(arr)


def caja_boca(cerrada, abierta) -> list[int]:
    """Caja [x, y, w, h] de lo que cambia entre la boca cerrada y la abierta, buscada en la cara (banda
    alta y central de la figura). Se toma el componente de diferencia más grande, con margen."""
    import numpy as np
    from scipy import ndimage as ndi
    a, b = np.array(cerrada).astype(int), np.array(abierta).astype(int)
    y0, y1, cx, _, _ = geometria(cerrada)
    alto = y1 - y0
    arriba, abajo = int(y0 + .08 * alto), int(y0 + .45 * alto)
    izq, der = int(max(0, cx - .2 * LIENZO[0])), int(min(LIENZO[0], cx + .2 * LIENZO[0]))
    dif = np.abs(a - b).max(axis=2) > 55
    roi = np.zeros(dif.shape, bool)
    roi[arriba:abajo, izq:der] = dif[arriba:abajo, izq:der]
    roi = ndi.binary_closing(roi, iterations=3)
    etiquetas, n = ndi.label(roi)
    if n == 0:
        raise ErrorReparto("no se encontró la diferencia de la boca entre la versión cerrada y la abierta")
    objetos = ndi.find_objects(etiquetas)
    _, (sy, sx) = max(((int((etiquetas[s] == k + 1).sum()), s) for k, s in enumerate(objetos) if s),
                      key=lambda c: c[0])
    x, y = max(0, sx.start - 10), max(0, sy.start - 10)
    r, ab = min(LIENZO[0], sx.stop + 10), min(LIENZO[1], sy.stop + 10)
    return [int(x), int(y), int(r - x), int(ab - y)]


def parche_boca(cerrada, abierta, caja):
    """La abierta final = la cerrada con SÓLO la caja de la boca de la abierta pegada encima: así las
    dos son idénticas fuera de la boca y el personaje no «tiembla» al hablar."""
    x, y, w, h = caja
    final = cerrada.copy()
    final.paste(abierta.crop((x, y, x + w, y + h)), (x, y))
    return final


def procesar_fondo(crudo: Path, salida: Path) -> list[int]:
    """Fondo a 1080×1620 (recorte centrado a 2:3) y la caja interior de su pizarra."""
    from PIL import Image
    im = Image.open(crudo).convert("RGB")
    w, h = im.size
    objetivo = FONDO[0] / FONDO[1]
    if w / h > objetivo:
        nw = round(h * objetivo)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w / objetivo)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize(FONDO, Image.Resampling.LANCZOS)
    im.save(salida, optimize=True)
    return detectar_pizarra(salida)


def detectar_pizarra(fondo: Path) -> list[int]:
    """Caja [x, y, w, h] del interior blanco más grande de la mitad de arriba del fondo; si no hay una
    pizarra razonable (ancha, en la parte de arriba), la del fondo por defecto."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    im = np.array(Image.open(fondo).convert("RGB").resize(FONDO))
    blanco = im.min(axis=2) > 235
    etiquetas, n = ndi.label(blanco)
    if n == 0:
        return list(PIZARRA_DEFECTO)
    cuentas = np.bincount(etiquetas.ravel())
    cuentas[0] = 0
    k = int(cuentas.argmax())
    ys, xs = np.where(etiquetas == k)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1
    llena = cuentas[k] / (w * h)
    if w < .6 * FONDO[0] or h < .25 * FONDO[1] or y0 > .45 * FONDO[1] or y1 > .75 * FONDO[1] or llena < .8:
        return list(PIZARRA_DEFECTO)
    return [x0, y0, w, h]


# ---------- resolver (y generar lo que falta) ----------

def resolver(g: dict, bib: Path | None = None, log=print) -> dict:
    """Asegura que la biblioteca tenga todo lo del guion; genera lo que falta (transaccional) y devuelve
    {"personaje", "vestuario", "fondo", "referencia", "poses": {pose: ficha}, "fondo_archivo", "pizarra",
    "biblioteca", "generado": [...]}, con rutas absolutas."""
    bib = bib or biblioteca()
    cat = leer_catalogo(bib)
    pedido = planear(g, cat)
    generado: list[str] = []
    if not pedido.vacio():
        generado = _generar_lo_que_falta(g, pedido, bib, cat)
        cat = leer_catalogo(bib)
    ficha = cat["personajes"][pedido.personaje]
    vest = ficha["vestuarios"][pedido.vestuario]
    fondo = cat["fondos"][pedido.fondo]
    abs_ = lambda r: str((bib / r).resolve())
    poses = {p: {"cerrada": abs_(vest["poses"][p]["cerrada"]), "abierta": abs_(vest["poses"][p]["abierta"]),
                 "boca": vest["poses"][p]["boca"]} for p in poses_del_guion(g)}
    pizarra = fondo.get("pizarra") or detectar_pizarra(bib / fondo["archivo"])
    log(f"personaje: {pedido.personaje} · vestuario: {pedido.vestuario} · fondo: {pedido.fondo}")
    log("generado: " + (", ".join(generado) if generado else "nada (todo estaba en la biblioteca)"))
    return {"personaje": pedido.personaje, "vestuario": pedido.vestuario, "fondo": pedido.fondo,
            "referencia": abs_(ficha["referencia"]), "poses": poses, "fondo_archivo": abs_(fondo["archivo"]),
            "pizarra": pizarra, "biblioteca": str(bib), "generado": generado}


def _generar_lo_que_falta(g: dict, pedido: Pedido, bib: Path, cat: dict) -> list[str]:
    que = pedido.que_falta()
    extra = g.get("poses") or {}
    pid, vnom = pedido.personaje, pedido.vestuario
    generado: list[str] = []
    nuevo = json.loads(json.dumps(cat))  # copia: el catálogo real no se toca hasta el final
    with tempfile.TemporaryDirectory(prefix="reparto-") as tmp_:
        tmp = Path(tmp_)
        crudos = tmp / "crudos"
        crudos.mkdir()
        listos = tmp / "listos"  # misma estructura que la biblioteca
        mover: list[str] = []    # rutas relativas a mover de listos/ a la biblioteca

        # 1) personaje nuevo: primero su referencia
        if pedido.referencia_nueva:
            estilo = [bib / f["referencia"] for f in cat["personajes"].values() if (bib / f["referencia"]).is_file()][:1]
            crudo = crudos / "referencia-cruda.png"
            prompt = prompt_referencia(pedido.referencia_nueva)
            generar(prompt, crudo, estilo, que)
            ref_rel = f"personajes/{pid}/referencia.png"
            img = recortar(crudo)
            y0, y1, cx, _, _ = geometria(img)
            destino = listos / ref_rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            normalizar(img, ALTO_FIGURA / max(1, y1 - y0) * ajuste([img]), cx, y1).save(destino, optimize=True)
            mover.append(ref_rel)
            nuevo["personajes"][pid] = {"referencia": ref_rel, "descripcion": pedido.referencia_nueva,
                                        "prompt": prompt, "vestuarios": {}}
            referencia = destino
            generado.append(f"personaje {pid} (referencia)")
        else:
            referencia = bib / nuevo["personajes"][pid]["referencia"]

        # 2) poses del vestuario: cerrada con la referencia, abierta con la referencia y la cerrada
        if pedido.poses_nuevas:
            ficha = nuevo["personajes"][pid]
            vest = ficha.setdefault("vestuarios", {}).setdefault(vnom, {"poses": {}})
            if pedido.vestuario_desc:
                vest["descripcion"] = pedido.vestuario_desc
            pares = {}
            for p in pedido.poses_nuevas:
                desc = extra.get(p) or POSES_CONOCIDAS[p]
                pc = prompt_pose(pid, desc, pedido.vestuario_desc, abierta=False)
                pa = prompt_pose(pid, desc, pedido.vestuario_desc, abierta=True)
                c, a = crudos / f"{p}-cerrada.png", crudos / f"{p}-abierta.png"
                generar(pc, c, [referencia], que)
                generar(pa, a, [referencia, c], que)
                pares[p] = (c, a, pc, pa)
            cerradas = {p: recortar(c) for p, (c, *_r) in pares.items()}
            f = ajuste(cerradas.values())
            for p, (c, a, pc, pa) in pares.items():
                cer = cerradas[p]
                y0, y1, cx, _, _ = geometria(cer)
                esc = ALTO_FIGURA / max(1, y1 - y0) * f
                cer_n = normalizar(cer, esc, cx, y1)
                ab = recortar(a)
                if ab.size != cer.size:
                    from PIL import Image
                    ab = ab.resize(cer.size, Image.Resampling.LANCZOS)
                ab_n = normalizar(ab, esc, cx, y1)
                try:
                    caja = caja_boca(cer_n, ab_n)
                except ErrorReparto as e:
                    raise ErrorReparto(f"{e.code.removeprefix('reparto: ')} (pose «{p}»): no se pudo generar {que}")
                ab_final = parche_boca(cer_n, ab_n, caja)
                rel = {v: f"personajes/{pid}/{vnom}/{p}-{v}.png" for v in ("cerrada", "abierta")}
                for v, im in (("cerrada", cer_n), ("abierta", ab_final)):
                    (listos / rel[v]).parent.mkdir(parents=True, exist_ok=True)
                    im.save(listos / rel[v], optimize=True)
                    mover.append(rel[v])
                vest["poses"][p] = {**rel, "boca": caja, "prompt": json.dumps({"cerrada": pc, "abierta": pa},
                                                                               ensure_ascii=False)}
            generado.append(f"vestuario {vnom} de {pid} ({', '.join(pedido.poses_nuevas)})")

        # 3) fondo nuevo
        if pedido.fondo_desc:
            crudo = crudos / "fondo.png"
            prompt = prompt_fondo(pedido.fondo_desc)
            generar(prompt, crudo, [], que)
            rel = f"fondos/{pedido.fondo}.png"
            (listos / rel).parent.mkdir(parents=True, exist_ok=True)
            pizarra = procesar_fondo(crudo, listos / rel)
            mover.append(rel)
            nuevo["fondos"][pedido.fondo] = {"archivo": rel, "prompt": prompt, "descripcion": pedido.fondo_desc,
                                             "pizarra": pizarra}
            generado.append(f"fondo {pedido.fondo}")

        # 4) todo salió bien: recién ahora se toca la biblioteca (archivos y, al final, el catálogo)
        for rel in mover:
            if (bib / rel).exists():
                raise ErrorReparto(f"{bib / rel} ya existe y el catálogo no lo nombra: no se pisa; revisalo a mano")
        hechos: list[Path] = []
        try:
            for rel in mover:
                (bib / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(listos / rel, bib / rel)
                hechos.append(bib / rel)
            tmp_cat = bib / ".catalogo.json.nuevo"
            tmp_cat.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2) + "\n")
            os.replace(tmp_cat, bib / "catalogo.json")
        except BaseException:
            for h in hechos:
                h.unlink(missing_ok=True)
            (bib / ".catalogo.json.nuevo").unlink(missing_ok=True)
            raise
    return generado

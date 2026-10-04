"""Librería de diapositivas con el estilo de la cátedra UTN TUPaD (16:9, python-pptx).

Dos niveles de uso:

1. Tipos de diapositiva listos (portada, viñetas, tarjetas, numerados, código, tabla,
   síntesis...), que es lo que usa build.py a partir de una especificación.
2. Un motor de bloques (`Deck.bloques`) que apila bloques verticalmente y los reparte en
   columnas con `fila`. Cada tipo de diapositiva es un atajo que arma un árbol de bloques.

Bloques disponibles (dict con UNA clave de tipo):
    {"tarjeta": "Título", "texto": [...], "acento": "naranja"}
    {"aviso": "Título", "texto": [...]}                    tarjeta naranja con fondo cálido
    {"codigo": "<fuente>", "titulo": "archivo.py", "tamano": 15}
    {"salida": "<texto de consola>", "titulo": "Salida", "tamano": 12}
    {"texto": [...], "tamano": 14, "color": "gris", "negrita": False, "alinear": "centro"}
    {"tabla": {"encabezado": [...], "filas": [[...]], "anchos": [1, 1, 4]}, "titulo": "..."}
    {"imagen": "<ruta png>", "epigrafe": "...", "fondo": "navy", "margen": 0.15}
    {"fila": [{"ancho": 1, "bloques": [...]}, {"ancho": 1.2, "bloques": [...]}]}
Cualquier bloque acepta "alto" (pulgadas) para fijar su altura.

Marcado de texto en línea (en cualquier texto):
    **negrita**   `código`   {naranja}texto en color{/}
Colores con nombre: navy, acento, naranja, verde, rojo, gris, texto, blanco, claro.
"""
from __future__ import annotations

import keyword
import math
import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# ---------------------------------------------------------------- identidad
NAVY = RGBColor(0x1B, 0x36, 0x5D)      # azul institucional: títulos, fondos oscuros
ACC = RGBColor(0x2F, 0x6F, 0xA7)       # acento: subrayado de título, etiquetas, botones
TXT = RGBColor(0x1F, 0x23, 0x28)       # texto corrido
GRIS = RGBColor(0x5B, 0x64, 0x70)      # texto secundario, pie, epígrafes
CARD = RGBColor(0xE8, 0xEE, 0xF6)      # fondo de tarjetas, filas pares de tabla
BORDE = RGBColor(0xC9, 0xD3, 0xDF)     # bordes de código, línea del pie
CODEBG = RGBColor(0xF6, 0xF8, 0xFA)    # fondo de código y consola
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
NARANJA = RGBColor(0xB5, 0x47, 0x08)   # caso base, advertencias, lo que importa
NARANJA_FONDO = RGBColor(0xFD, 0xF1, 0xE8)
VERDE = RGBColor(0x2E, 0x7D, 0x4F)     # cadenas en el código
ROJO = RGBColor(0xB4, 0x23, 0x18)      # errores en la consola
CLARO = RGBColor(0xC3, 0xD5, 0xEA)     # subtítulos sobre fondo navy
LINEA = RGBColor(0x8F, 0xB0, 0xD6)     # filete de la portada

COLORES = {"navy": NAVY, "acento": ACC, "texto": TXT, "gris": GRIS, "naranja": NARANJA,
           "verde": VERDE, "rojo": ROJO, "blanco": BLANCO, "claro": CLARO}

SANS = "Inter"
# DejaVu Sans Mono y NO JetBrains Mono: LibreOffice activa las ligaduras de JetBrains y
# convierte `==`, `<=`, `!=` y `->` en un solo símbolo. En una clase de programación eso
# muestra un operador que no existe en el teclado.
MONO = "DejaVu Sans Mono"
KEYWORDS = set(keyword.kwlist)

# ---------------------------------------------------------------- geometría (pulgadas)
ANCHO, ALTO = 13.333, 7.5
X0, Y0 = 0.6, 1.45          # área de contenido
W0 = ANCHO - 2 * X0         # 12.13
Y_FIN = 6.75                # el pie arranca en 6.95
GAP_V, GAP_H = 0.25, 0.4
ETIQUETA = 0.4              # alto del rótulo azul sobre código, salida y tabla
CRECE_MAX = 1.2             # lo máximo que un bloque elástico se estira sobre su alto natural

AVISOS: list[str] = []


def avisar(msg):
    AVISOS.append(msg)
    print("AVISO:", msg, file=sys.stderr)


def color(c, defecto=TXT):
    if c is None:
        return defecto
    if isinstance(c, RGBColor):
        return c
    if c in COLORES:
        return COLORES[c]
    c = str(c).lstrip("#")
    return RGBColor.from_string(c.upper())


# ---------------------------------------------------------------- marcado en línea
_TOK = re.compile(r"\{/\}|\{(\w+)\}|\*\*|`[^`]*`|[^`*{]+|.")


def runs(texto, base=None):
    """'**a** `b` {naranja}c{/}' -> [(texto, estilo), ...]. Las listas ya armadas pasan igual."""
    if not isinstance(texto, str):
        return texto
    base = base or {}
    out, colores, negrita = [], [], False
    for m in _TOK.finditer(texto):
        t = m.group(0)
        if t == "{/}":
            colores and colores.pop()
            continue
        if m.group(1) and m.group(1) in COLORES:
            colores.append(COLORES[m.group(1)])
            continue
        if t == "**":
            negrita = not negrita
            continue
        st = dict(base)
        if colores:
            st["color"] = colores[-1]
        if negrita:
            st["bold"] = True
        if t.startswith("`") and t.endswith("`") and len(t) >= 2:
            t = t[1:-1]
            st["font"] = MONO
            st.setdefault("color", NAVY)
        out.append((t, st))
    return out or [(" ", {})]


def _plano(p):
    return "".join(t for t, _ in runs(p)) if isinstance(p, str) else "".join(t for t, _ in p)


def lineas_estimadas(paras, ancho, tam, mono=False):
    """Cuántas líneas ocupa una lista de párrafos en `ancho` pulgadas (estimación)."""
    em = 0.602 if mono else 0.53
    cpl = max(8, int(ancho * 72 / (tam * em)))
    return sum(max(1, math.ceil(len(_plano(p)) / cpl)) for p in paras)


class Deck:
    def __init__(self, pie, autor=None, titulo=None, numeracion=True):
        self.prs = Presentation()
        self.prs.slide_width = Emu(12191695)
        self.prs.slide_height = Emu(6858000)
        self.pie = pie
        self.autor = autor
        self.titulo = titulo
        self.numeracion = numeracion   # True, False o lista de etiquetas propias
        self.slides, self.oscuras = [], set()

    # ------------------------------------------------------------ primitivas
    def _blank(self):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.slides.append(s)
        return s

    @staticmethod
    def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
        r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        r.shadow.inherit = False
        if fill is None:
            r.fill.background()
        else:
            r.fill.solid()
            r.fill.fore_color.rgb = fill
        if line is None:
            r.line.fill.background()
        else:
            r.line.color.rgb = line
            r.line.width = Pt(0.75)
        return r

    @staticmethod
    def text(s, x, y, w, h, paras, size=16, color=TXT, bold=False, font=SANS,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.1, space_after=4):
        """paras: lista de párrafos; cada uno es str (con marcado) o lista de (texto, estilo)."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, m, 0)
        for i, p in enumerate(paras):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.alignment = align
            para.line_spacing = spacing
            para.space_after = Pt(space_after)
            for t, st in runs(p):
                r = para.add_run()
                r.text = t
                f = r.font
                f.name = st.get("font", font)
                f.size = Pt(st.get("size", size))
                f.bold = st.get("bold", bold)
                f.color.rgb = st.get("color", color)
        return tb

    def imagen(self, s, ruta, x, y, w, h):
        """Inserta la imagen ajustada a la caja, sin deformarla, centrada."""
        from PIL import Image
        with Image.open(ruta) as im:
            iw, ih = im.size
        esc = min(w / iw, h / ih)
        rw, rh = iw * esc, ih * esc
        return s.shapes.add_picture(str(ruta), Inches(x + (w - rw) / 2), Inches(y + (h - rh) / 2),
                                    Inches(rw), Inches(rh))

    # ------------------------------------------------------------ código y consola
    @staticmethod
    def _tokens(line):
        if not line:
            return [(" ", {})]
        out = []
        for tok in re.findall(r'#.*$|[rbfRBF]{0,2}"[^"]*"|[rbfRBF]{0,2}\'[^\']*\'|\w+|\s+|.', line):
            if tok.startswith("#"):
                out.append((tok, {"color": GRIS}))
            elif tok.endswith(('"', "'")) and len(tok) > 1:
                out.append((tok, {"color": VERDE}))
            elif tok in KEYWORDS:
                out.append((tok, {"color": NAVY, "bold": True}))
            else:
                out.append((tok, {}))
        return out

    @staticmethod
    def _consola(line):
        if re.match(r"^(\w+(Error|Exception|Interrupt)|Traceback)\b", line):
            return [(line, {"color": ROJO, "bold": line[0] != "T"})]
        if line.startswith(("$ ", "[", "…", "  [")):
            return [(line, {"color": GRIS})]
        return [(line or " ", {})]

    @staticmethod
    def tam_codigo(src, w, tam):
        """Achica la letra si la línea más larga no entra en el ancho: el código no se corta."""
        largo = max((len(l) for l in src.split("\n")), default=1) or 1
        cabe = (w - 0.45) * 72 / (0.602 * largo)
        return min(tam, math.floor(cabe * 2) / 2)

    def code(self, s, x, y, w, h, src, size=15, titulo=None, consola=False):
        if titulo:
            self.text(s, x, y, w, 0.35, [titulo], size=12, color=ACC, bold=True)
            y, h = y + ETIQUETA, h - ETIQUETA
        src = src.rstrip("\n")
        size = self.tam_codigo(src, w, size)
        self.rect(s, x, y, w, h, CODEBG, BORDE)
        paras = [self._consola(l) if consola else self._tokens(l) for l in src.split("\n")]
        self.text(s, x + 0.25, y + 0.2, w - 0.4, h - 0.3, paras, size=size, font=MONO,
                  spacing=1.0, space_after=1)

    def card(self, s, x, y, w, h, titulo, cuerpo, acento=ACC, size=15, tsize=16, fondo=CARD):
        self.rect(s, x, y, w, h, fondo)
        self.rect(s, x, y, 0.07, h, acento)
        paras = []
        if titulo:
            paras.append([(titulo, {"bold": True, "color": NAVY if acento == ACC else acento,
                                    "size": tsize})])
        paras += list(cuerpo)
        self.text(s, x + 0.25, y + 0.16, w - 0.45, h - 0.25, paras, size=size)

    def tabla(self, s, x, y, w, t, size=14, titulo=None):
        if titulo:
            self.text(s, x, y, w, 0.35, [titulo], size=12, color=ACC, bold=True)
            y += ETIQUETA
        filas = ([t["encabezado"]] if t.get("encabezado") else []) + t["filas"]
        ncol = max(len(f) for f in filas)
        pesos = t.get("anchos") or [1] * ncol
        anchos = [w * p / sum(pesos) for p in pesos]
        alturas = [self._alto_fila(f, anchos, size) for f in filas]
        tbl = s.shapes.add_table(len(filas), ncol, Inches(x), Inches(y), Inches(w),
                                 Inches(sum(alturas))).table
        for j, a in enumerate(anchos):
            tbl.columns[j].width = Inches(a)
        resaltar = set(t.get("resaltar", []))           # índices de fila de datos (desde 1)
        centrar = set(t.get("centrar", []))             # índices de columna (desde 1)
        enc = bool(t.get("encabezado"))
        for i, fila in enumerate(filas):
            tbl.rows[i].height = Inches(alturas[i])
            dato = i if enc else i + 1
            for j, val in enumerate(fila):
                c = tbl.cell(i, j)
                c.fill.solid()
                es_enc = enc and i == 0
                c.fill.fore_color.rgb = NAVY if es_enc else (CARD if dato % 2 else BLANCO)
                tf = c.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER if (j + 1) in centrar else PP_ALIGN.LEFT
                base = {"size": size}
                if es_enc:
                    base.update(color=BLANCO, bold=True)
                elif dato in resaltar:
                    base.update(color=NARANJA, bold=True)
                elif j == 0 and t.get("primera_negrita"):
                    base.update(color=NAVY, bold=True)
                for txt, st in runs(str(val), base):
                    r = p.add_run()
                    r.text = txt
                    f = r.font
                    f.name = st.get("font", SANS)
                    f.size = Pt(st.get("size", size))
                    f.bold = st.get("bold", False)
                    f.color.rgb = st.get("color", TXT)
        return sum(alturas)

    @staticmethod
    def _alto_fila(fila, anchos, size):
        lin = max(lineas_estimadas([str(v)], a - 0.2, size) for v, a in zip(fila, anchos))
        return lin * size * 1.25 / 72 + 0.22

    # ------------------------------------------------------------ motor de bloques
    def natural(self, b, w):
        """Alto natural estimado de un bloque con ancho w."""
        if "alto" in b:
            return b["alto"]
        tam = b.get("tamano")
        if "fila" in b:
            cols = self._columnas(b["fila"], w)
            return max(self._natural_pila(c["bloques"], cw) for c, cw in cols)
        if "tarjeta" in b or "aviso" in b:
            tam = tam or 15
            tt = b.get("tamano_titulo", tam + 1)
            tit = 1 if (b.get("tarjeta") or b.get("aviso")) else 0
            n = lineas_estimadas(_lista(b.get("texto")), w - 0.45, tam)
            return 0.42 + tit * (tt * 1.3 + 4) / 72 + n * (tam * 1.32 + 4) / 72
        if "codigo" in b or "salida" in b:
            src = (b.get("codigo") or b.get("salida") or "").rstrip("\n")
            tam = self.tam_codigo(src, w, tam or (15 if "codigo" in b else 12))
            n = src.count("\n") + 1
            return (ETIQUETA if b.get("titulo") else 0) + 0.45 + n * (tam * 1.2 + 1) / 72
        if "texto" in b:
            tam = tam or 16
            n = lineas_estimadas(_lista(b["texto"]), w, tam)
            return n * (tam * 1.3 + 4) / 72
        if "tabla" in b:
            t = b["tabla"]
            filas = ([t["encabezado"]] if t.get("encabezado") else []) + t["filas"]
            pesos = t.get("anchos") or [1] * max(len(f) for f in filas)
            anchos = [w * p / sum(pesos) for p in pesos]
            return (ETIQUETA if b.get("titulo") else 0) + sum(
                self._alto_fila(f, anchos, tam or 14) for f in filas)
        if "imagen" in b:
            from PIL import Image
            with Image.open(b["imagen"]) as im:
                iw, ih = im.size
            m = b.get("margen", 0.15 if b.get("fondo") else 0)
            return (w - 2 * m) * ih / iw + 2 * m + (0.4 if b.get("epigrafe") else 0)
        raise ValueError(f"bloque desconocido: {list(b)}")

    @staticmethod
    def _elastico(b):
        if "alto" in b or b.get("fijo"):
            return False
        if "fila" in b:
            return any(Deck._elastico(x) for c in b["fila"] for x in c["bloques"])
        return any(k in b for k in ("tarjeta", "aviso", "codigo", "salida"))

    @staticmethod
    def _columnas(cols, w):
        pesos = [c.get("ancho", 1) for c in cols]
        util = w - GAP_H * (len(cols) - 1)
        return [(c, util * p / sum(pesos)) for c, p in zip(cols, pesos)]

    def _natural_pila(self, bloques, w):
        return sum(self.natural(b, w) for b in bloques) + GAP_V * (len(bloques) - 1)

    def pila(self, s, bloques, x, y, w, h, n_diapo="?"):
        """Apila bloques en la caja (x, y, w, h) repartiendo el alto sobrante entre los elásticos."""
        if not bloques:
            return
        nat = [self.natural(b, w) for b in bloques]
        libre = h - sum(nat) - GAP_V * (len(bloques) - 1)
        if libre < -0.02:
            # primero se achican las imágenes, que no pierden contenido al reducirse
            imgs = [i for i, b in enumerate(bloques) if "imagen" in b and "alto" not in b]
            for i in imgs:
                quita = min(-libre, nat[i] * 0.4)
                nat[i] -= quita
                libre += quita
            if libre < -0.02:
                avisar(f"diapositiva {n_diapo}: el contenido pide {-libre:.2f} in más de los "
                       f"que hay. Revisá la imagen: puede desbordar.")
        elif libre > 0:
            # El sobrante se reparte entre los elásticos, pero cada bloque crece como mucho
            # CRECE_MAX: una tarjeta con dos líneas estirada a toda la altura se ve vacía.
            el = [i for i, b in enumerate(bloques) if self._elastico(b)]
            tot = sum(nat[i] for i in el)
            for i in el:
                extra = libre * nat[i] / tot
                if "fila" not in bloques[i]:
                    extra = min(extra, CRECE_MAX)
                nat[i] += extra
        for b, alto in zip(bloques, nat):
            self.bloque(s, b, x, y, w, alto, n_diapo)
            y += alto + GAP_V

    def bloque(self, s, b, x, y, w, h, n_diapo="?"):
        tam = b.get("tamano")
        if "fila" in b:
            for c, cw in self._columnas(b["fila"], w):
                self.pila(s, c["bloques"], x, y, cw, h, n_diapo)
                x += cw + GAP_H
        elif "tarjeta" in b or "aviso" in b:
            av = "aviso" in b
            acento = color(b.get("acento"), NARANJA if av else ACC)
            self.card(s, x, y, w, h, b.get("tarjeta") or b.get("aviso"), _lista(b.get("texto")),
                      acento=acento, size=tam or 15, tsize=b.get("tamano_titulo", (tam or 15) + 1),
                      fondo=NARANJA_FONDO if av else CARD)
        elif "codigo" in b:
            self.code(s, x, y, w, h, b["codigo"], size=tam or 15, titulo=b.get("titulo"))
        elif "salida" in b:
            self.code(s, x, y, w, h, b["salida"], size=tam or 12, titulo=b.get("titulo"),
                      consola=True)
        elif "texto" in b:
            al = {"centro": PP_ALIGN.CENTER, "derecha": PP_ALIGN.RIGHT}.get(b.get("alinear"),
                                                                           PP_ALIGN.LEFT)
            self.text(s, x, y, w, h, _lista(b["texto"]), size=tam or 16,
                      color=color(b.get("color")), bold=b.get("negrita", False), align=al,
                      space_after=b.get("separacion", 4))
        elif "tabla" in b:
            self.tabla(s, x, y, w, b["tabla"], size=tam or 14, titulo=b.get("titulo"))
        elif "imagen" in b:
            ep = 0.4 if b.get("epigrafe") else 0
            ih = h - ep
            if b.get("fondo"):
                self.rect(s, x, y, w, ih, color(b["fondo"]))
                m = b.get("margen", 0.15)
                self.imagen(s, b["imagen"], x + m, y + m, w - 2 * m, ih - 2 * m)
            else:
                self.imagen(s, b["imagen"], x, y, w, ih)
            if ep:
                self.text(s, x, y + ih + 0.08, w, 0.3, [b["epigrafe"]], size=11, color=GRIS,
                          align=PP_ALIGN.CENTER)

    # ------------------------------------------------------------ tipos de diapositiva
    def contenido(self, titulo):
        s = self._blank()
        self.rect(s, 0, 0, ANCHO, 0.12, NAVY)
        self.text(s, X0, 0.38, W0, 0.75, [titulo], size=28, color=NAVY, bold=True,
                  anchor=MSO_ANCHOR.MIDDLE)
        self.rect(s, X0, 1.15, 1.1, 0.06, ACC)
        return s

    def bloques(self, titulo, bloques):
        s = self.contenido(titulo)
        self.pila(s, bloques, X0, Y0, W0, Y_FIN - Y0, len(self.slides))
        return s

    def _oscura(self, decoracion=True):
        s = self._blank()
        self.oscuras.add(id(s))
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = NAVY
        if decoracion:
            dec = decoracion if isinstance(decoracion, (str, Path)) else ASSETS / "portada-marcos.png"
            s.shapes.add_picture(str(dec), Inches(7.75), Inches(1.2), Inches(5.1), Inches(5.1))
        s.shapes.add_picture(str(ASSETS / "logo-utn-blanco.png"), Inches(0.6), Inches(0.55),
                             Inches(1.55))
        return s

    def portada(self, titulo, subtitulo, cuerpo, revisor=None, rol="Revisor de la unidad",
                decoracion=True):
        s = self._oscura(decoracion)
        self.text(s, 0.6, 1.55, 7.0, 0.45, [subtitulo], size=15, color=CLARO, bold=True)
        lineas = lineas_estimadas([titulo], 7.0, 40 * 1.08)
        self.text(s, 0.6, 2.05, 7.0, 0.8 * lineas, [titulo], size=40, color=BLANCO, bold=True,
                  spacing=1.0)
        yc = 2.05 + 0.8 * lineas + 0.35
        self.text(s, 0.6, yc, 6.9, 6.0 - yc, _lista(cuerpo), size=17, color=BLANCO,
                  space_after=10)
        if revisor:
            self.rect(s, 0.6, 6.15, 0.9, 0.04, LINEA)
            self.text(s, 0.6, 6.3, 7.5, 0.4, [[(f"{rol}: ", {}), (revisor, {"bold": True})]],
                      size=14, color=BLANCO)
        return s

    def seccion(self, titulo, subtitulo=None, decoracion=True):
        s = self._oscura(decoracion)
        if subtitulo:
            self.text(s, 0.6, 2.4, 7.0, 0.45, [subtitulo], size=15, color=CLARO, bold=True)
        self.text(s, 0.6, 2.9, 7.0, 2.0, [titulo], size=40, color=BLANCO, bold=True, spacing=1.0)
        self.text(s, 0.6, 6.9, 7.0, 0.3, [self.pie], size=10, color=CLARO)
        return s

    def sintesis(self, titulo, botones, cuerpo, decoracion=True):
        s = self._oscura(decoracion)
        self.text(s, 0.6, 1.75, 7.0, 0.8, [titulo], size=36, color=BLANCO, bold=True)
        for i, b in enumerate(botones):
            x = 0.6 + (i % 2) * 3.55
            y = 2.75 + (i // 2) * 0.9
            r = self.rect(s, x, y, 3.35, 0.65, ACC, None, MSO_SHAPE.ROUNDED_RECTANGLE)
            r.adjustments[0] = 0.15
            self.text(s, x + 0.1, y, 3.15, 0.65, [b], size=16 if len(b) <= 22 else 14,
                      color=BLANCO, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        yb = 2.75 + ((len(botones) + 1) // 2) * 0.9 + 0.1
        self.text(s, 0.6, yb, 6.9, 6.7 - yb, _lista(cuerpo), size=15, color=BLANCO, space_after=8)
        self.text(s, 0.6, 6.9, 7.0, 0.3, [self.pie], size=10, color=CLARO)
        return s

    # ------------------------------------------------------------ cierre
    def guardar(self, ruta):
        total = len(self.slides)
        for i, s in enumerate(self.slides, 1):
            if id(s) in self.oscuras:
                continue
            self.rect(s, 0.6, 6.95, W0, 0.01, BORDE)
            s.shapes.add_picture(str(ASSETS / "logo-utn-negro.png"), Inches(0.6), Inches(7.05),
                                 Inches(0.81))
            self.text(s, 1.55, 7.02, 8.0, 0.32, [self.pie], size=10, color=GRIS,
                      anchor=MSO_ANCHOR.MIDDLE)
            if self.numeracion:
                et = (self.numeracion[i - 1] if isinstance(self.numeracion, list)
                      else f"{i} / {total}")
                self.text(s, 10.23, 7.02, 2.5, 0.32, [et], size=10, color=GRIS,
                          align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        cp = self.prs.core_properties
        if self.autor:
            cp.author = cp.last_modified_by = self.autor
        if self.titulo:
            cp.title = self.titulo
        cp.subject = self.pie
        self.prs.save(str(ruta))


def _lista(x):
    if x is None:
        return []
    return [x] if isinstance(x, str) else list(x)

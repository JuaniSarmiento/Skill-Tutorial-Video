"""Detección de momentos clave para el zoom automático, a partir de diferencias entre
cuadros del crudo (S7a del Hito 2, docs/explicador/HITO2.md: decisión Q5 de Juani del
03/10/2026 — los momentos salen de analizar los cuadros grabados, no de coordenadas que
`rec.py` nunca guardó, y así funciona también con lo que ya está grabado hoy).

Analiza el crudo ANTES de mpdecimate (igual que el recorte del zoom fijo en `editar.py`),
muestreando a pocos fps y en escala de grises a baja resolución: así el diff se hace en
Python puro, sin numpy (no está instalado en el entorno fijo de los tests de este repo,
`uv run --with pytest --with playwright ...`).

Formato de salida (`videos/<vNN>/zonas/NN.json`, uno por segmento de pantalla):
  [{"t": segundos en el eje del CRUDO (el mismo que seg["inicio"]/seg["fin"]),
    "x", "y", "w", "h": caja en píxeles del crudo (sin escalar, misma convención que el
    "zoom": {x,y,w,h} fijo de editar.py), "importancia": número, mayor = más píxeles
    cambiados DE VERDAD en ese componente (no el área de la caja que lo encierra: una
    caja grande con pocos píxeles cambiados -como un scroll- no vale más que una chica
    bien sostenida)}, ...]
Un cambio entre dos cuadros se agrupa en componentes conexas (B3, `_componentes`) y cada
una se clasifica por separado: ruido (demasiado chica), scroll (el contenido se desplazó,
`_desplazamiento`), parpadeo (vuelve al estado anterior) o momento de verdad. Ver la
sección "Fuente de datos del zoom" de ../../SKILL.md para el detalle.
No decide CUÁLES usar ni limita la frecuencia entre acercamientos: eso es trabajo de S7b
(R-7.2 como mucho un acercamiento cada 3 s, R-7.4 sin momentos clave).
"""
import array
import tempfile
from pathlib import Path

import editar

FPS_MUESTREO = 2.0       # muestras por segundo analizadas
ANCHO_MUESTRA = 160      # ancho (px) del cuadro reducido para el diff en Python puro
UMBRAL_GRIS = 15         # diferencia de gris (0-255) para contar un píxel como "cambiado"
AREA_MIN_FRAC = 0.0003   # por debajo: ruido (cursor parpadeando, reloj) -> no es momento
AREA_MAX_FRAC = 0.35     # por encima: cambia casi toda la pantalla (scroll) -> no es momento


def _componentes(cambiados: set[tuple[int, int]], dilatacion: int) -> list[set[tuple[int, int]]]:
    """Agrupa coordenadas (x, y) cambiadas en componentes conexas (B3): dos píxeles quedan
    en el mismo componente si su distancia Chebyshev es <= `dilatacion` + 1 (0 = sólo
    contacto directo, como una línea de texto con letras pegadas; un valor mayor junta
    letras con un hueco chico de por medio sin unir dos cambios que están lejos de
    verdad, como un aviso en una esquina y la salida de un comando en otra).
    """
    radio = dilatacion + 1
    padre: dict[tuple[int, int], tuple[int, int]] = {p: p for p in cambiados}

    def find(p: tuple[int, int]) -> tuple[int, int]:
        while padre[p] != p:
            padre[p] = padre[padre[p]]
            p = padre[p]
        return p

    def union(a: tuple[int, int], b: tuple[int, int]) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            padre[ra] = rb

    por_fila: dict[int, list[int]] = {}
    for x, y in cambiados:
        por_fila.setdefault(y, []).append(x)
    for x, y in cambiados:
        for dy in range(-radio, radio + 1):
            for x2 in por_fila.get(y + dy, ()):
                if (x2, y + dy) == (x, y):
                    continue
                if abs(x2 - x) <= radio:
                    union((x, y), (x2, y + dy))

    grupos: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for p in cambiados:
        grupos.setdefault(find(p), set()).add(p)
    return list(grupos.values())


def _diff_cambiados(a: bytes, b: bytes, ancho: int, umbral: int) -> set[tuple[int, int]]:
    """Coordenadas (x, y) donde `b` difiere de `a` en más de `umbral` (escala de grises,
    0-255)."""
    av = array.array("B", a)
    bv = array.array("B", b)
    return {(i % ancho, i // ancho) for i in range(len(av)) if abs(av[i] - bv[i]) > umbral}


def _bbox_de(componente: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) -caja semiabierta- que encierra un componente de coordenadas."""
    xs = [x for x, _ in componente]
    ys = [y for _, y in componente]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _diff_bbox(a: bytes, b: bytes, ancho: int, umbral: int) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) -caja semiabierta- de los píxeles donde `b` difiere de `a` en más
    de `umbral` (escala de grises, 0-255). None si no hay ninguno."""
    cambiados = _diff_cambiados(a, b, ancho, umbral)
    return _bbox_de(cambiados) if cambiados else None


DILATACION = 4  # celdas de la grilla reducida que se puentean al agrupar en componentes
DESPLAZAMIENTO_DY_MAX = 20            # filas máximas de corrimiento que se prueban
DESPLAZAMIENTO_RESIDUAL_MAX_FRAC = 0.15  # fracción de píxeles que puede no calzar ni corrido
DESPLAZAMIENTO_ALTO_MIN = 6  # filas mínimas del componente para animarse a buscar un scroll:
                              # con menos, la superposición al corrimiento es tan chica (1-2
                              # filas) que "calza" con cualquier cosa por casualidad -una línea
                              # de texto tipeada (1-3 filas) no tiene que confundirse con un
                              # scroll real (que ocupa muchas filas de la pantalla)


def _desplazamiento(base: bytes, cuadro: bytes, ancho: int, bbox: tuple[int, int, int, int],
                     *, umbral: int, dy_max: int, residual_max_frac: float) -> int | None:
    """dy (!= 0) tal que, dentro de `bbox`, `cuadro` se parece a `base` corrido `dy` filas
    verticalmente (B1: un scroll es un DESPLAZAMIENTO del contenido -lo que entra por un
    borde reemplaza lo que sale por el otro-, no "cambia casi toda la pantalla"). Compara
    sólo la zona donde `base` corrida se superpone con el propio `bbox` (lo que entra por
    el borde nuevo no tiene con qué compararse, y no cuenta ni a favor ni en contra).

    None si ningún corrimiento en [-dy_max, dy_max] explica el cambio con una fracción de
    píxeles residuales (que no calzan ni corridos, dentro de lo comparado) <= `residual_max_frac`.
    """
    bv = array.array("B", base)
    cv = array.array("B", cuadro)
    x0, y0, x1, y1 = bbox
    mejor: tuple[int, float] | None = None
    for dy in range(-dy_max, dy_max + 1):
        if dy == 0:
            continue
        total = malos = 0
        for y in range(y0, y1):
            yb = y + dy
            if yb < y0 or yb >= y1:
                continue
            fila_b, fila_c = yb * ancho, y * ancho
            for x in range(x0, x1):
                total += 1
                if abs(bv[fila_b + x] - cv[fila_c + x]) > umbral:
                    malos += 1
        if total == 0:
            continue
        frac = malos / total
        if frac <= residual_max_frac and (
                mejor is None or (frac, abs(dy)) < (mejor[1], abs(mejor[0]))):
            mejor = (dy, frac)
    return mejor[0] if mejor else None


def _momentos_en_cuadros(cuadros_con_t: list[tuple[float, bytes]], ancho: int, alto: int,
                          escala_x: float, escala_y: float, *, umbral: int,
                          area_min_frac: float, area_max_frac: float,
                          dilatacion: int = DILATACION) -> list[dict]:
    """[{t,x,y,w,h,importancia}] a partir de una secuencia de (t, cuadro en escala de
    grises) ya muestreada.

    Compara cada cuadro contra un "estado estable" (`base`), que arranca en el primer
    cuadro y se va actualizando POR REGIÓN (no entera): cada región cambiada se agrupa
    en componentes conexas (B3, `_componentes`) y cada una se clasifica por separado, así
    un cambio chico y persistente en un borde (reloj, barra de estado) no se mezcla con
    el cambio grande del medio de la pantalla (B4) ni lo estira:
      - un cambio demasiado chico (cursor parpadeando, reloj) se ignora y NO mueve la
        base en esa región: lo que vino antes sigue siendo la referencia ahí.
      - un cambio que cubre casi toda la pantalla (scroll "duro", sin correspondencia de
        desplazamiento) no es un momento, pero SÍ actualiza la base en esa región.
      - un cambio que se sostiene en el cuadro siguiente (no vuelve a la base) es un
        momento de verdad: se guarda y la base de esa región pasa a ser el nuevo estado.
      - un cambio que YA volvió a la base en el cuadro siguiente es un parpadeo
        (cursor, reloj): no se guarda y la base no se mueve.
    """
    if len(cuadros_con_t) < 2:
        return []
    area_total = ancho * alto
    momentos: list[dict] = []
    base = bytearray(cuadros_con_t[0][1])
    parpadeos_confirmados: set[frozenset[tuple[int, int]]] = set()
    i = 1
    while i < len(cuadros_con_t):
        t_k, f_k = cuadros_con_t[i]
        cambiados = _diff_cambiados(bytes(base), f_k, ancho, umbral)
        if not cambiados:
            i += 1
            continue
        fv = array.array("B", f_k)
        sigv = array.array("B", cuadros_con_t[i + 1][1]) if i + 1 < len(cuadros_con_t) else None
        for componente in sorted(_componentes(cambiados, dilatacion), key=min):
            x0, y0, x1, y1 = _bbox_de(componente)
            frac_px = len(componente) / area_total
            if frac_px < area_min_frac:
                continue  # ruido: no mueve la base en esta región
            dy_max = min(y1 - y0, DESPLAZAMIENTO_DY_MAX)
            if y1 - y0 >= DESPLAZAMIENTO_ALTO_MIN and _desplazamiento(
                    bytes(base), f_k, ancho, (x0, y0, x1, y1), umbral=umbral, dy_max=dy_max,
                    residual_max_frac=DESPLAZAMIENTO_RESIDUAL_MAX_FRAC) is not None:
                # B1: es un scroll (el contenido se desplazó), no un momento -> absorbe
                # en la base para no seguir comparando contra la pantalla de antes.
                for x, y in componente:
                    base[y * ancho + x] = fv[y * ancho + x]
                continue
            frac_bbox = (x1 - x0) * (y1 - y0) / area_total
            if frac_bbox > area_max_frac:
                for x, y in componente:
                    base[y * ancho + x] = fv[y * ancho + x]
                continue
            clave = frozenset(componente)
            if sigv is not None:
                volvio = all(abs(base[y * ancho + x] - sigv[y * ancho + x]) <= umbral
                              for x, y in componente)
            else:
                # último cuadro: no hay siguiente para confirmar que "vuelve", pero si
                # esta MISMA región ya se vio parpadear antes (aparece y vuelve a la
                # base) en esta misma secuencia, el muestreo cayó de nuevo en fase "on"
                # por casualidad -no es un momento nuevo- (N3: una animación que no para
                # no es un momento por cada muestra).
                volvio = clave in parpadeos_confirmados
            if volvio:
                parpadeos_confirmados.add(clave)
                continue
            momentos.append({
                "t": t_k,
                "x": round(x0 * escala_x), "y": round(y0 * escala_y),
                "w": round((x1 - x0) * escala_x), "h": round((y1 - y0) * escala_y),
                "importancia": round(frac_px, 6),
            })
            for x, y in componente:
                base[y * ancho + x] = fv[y * ancho + x]
        i += 1
    return momentos


def _dimensiones(path: Path) -> tuple[int, int]:
    """(ancho, alto) en píxeles del stream de video de `path`."""
    out = editar.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                      "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")
    return int(w), int(h)


def _muestras(raw: Path, inicio: float, fin: float, fps: float,
              ancho: int) -> tuple[list[bytes], int, int, float, float]:
    """Cuadros en escala de grises de `raw` entre [`inicio`, `fin`), muestreados a `fps`
    y reducidos a `ancho` px de ancho (par de alto, preservando la relación de aspecto).

    Devuelve (cuadros, ancho_real, alto_real, escala_x, escala_y): los factores para
    volver a píxeles del crudo, UNO POR EJE (N1: redondear `alto` a un entero par corre
    la escala vertical real respecto de `w0/ancho` -hasta 34px en resoluciones no 16:9
    como 1280x1024 o 3440x1440-, así que no alcanza una sola escala para los dos ejes).
    """
    w0, h0 = _dimensiones(raw)
    escala_x = w0 / ancho
    alto = max(2, round(h0 / escala_x / 2) * 2)
    escala_y = h0 / alto
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "muestras.raw"
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}",
                    "-i", str(raw), "-vf", f"fps={fps},scale={ancho}:{alto}:flags=area",
                    "-f", "rawvideo", "-pix_fmt", "gray", str(salida)])
        datos = salida.read_bytes()
    tam = ancho * alto
    cuadros = [datos[i:i + tam] for i in range(0, len(datos) - tam + 1, tam)]
    return cuadros, ancho, alto, escala_x, escala_y


def detectar_momentos(raw: Path, inicio: float, fin: float, *, fps: float = FPS_MUESTREO,
                       ancho: int = ANCHO_MUESTRA, umbral: int = UMBRAL_GRIS,
                       area_min_frac: float = AREA_MIN_FRAC,
                       area_max_frac: float = AREA_MAX_FRAC) -> list[dict]:
    """[{t,x,y,w,h,importancia}] detectados en `raw` entre `inicio` y `fin` (segundos,
    en el eje del propio crudo)."""
    cuadros, anchop, altop, escala_x, escala_y = _muestras(raw, inicio, fin, fps, ancho)
    paso = 1.0 / fps
    con_t = [(inicio + i * paso, c) for i, c in enumerate(cuadros)]
    return _momentos_en_cuadros(con_t, anchop, altop, escala_x, escala_y, umbral=umbral,
                                area_min_frac=area_min_frac, area_max_frac=area_max_frac)

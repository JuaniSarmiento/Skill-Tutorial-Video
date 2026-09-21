#!/usr/bin/env python3
"""Tapa credenciales frame por frame: una caja por tramo, no una caja unica.

La posicion del secreto se mueve con el scroll. Unir todas las detecciones en un solo
rectangulo termina tapando media pantalla, asi que agrupamos por cercania temporal Y
espacial y emitimos un drawbox por grupo, activo solo en su ventana de tiempo.
"""
import os, re, subprocess, sys, pathlib, csv, io

# Los patrones NUNCA se hardcodean aca: este archivo se versiona, y un secreto
# escrito para taparlo en un video queda publicado en el repo, que es el mismo
# error del que este script existe para salvarte.
#
# Van en un archivo fuera del repo, una expresion por linea, comentarios con #:
#   ~/.config/tutorial-video/secretos.txt   (o $CENSURAR_PATRONES)
# Ejemplo de contenido (fragmentos, no el secreto entero: alcanza para el OCR):
#   1234567890        # prefijo del token del bot
#   micorreo          # usuario del mail
def cargar_patrones() -> re.Pattern:
    ruta = pathlib.Path(os.environ.get(
        "CENSURAR_PATRONES",
        pathlib.Path.home() / ".config/tutorial-video/secretos.txt"))
    if not ruta.exists():
        sys.exit(f"  Falta {ruta}. Escribi ahi los fragmentos a tapar, uno por linea.\n"
                 f"  mkdir -p {ruta.parent} && chmod 700 {ruta.parent}")
    pats = [l.split("#")[0].strip() for l in ruta.read_text().splitlines()]
    pats = [p for p in pats if p]
    if not pats:
        sys.exit(f"  {ruta} esta vacio: no hay nada que tapar.")
    print(f"  {len(pats)} patron(es) cargados desde {ruta}")
    return re.compile("|".join(re.escape(p) for p in pats), re.I)


PAT = cargar_patrones()
W = pathlib.Path('/tmp/censor-work'); W.mkdir(exist_ok=True)
PASO = 1.0          # muestreo fino: el scroll mueve el texto rapido
MARGEN_T = 1.2      # cuanto extender la caja antes y despues de cada deteccion

def dur(v):
    return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
                                 '-of','csv=p=0',str(v)],capture_output=True,text=True).stdout)

def detectar(video):
    d = dur(video); hits = []; t = 0.0
    f = W / f'{pathlib.Path(video).parent.name}.png'
    while t < d:
        subprocess.run(['ffmpeg','-y','-loglevel','error','-ss',f'{t:.2f}','-i',str(video),
                        '-frames:v','1',str(f)],capture_output=True)
        r = subprocess.run(['tesseract',str(f),'stdout','tsv'],capture_output=True,text=True)
        for row in csv.DictReader(io.StringIO(r.stdout), delimiter='\t', quoting=csv.QUOTE_NONE):
            txt = (row.get('text') or '').strip()
            if txt and PAT.search(txt):
                try:
                    hits.append((t, int(row['left']), int(row['top']),
                                 int(row['width']), int(row['height'])))
                except (ValueError, KeyError):
                    pass
        t += PASO
    return hits

def agrupar(hits):
    """Junta detecciones contiguas en el tiempo cuya caja esta cerca."""
    grupos = []
    for t, x, y, w, h in hits:
        for g in grupos:
            if (abs(g['y'] - y) < 40 and abs(g['x'] - x) < 120
                    and t - g['t1'] <= PASO * 2.5):
                g['x'] = min(g['x'], x); g['y'] = min(g['y'], y)
                g['x2'] = max(g['x2'], x + w); g['y2'] = max(g['y2'], y + h)
                g['t1'] = t
                break
        else:
            grupos.append({'x': x, 'y': y, 'x2': x + w, 'y2': y + h, 't0': t, 't1': t})
    return grupos

def main():
    v = pathlib.Path(sys.argv[1])
    dst = v.parent / 'final-joven-limpio.mp4'
    hits = detectar(v)
    if not hits:
        print(f"  {v.parent.name}: limpio, se copia tal cual")
        subprocess.run(['cp', str(v), str(dst)])
        return
    gs = agrupar(hits)
    filtros = []
    area_total = 0
    for g in gs:
        x = max(g['x'] - 14, 0); y = max(g['y'] - 10, 0)
        w = g['x2'] - x + 28; h = g['y2'] - y + 20
        t0 = max(g['t0'] - MARGEN_T, 0); t1 = g['t1'] + MARGEN_T
        area_total += w * h
        filtros.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black@1.0:t=fill:"
                       f"enable='between(t,{t0:.2f},{t1:.2f})'")
    prom = area_total // max(len(gs), 1)
    pct = 100 * prom / (1920 * 1080)
    print(f"  {v.parent.name}: {len(hits)} detecciones en {len(gs)} tramos · "
          f"caja promedio {prom} px ({pct:.1f}% de pantalla)")
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(v),
                    '-vf', ','.join(filtros),
                    '-c:v','libx264','-preset','medium','-crf','23',
                    '-c:a','copy',str(dst)], check=True)
    print(f"  {v.parent.name}: tapado -> {dst.name}")

main()

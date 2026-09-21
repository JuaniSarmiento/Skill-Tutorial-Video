#!/usr/bin/env python3
"""Vigila opencode hasta que haga falta intervenir.

Sale cuando: (a) el log registra un pedido de permiso nuevo, (b) hay una tool `question`
corriendo, (c) la sesión principal terminó su turno, o (d) se cumple `max` s.

DOS ARREGLOS respecto de la versión original:

1. El permiso se imprime COMPLETO. Antes se truncaba a 300 caracteres y `drive.sh`
   decidía sobre ese texto recortado: un comando peligroso más allá del corte pasaba
   el filtro y se aprobaba con "allow always". El guardrail fallaba ABIERTO.

2. El offset del log se puede pasar y se devuelve (`OFFSET=n`). Antes cada arranque
   se reposicionaba al final del archivo, así que todo lo que ocurría entre dos
   invocaciones (los ~5 s que tarda allow.sh) se perdía: si opencode pedía un segundo
   permiso ahí, nadie lo veía y se esperaba hasta el timeout.

uso: ocwatch.py [max_s=900] [idle_s=8] [--offset N]
"""
import json
import os
import sqlite3
import sys
import time

LOG = os.path.expanduser("~/.local/share/opencode/log/opencode.log")
DB = f"file:{os.path.expanduser('~')}/.local/share/opencode/opencode.db?mode=ro"
DIR = os.environ.get("OC_DIR", os.getcwd())

pos = [a for a in sys.argv if a.startswith("--")]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
maximum = int(args[0]) if args else 900
idle_need = int(args[1]) if len(args) > 1 else 8

offset = None
for i, a in enumerate(sys.argv):
    if a == "--offset":
        offset = int(sys.argv[i + 1])

# el log puede haber rotado o truncado: si el offset quedó más allá del final,
# empezamos de cero en vez de quedarnos ciegos para siempre.
tam = os.path.getsize(LOG) if os.path.exists(LOG) else 0
if offset is None:
    offset = tam
elif offset > tam:
    offset = 0

start = time.time()


def db_state() -> tuple[bool, bool]:
    con = sqlite3.connect(DB, uri=True)
    try:
        question = con.execute(
            "select count(*) from part p join session s on s.id = p.session_id where s.directory = ? "
            "and json_extract(p.data,'$.type')='tool' and json_extract(p.data,'$.tool')='question' "
            "and json_extract(p.data,'$.state.status') in ('running','pending')",
            (DIR,),
        ).fetchone()[0]
        row = con.execute(
            "select m.data, m.time_updated from message m join session s on s.id = m.session_id "
            "where s.directory = ? and s.parent_id is null order by m.time_created desc limit 1",
            (DIR,),
        ).fetchone()
    finally:
        con.close()
    done = False
    if row:
        data = json.loads(row[0])
        completed = data.get("time", {}).get("completed")
        done = (data.get("role") == "assistant" and completed is not None
                and time.time() - completed / 1000 >= idle_need)
    return question > 0, done


def salir(msg: str) -> None:
    print(msg)
    print(f"OFFSET={offset}")
    print(f"({int(time.time() - start)}s)")
    sys.exit(0)


while True:
    # leemos en BINARIO: con errors="replace" un byte inválido se vuelve 3 bytes de
    # U+FFFD y el offset calculado sobre el texto se desalinea del archivo real.
    with open(LOG, "rb") as fh:
        fh.seek(offset)
        crudo = fh.read()
    offset += len(crudo)
    new = crudo.decode("utf-8", errors="replace")

    pedidos = [l for l in new.splitlines() if "message=asking" in l and "permission=" in l]
    if pedidos:
        linea = pedidos[-1]
        # COMPLETO, sin truncar: quien filtra necesita ver todo el comando.
        salir("PERMISO: " + linea[linea.find("permission="):])

    for l in new.splitlines():
        if "level=ERROR" in l:
            print("ERROR:", l[:400])

    question, done = db_state()
    if question:
        salir("PREGUNTA pendiente")
    if done:
        salir("TURNO TERMINADO")
    if time.time() - start > maximum:
        salir("TIMEOUT, sigue trabajando")
    time.sleep(3)

#!/usr/bin/env python3
"""Vigila opencode hasta que haga falta intervenir.

Sale cuando: (a) el log registra un pedido de permiso nuevo, (b) hay una tool `question` corriendo,
(c) la sesión principal terminó su turno (último mensaje del asistente con time.completed) y pasó `idle` s,
o (d) se cumple `max` s.

uso: ocwatch.py [max_s=900] [idle_s=8]
"""
import json
import os
import os
import sqlite3
import sys
import time

LOG = os.path.expanduser("~/.local/share/opencode/log/opencode.log")
DB = f"file:{os.path.expanduser('~')}/.local/share/opencode/opencode.db?mode=ro"
DIR = os.environ.get("OC_DIR", os.getcwd())

maximum = int(sys.argv[1]) if len(sys.argv) > 1 else 900
idle_need = int(sys.argv[2]) if len(sys.argv) > 2 else 8
start = time.time()
offset = os.path.getsize(LOG)


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
        done = data.get("role") == "assistant" and completed is not None and time.time() - completed / 1000 >= idle_need
    return question > 0, done


while True:
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        new = fh.read()
    if any("message=asking" in l and "permission=" in l for l in new.splitlines()):
        line = [l for l in new.splitlines() if "message=asking" in l and "permission=" in l][-1]
        print("PERMISO:", line[line.find("permission="):][:300])
        break
    if "level=ERROR" in new:
        line = [l for l in new.splitlines() if "level=ERROR" in l][-1]
        print("ERROR:", line[:400])
    offset += len(new.encode("utf-8"))
    question, done = db_state()
    if question:
        print("PREGUNTA pendiente")
        break
    if done:
        print("TURNO TERMINADO")
        break
    if time.time() - start > maximum:
        print("TIMEOUT, sigue trabajando")
        break
    time.sleep(3)
print(f"({int(time.time() - start)}s)")

#!/usr/bin/env python3
"""Espera a que la última tool `question` de opencode tenga input y la imprime con el último texto del asistente.

uso: OC_DIR=/ruta/proyecto lastq.py
"""
import json
import os
import sqlite3
import time

DB = f"file:{os.path.expanduser('~')}/.local/share/opencode/opencode.db?mode=ro"
DIR = os.environ.get("OC_DIR", os.getcwd())
Q = ("select p.data from part p join session s on s.id=p.session_id where s.directory = ? "
     "and json_extract(p.data,'$.{k}')='{v}' order by p.time_created desc limit 1")
for _ in range(100):
    c = sqlite3.connect(DB, uri=True)
    r = c.execute(Q.format(k="tool", v="question"), (DIR,)).fetchone()
    t = c.execute(Q.format(k="type", v="text"), (DIR,)).fetchone()
    c.close()
    if r and json.loads(r[0])["state"].get("input", {}).get("questions"):
        if t:
            print(json.loads(t[0])["text"])
        print("-----")
        for q in json.loads(r[0])["state"]["input"]["questions"]:
            print("Q:", q["question"], "(multiple)" if q.get("multiple") else "")
            for i, o in enumerate(q["options"], 1):
                print(f"  {i}. {o['label']} — {o.get('description', '')}")
        break
    time.sleep(3)

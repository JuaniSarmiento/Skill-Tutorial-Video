#!/usr/bin/env python3
"""Muestra lo último que pasó en las sesiones de opencode de un directorio.

uso: oclog.py [--dir PATH] [--n N] [--full]
"""
import argparse
import json
import os
import sqlite3
import time

DB = f"file:{os.path.expanduser('~')}/.local/share/opencode/opencode.db?mode=ro"


def short(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ⏎ ")
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("OC_DIR", os.getcwd()))
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    lim = 4000 if args.full else 400

    con = sqlite3.connect(DB, uri=True)
    sessions = {
        sid: (title, parent)
        for sid, title, parent in con.execute(
            "select id, title, parent_id from session where directory = ?", (args.dir,)
        )
    }
    if not sessions:
        print("sin sesiones")
        return
    marks = ",".join("?" * len(sessions))
    rows = con.execute(
        f"select p.session_id, p.time_updated, p.data, m.data from part p join message m on m.id = p.message_id "
        f"where p.session_id in ({marks}) order by p.time_created desc limit ?",
        (*sessions, args.n),
    ).fetchall()
    now = time.time()
    for sid, updated, pdata, mdata in reversed(rows):
        part = json.loads(pdata)
        role = json.loads(mdata).get("role", "?")
        tag = "sub" if sessions[sid][1] else "main"
        age = int(now - updated / 1000)
        kind = part.get("type")
        head = f"[{tag} {role} -{age}s]"
        if kind == "text":
            print(head, "TEXT:", short(part.get("text", ""), lim))
        elif kind == "reasoning":
            print(head, "THINK:", short(part.get("text", ""), 160))
        elif kind == "tool":
            state = part.get("state", {})
            print(
                head,
                f"TOOL {part.get('tool')} [{state.get('status')}]",
                "in:", short(state.get("input", {}), lim),
                "| out:", short(state.get("output", state.get("error", "")), lim),
            )
        elif kind in ("step-start", "step-finish"):
            continue
        else:
            print(head, kind, short(part, 200))


if __name__ == "__main__":
    main()

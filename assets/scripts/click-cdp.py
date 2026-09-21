#!/usr/bin/env python3
"""Hace click en un botón de la app de OpenCode por su texto, vía CDP.
uso: click-cdp.py 'Permitir siempre' [--puerto N]
"""
import json, sys, urllib.request
from websocket import create_connection

puerto = 9222
for i, a in enumerate(sys.argv):
    if a == "--puerto": puerto = int(sys.argv[i + 1])
texto = [a for a in sys.argv[1:] if not a.startswith("--")][0]

data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json", timeout=10))
url = next(t["webSocketDebuggerUrl"] for t in data if t.get("type") == "page")
ws = create_connection(url, timeout=20)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": f"""
  (() => {{
    const objetivo = {json.dumps(texto)}.toLowerCase();
    const els = [...document.querySelectorAll('button, [role="button"], a, div')];
    const hit = els.reverse().find(e =>
      (e.innerText || '').trim().toLowerCase() === objetivo && e.offsetParent !== null);
    if (!hit) return 'NO-ENCONTRADO';
    hit.click();
    return 'CLICK: ' + (e => e.trim().slice(0,40))(hit.innerText);
  }})()
""", "returnByValue": True}}))
while True:
    r = json.loads(ws.recv())
    if r.get("id") == 1:
        print("  ", r.get("result", {}).get("result", {}).get("value", r))
        break

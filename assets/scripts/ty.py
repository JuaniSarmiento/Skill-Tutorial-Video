#!/usr/bin/env python3
"""Tipea texto en la ventana de opencode; los caracteres no ASCII van de a uno y lentos (xdotool los pierde)."""
import os, subprocess, sys, time
text = sys.argv[1]
subprocess.run(["wmctrl", "-i", "-a", os.environ["OC_WIN"]]); time.sleep(0.6)
buf = ""
def flush():
    global buf
    if buf:
        subprocess.run(["xdotool", "type", "--delay", "22", buf]); buf = ""
for ch in text:
    if ord(ch) < 128:
        buf += ch
    else:
        flush(); time.sleep(0.12)
        subprocess.run(["xdotool", "type", "--delay", "60", ch]); time.sleep(0.12)
flush()
if "--enter" in sys.argv:
    time.sleep(0.8); subprocess.run(["xdotool", "key", "Return"])

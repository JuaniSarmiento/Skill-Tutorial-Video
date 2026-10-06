## Diapositivas de cátedra: `presentaciones/`

Para videos de una materia de UTN TUPaD, las diapositivas las arma el módulo
**`presentaciones/`** de esta skill (antes era la skill aparte `presentaciones-tupad`), no las
escenas de arriba: es el estilo institucional (azul UTN, tarjetas, código sobre gris, pie con
logo y numeración) y genera `.pptx` editable + `.pdf` desde un YAML. Las escenas animadas quedan
para videos propios. **Leé `presentaciones/SKILL.md` antes de armar o corregir diapositivas**: su
flujo (preflight, spec, build, revisar cada diapositiva por imagen) es obligatorio.

```bash
P=<skill>/presentaciones
# una vez: python3 -m venv $P/.venv && $P/.venv/bin/pip install -r $P/scripts/requirements.txt
$P/.venv/bin/python $P/scripts/preflight.py
$P/.venv/bin/python $P/scripts/build.py presentacion.yaml -o salida --pdf --hoja
```

- **Si la cátedra ya tiene la presentación**, se usa esa (es material que el alumno también lee).
  Si no la hay o hay que corregirla, se arma o se corrige desde su YAML (no editando el `.pptx` a
  mano: si se regenera, los retoques manuales se pierden).
- **El código y las salidas salen de ejecutar los `.py`**, y la pila de llamadas o el árbol de
  recursión se dibujan desde una traza real (`imagen: {diagrama: pila|arbol, ...}`). Las salidas
  de la diapositiva y las de la terminal del video coinciden porque salen del mismo programa.
- **Del PDF al video**: cada página a 1920x1080 (`pdftoppm -r 120 -png` y encuadre sin deformar)
  como tramo de imagen fija a pantalla completa; los recuadros sobre lo que se nombra y los
  cortes al editor/terminal se sincronizan con la voz. El método completo, probado en los videos
  de la U10 de Programación I, está en
  `~/Proyectos/Video-Tutoriales/u10-recursividad/produccion/` (`LEEME.md` y `scripts/armar.py`).
- **Revelado por partes sin animar**: para una diapositiva densa, generar con la spec variantes
  que muestren una tarjeta por vez y pasarlas con cortes (no viola "solo cortes").
- Las dos skills comparten las reglas que importan: código leído de archivos reales, salidas
  ejecutadas, ninguna ruta personal en pantalla (`/tmp/recursividad/`, carpeta real) y DejaVu
  Sans Mono sin ligaduras (`==` no se puede ver como un símbolo).

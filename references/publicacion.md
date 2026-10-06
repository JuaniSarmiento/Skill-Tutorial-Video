## Publicar

- `file_upload` de la extensión acepta ≤10 MB por llamada → comprimir con `-crf 29–34 -tune stillimage`.
- YouTube Studio: el primer tipeo en título/descripción tras subir se pierde → repetir en otro tool call y verificar con zoom. "No es para niños": click por coordenada + zoom.
- YouTube tiene **límite diario de cargas** para canales sin verificar (~10): verificar teléfono en `youtube.com/verify` o esperar 24 h.
- YouTube no reemplaza archivos: subir nuevos y pasar los viejos a **Privado** (nunca borrar: lo hace el usuario).
- Drive: crear carpetas con el MCP de Drive (`create_file` con mimeType folder), subir con Chrome (Nuevo → Subir archivo → `find input type=file` → `file_upload`), compartir "Cualquier persona con el vínculo: Lector" desde la UI y verificar con `get_file_permissions`.

```bash
# comprimir para subir
ffmpeg -y -i videos/v01/final-argentina.mp4 -c:v libx264 -preset slow -crf 30 -tune stillimage -c:a aac -b:a 128k "drive/1 - Titulo.mp4"
```

**Publicar (YouTube/Drive público) requiere OK explícito del usuario**; avisar si el contenido
es una solución de TP antes del cierre. Ver también la regla dura en `SKILL.md`.

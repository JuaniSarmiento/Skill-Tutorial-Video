# Voces TTS usadas y cómo elegirlas

Las voces se definen en `assets/scripts/editar.py`. Cada voz tiene su carpeta de audios cacheados
(`videos/vNN/<voz>/NN.wav` + `.txt`): solo se regenera un tramo si cambia su texto.

## Proveedores probados (2026-09)

| Voz (`editar.py`) | Proveedor | Costo | Calidad / notas |
|---|---|---|---|
| `daniela` | Piper local, `es_AR-daniela-high` | Gratis, offline | Robótica. Necesita fonética en inglés ("esquils"). |
| `elevenlabs` | ElevenLabs API, voz prediseñada "Chris", modelo `eleven_flash_v2_5` | Free: 10.000 créditos/mes (flash = 0,5/carácter) | Natural pero acento neutro. **Cuenta free no puede usar voces de biblioteca por API** (402 `paid_plan_required`); Starter USD 6 las habilita. Free = sin uso comercial, pide crédito. |
| `fish` | Fish Audio, "Profesora Argentina", modelo `s2.1-pro-free`, speed 1.0 | Gratis por API (uso justo) | Buena; a velocidad normal suena apurada (~172 pal/min). |
| `profe` | Fish, Profesora Argentina, speed 0.8, pausas 0.8 s | Gratis | Femenina. Fue la elegida hasta 2026-09-17 (~135 pal/min). |
| `joven` | Fish, "Narrador Joven argentino", speed 0.8, pausas 0.8 s | Gratis | **PRINCIPAL desde 2026-09-17.** Masculina joven, tono claro y educativo (~118 pal/min). Es el default de `editar.py imagen`. |
| `mendoza` | Fish, "Hombre Argentino (Mendoza)", acento cuyano | Gratis | Masculina, cuyana. |
| — | Edge TTS `es-AR-TomasNeural` / `es-AR-ElenaNeural` (`uv run --with edge-tts edge-tts`) | Gratis, sin cuenta | Buena y rioplatense; uso no oficial del servicio de Edge (sin licencia comercial clara). |

IDs Fish (`reference_id`):
- Profesora Argentina: `55589185654d4d5abc1035280611fb65`
- Narrador Joven argentino: `b23ed8db79dd49feac23dacfdf762a18`
- Hombre Argentino (Mendoza): `dcda4aaeb81c4a95bb9ac659b6753e41`

## Buscar voces en Fish (sin key)

```bash
curl -s "https://api.fish.audio/model?page_size=20&sort_by=task_count&language=es&title=narrador%20argentino" \
  | python3 -c "import json,sys;[print(m['title'],m['task_count'],m['_id']) for m in json.load(sys.stdin)['items']]"
```

Descartar las que son clones de personas reales (nombre y apellido, famosos, streamers): riesgo legal y ético.

## Probar antes de rearmar todo

Generar LA MISMA frase con cada candidata y a la misma velocidad, guardarlas numeradas en una carpeta
(`mujeres/`, `hombres/`) y que el usuario elija escuchando. La descripción de la comunidad no garantiza calidad.

## Agregar una voz de Fish a editar.py

Sumar una entrada al dict `FISH_LENTAS` (`"nombre": "reference_id"`). Hereda speed 0.8, pausas 0.8 s,
margen de 1 s entre tramos y las reglas de pronunciación de `fish`.

## Keys

- ElevenLabs: `~/.config/elevenlabs/api_key`
- Fish Audio: `~/.config/fish/api_key`

Guardar con `umask 077` / `chmod 600`. Si el usuario las pegó en el chat, recomendar rotarlas.

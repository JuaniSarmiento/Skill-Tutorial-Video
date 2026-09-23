# Voces TTS usadas y cómo elegirlas

Las voces se definen en `assets/scripts/editar.py`. Cada voz tiene su carpeta de audios cacheados
(`videos/vNN/<voz>/NN.wav` + `.txt`): solo se regenera un tramo si cambia su texto.

## Proveedores probados (2026-09)

| Voz (`editar.py`) | Proveedor | Costo | Calidad / notas |
|---|---|---|---|
| `daniela` | Piper local, `es_AR-daniela-high` | Gratis, offline | Robótica. Necesita fonética en inglés ("esquils"). |
| `elevenlabs` | ElevenLabs API, voz prediseñada "Chris", modelo `eleven_flash_v2_5` | Free: 10.000 créditos/mes (flash = 0,5/carácter) | Natural pero acento neutro. **Cuenta free no puede usar voces de biblioteca por API** (402 `paid_plan_required`); Starter USD 6 las habilita. Free = sin uso comercial, pide crédito. |
| `fish` | Fish Audio, "Profesora Argentina", modelo `s2.1-pro-free`, speed 1.0 | Gratis por API (uso justo) | Buena; a velocidad normal suena apurada (~172 pal/min). |
| `profe` | Fish, Profesora Argentina, speed 0.8, pausas 0.8 s | Gratis | Femenina. Fue la elegida hasta 2026-09-17. **~155 pal/min medidos** (2026-09-22, 1363 palabras en 526 s de slots): el ~135 que decía antes subestimaba en un 15% y hacía estimar de más la duración. |
| `joven` | Fish, "Narrador Joven argentino", speed 0.8, pausas 0.8 s | Gratis | **PRINCIPAL desde 2026-09-17.** Masculina joven, tono claro y educativo (~118 pal/min). Es el default de `editar.py imagen`. |
| `mendoza` | Fish, "Hombre Argentino (Mendoza)", acento cuyano | Gratis | Masculina, cuyana. |
| `argentina` | Fish, "argentina", speed 0.80, pausas 0.45 | Gratis | **Femenina argentina, la más expresiva probada.** Tags `educational` / `energetic` / `enthusiastic`. 163-185 pal/min según el texto. Elegida el 2026-09-22 midiendo el rango de pitch sobre el MISMO texto en 9 voces. |
| — | Edge TTS `es-AR-TomasNeural` / `es-AR-ElenaNeural` (`uv run --with edge-tts edge-tts`) | Gratis, sin cuenta | Buena y rioplatense; uso no oficial del servicio de Edge (sin licencia comercial clara). |

IDs Fish (`reference_id`):
- Profesora Argentina: `55589185654d4d5abc1035280611fb65`
- Narrador Joven argentino: `b23ed8db79dd49feac23dacfdf762a18`
- Hombre Argentino (Mendoza): `dcda4aaeb81c4a95bb9ac659b6753e41`

## Cómo se eligió `argentina`, y cómo repetir el método

Medir gana a leer descripciones. El 2026-09-22 se buscaba una voz femenina "cálida,
docente, expresiva y argentina" y el método que funcionó fue este:

1. **Barrer el catálogo, no buscar por título.** `GET /model?page_size=100&page_number=N&language=es`
   devuelve 1000 modelos. Buscar por `title` no sirve: la biblioteca está llena de
   personajes de anime y de streamers, y el título no dice ni el género ni el acento.
2. **Filtrar por `tags`**, que sí traen `female` / `male`, la edad y el tono
   (`educational`, `energetic`, `warm`, `narration`). De 1000 modelos en español,
   375 tienen tag `female`.
3. **Puntuar contra `description` + `tags`** buscando acento (argentin/rioplat/porteño),
   calidez (warm/friendly/gentle), docencia (teach/educat/narrat) y expresividad.
4. **Generar EL MISMO texto con las finalistas** y medir el **rango de pitch**
   (percentil 90 menos percentil 10 de la F0). Ese número es la expresividad y ordena
   las voces objetivamente. Comparar textos distintos NO sirve: la misma voz da 149 Hz
   en un texto y 201 Hz en otro, porque el pitch promedio depende de qué se dice.
5. **Y recién ahí, escucharlas.** La medición ordena las candidatas; el oído elige.

Resultado de esa medición, mismo texto en las 9:

| voz | pitch | rango (expresividad) |
|---|---|---|
| `argentina` a 0.80 | 212 Hz | **116 Hz** |
| `profe` a 0.80 | 156 Hz | **51 Hz** — la más plana de las nueve |

**El `speed` no es monotónico.** `argentina` mide 116 Hz de expresividad a 0.80 y sólo
100 Hz a 0.84: acelerarla la aplana, no sólo la apura. Calibrar midiendo, no asumiendo.

**`FISH_PAUSA` no aplica a toda voz.** Con `argentina`, los valores 0.35, 0.45, 0.55 y
0.70 dan la MISMA duración al milisegundo: el filtro recorta silencios largos y esta voz
no tiene ninguno — cero pausas de más de 0.2 s, medido hasta un umbral de -28 dB. Habla
de corrido. Antes de tocar ese parámetro, comprobar que hay silencios que recortar.

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

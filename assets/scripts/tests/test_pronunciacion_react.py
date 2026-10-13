"""Reglas de pronunciación para React y TanStack Query (voz argentina de Fish).

Cada regla salió de generar la frase con la voz y transcribirla con Whisper
(12/10/2026, serie de Programación IV): tal cual se escribe, "useQuery" se oía
"Ease Query", "gcTime" se oía "easy time" / "healthy time" e "isPending" "Ease
pending". Con la escritura de la derecha, las tres se oyeron limpias. El .srt no se
ve afectado: usa el texto del guion, no esto.
"""
import editar


def test_los_hooks_y_opciones_de_tanstack_se_escriben_como_se_dicen():
    texto = "Con useQuery y useMutation, la query key, el staleTime, el gcTime e isPending."
    assert editar.adaptar(texto, "argentina") == (
        "Con iús kueri y iús miutéishon, la kueri ki, el steil taim, el ge ce taim e is pénding.")


def test_query_client_provider_va_entero_antes_que_query_client():
    assert editar.adaptar("el query client provider envuelve", "argentina") == "el kueri klaient provaider envuelve"
    assert editar.adaptar("creás un query client", "argentina") == "creás un kueri klaient"


def test_las_formas_con_espacio_tambien():
    assert editar.adaptar("el stale time y el gc time, is pending", "argentina") == (
        "el steil taim y el ge ce taim, is pénding")


def test_un_texto_sin_esos_terminos_no_cambia():
    texto = "Pensalo como una heladera: si está fresca, la usás."
    assert editar.adaptar(texto, "argentina") == texto

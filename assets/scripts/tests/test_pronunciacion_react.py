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


def test_query_sola_se_dice_kueri_y_no_pisa_a_useQuery():
    # "Para eso está Query" se oía "Para eso te acuerí" (piloto 7.1, 12/10/2026)
    assert editar.adaptar("Para eso está Query.", "argentina") == "Para eso está kueri."
    assert editar.adaptar("Con useQuery y Query", "argentina") == "Con iús kueri y kueri"


def test_useParams_y_la_palabra_id_suelta():
    # "useParams" se oía "Iverpans" / "Uber Pans" y "id vale" "y duale" (7.4, 12/10/2026)
    assert editar.adaptar("Se lee con useParams: id vale siete.", "argentina") == (
        "Se lee con iús párams: aidí vale siete.")
    assert editar.adaptar("se guarda en id. Y el id, siempre", "argentina") == (
        "se guarda en aidí. Y el aidí, siempre")


def test_id_dentro_de_otra_palabra_no_cambia():
    texto = "Un video ideal, decidido y rápido."
    assert editar.adaptar(texto, "argentina") == texto

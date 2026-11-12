from app.telegram.conector import formatear_respuesta


def test_capitaliza_la_respuesta():
    salida = {
        "ok": True,
        "datos": "evento creado: dentista, 13/11/2026 10:00 a 11:00.",
    }

    texto = formatear_respuesta(salida)

    assert texto.startswith("Evento creado")
    assert "dentista" in texto.lower()


def test_capitaliza_elementos_de_lista():
    salida = {
        "ok": True,
        "datos": "tienes 1 evento esta semana:\n\u2022 dentista \u2014 13/11/2026 10:00 a 11:00",
    }

    texto = formatear_respuesta(salida)

    assert "\u2022 Dentista" in texto
    assert texto.startswith("Tienes")

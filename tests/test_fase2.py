from app.agents.reglas import _respuesta_creacion_evento


def test_detecta_creacion_de_evento():
    respuesta = _respuesta_creacion_evento(
        "crea un evento dentista manana a las 10 durante 1 hora"
    )
    assert respuesta is not None
    assert respuesta["ok"] is True
    assert "dentista" in respuesta["datos"].lower()
    assert "10:00" in respuesta["datos"]


def test_no_detecta_consulta_de_agenda():
    assert _respuesta_creacion_evento("que eventos tengo hoy") is None

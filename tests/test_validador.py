from uuid import uuid4

from app.llm.validador import LLMValidador


def test_validador_aprueba_cancelar_evento():
    validador = LLMValidador(motor=None)
    resultado = validador.validar(
        uuid4(),
        "agenda_cancelar_evento",
        {"evento_id": "abc"},
    )
    assert resultado["ok"] is True


def test_validador_aprueba_reprogramar_evento():
    validador = LLMValidador(motor=None)
    resultado = validador.validar(
        uuid4(),
        "agenda_reprogramar_evento",
        {"evento_id": "abc"},
    )
    assert resultado["ok"] is True


def test_validador_aprueba_accion_desconocida():
    validador = LLMValidador(motor=None)
    resultado = validador.validar(
        uuid4(),
        "agenda_crear_evento",
        {"titulo": "Dentista"},
    )
    assert resultado["ok"] is True
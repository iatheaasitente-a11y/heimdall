from uuid import uuid4

from app.agents.agenda_paso_a_paso import AgendaPasoAPaso


def _crear_agenda(llamadas):
    def crear(usuario_id, datos):
        llamadas.append((usuario_id, datos))
        return {"ok": True, "datos": {"evento": datos}}

    return AgendaPasoAPaso(crear)


def test_pregunta_titulo_cuando_no_hay_datos():
    llamadas = []
    agenda = _crear_agenda(llamadas)
    resultado = agenda.procesar(uuid4(), uuid4(), "Quiero agendar")
    assert resultado["datos"]["pregunta"] == "¿Cómo se llama el evento?"
    assert llamadas == []


def test_flujo_completo_en_cuatro_mensajes():
    llamadas = []
    agenda = _crear_agenda(llamadas)
    usuario_id = uuid4()
    conversacion_id = uuid4()
    agenda.procesar(usuario_id, conversacion_id, "Quiero agendar dentista")
    agenda.procesar(usuario_id, conversacion_id, "mañana")
    agenda.procesar(usuario_id, conversacion_id, "a las 10")
    resultado = agenda.procesar(usuario_id, conversacion_id, "1 hora")
    assert resultado["ok"] is True
    assert len(llamadas) == 1
    datos = llamadas[0][1]
    assert datos["titulo"] == "dentista"
    assert datos["dia"] == "mañana"
    assert datos["hora"] == "10:00"
    assert datos["duracion"] == "1 horas"


def test_cancelar_borra_el_borrador():
    llamadas = []
    agenda = _crear_agenda(llamadas)
    usuario_id = uuid4()
    conversacion_id = uuid4()
    agenda.procesar(usuario_id, conversacion_id, "Quiero agendar dentista")
    resultado = agenda.procesar(usuario_id, conversacion_id, "cancela")
    assert resultado["datos"]["mensaje"] == "Agendado cancelado."
    assert llamadas == []


def test_mensaje_ajeno_sin_borrador_devuelve_none():
    llamadas = []
    agenda = _crear_agenda(llamadas)
    resultado = agenda.procesar(uuid4(), uuid4(), "Hola")
    assert resultado is None

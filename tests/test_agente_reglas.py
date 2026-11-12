from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.composicion import crear_composicion
from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.llm import MotorFalso

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    motor = MotorFalso()
    aplicacion = crear_composicion(conexion, lambda: AHORA, motor=motor)
    usuario = aplicacion.usuarios.registrar("Ana", zona_horaria="Europe/Madrid")
    try:
        yield aplicacion, usuario, motor
    finally:
        conexion.close()


def procesar(entorno, texto):
    aplicacion, usuario, _motor = entorno
    return aplicacion.router.procesar(usuario.id, uuid4(), texto)


def test_crea_evento_con_fecha_hora_y_duracion_explicitas(entorno):
    propuesta = procesar(
        entorno,
        "ma\u00f1ana a las cinco de la tarde reuni\u00f3n durante una hora",
    )

    assert propuesta["ok"] is True
    assert "reuni\u00f3n" in propuesta["datos"].lower()
    assert "Responde si para confirmar" in propuesta["datos"]

    creado = procesar(entorno, "si")

    assert creado["ok"] is True
    assert "Evento creado" in creado["datos"]
    assert "reuni\u00f3n" in creado["datos"].lower()
    assert "17:00" in creado["datos"]



def test_no_crea_evento_sin_confirmacion(entorno):
    procesar(
        entorno,
        "mañana a las cinco de la tarde reunión durante una hora",
    )

    eventos = entorno[0].herramientas.obtener(
        "agenda_eventos_del_dia"
    ).ejecutar(
        entorno[1].id,
        {"dia": "2026-10-24"},
    )

    assert eventos["datos"] == []


def test_cancela_evento_pendiente(entorno):
    procesar(
        entorno,
        "mañana a las cinco de la tarde reunión durante una hora",
    )

    cancelado = procesar(entorno, "no")

    assert cancelado["ok"] is True
    assert "cancelado" in cancelado["datos"].lower()


def test_pregunta_por_la_franja_de_una_hora_ambigua(entorno):
    resultado = procesar(entorno, "ma\u00f1ana a las cinco reuni\u00f3n")

    assert resultado == {
        "ok": False,
        "error": "\u00bfCu\u00e1nto dura el evento o a qu\u00e9 hora termina?",
    }
    assert entorno[0].herramientas.obtener("agenda_eventos_del_dia").ejecutar(
        entorno[1].id,
        {"dia": "2026-10-24"},
    )["datos"] == []



def test_pregunta_por_el_dia_que_falta_para_crear_evento(entorno):
    resultado = procesar(
        entorno,
        "crea evento a las cinco de la tarde durante una hora",
    )

    assert resultado["ok"] is False
    assert "¿Qué día quieres?" in resultado["error"]


def test_pregunta_por_la_duracion_que_falta_para_crear_evento(entorno):
    resultado = procesar(entorno, "mañana a las cinco de la tarde reunión")

    assert resultado["ok"] is False
    assert "¿Cuánto dura" in resultado["error"]


def test_programa_recordatorio_con_fecha_y_hora_explicitas(entorno):
    resultado = procesar(
        entorno,
        "recuérdame llamar a mamá el jueves a las diez de la mañana",
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["mensaje"] == "llamar a mamá"
    assert resultado["datos"]["programado_para"] == "2026-10-29T10:00:00+01:00"


def test_asume_manana_para_hora_ambigua_de_recordatorio(entorno):
    resultado = procesar(
        entorno,
        "recu\u00e9rdame llamar a mam\u00e1 el jueves a las diez",
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["mensaje"] == "llamar a mam\u00e1"
    assert resultado["datos"]["programado_para"] == "2026-10-29T10:00:00+01:00"



def test_pregunta_por_el_dia_que_falta_para_programar_recordatorio(entorno):
    resultado = procesar(
        entorno,
        "recuérdame llamar a mamá a las diez de la mañana",
    )

    assert resultado["ok"] is False
    assert "¿Qué día quieres?" in resultado["error"]


def test_pregunta_por_el_mensaje_que_falta_en_recordatorio(entorno):
    resultado = procesar(entorno, "recuérdame el jueves a las diez de la mañana")

    assert resultado["ok"] is False
    assert "¿Qué quieres que te recuerde?" in resultado["error"]


def test_registra_progreso_de_habito_solo_con_cantidad_y_dia_explicitos(entorno):
    usuario_id = entorno[1].id
    creado = entorno[0].herramientas.obtener("habitos_crear").ejecutar(
        usuario_id,
        {"nombre": "Agua", "unidad": "litros", "objetivo": 2},
    )

    resultado = procesar(entorno, "he bebido dos litros de agua hoy")

    assert creado["ok"] is True
    assert resultado["ok"] is True
    assert resultado["datos"]["habito_id"] == creado["datos"]["id"]
    assert resultado["datos"]["valor"] == 2


def test_pregunta_por_el_dia_que_falta_al_registrar_progreso(entorno):
    entorno[0].herramientas.obtener("habitos_crear").ejecutar(
        entorno[1].id,
        {"nombre": "Agua", "unidad": "litros"},
    )

    resultado = procesar(entorno, "he bebido dos litros de agua")

    assert resultado["ok"] is False
    assert "¿De qué día es ese progreso?" in resultado["error"]


def test_pregunta_por_la_cantidad_que_falta_al_registrar_progreso(entorno):
    resultado = procesar(entorno, "he bebido agua hoy")

    assert resultado["ok"] is False
    assert "¿Qué cantidad" in resultado["error"]


def test_consulta_progreso_de_habito_por_nombre_y_dia(entorno):
    usuario_id = entorno[1].id
    creado = entorno[0].herramientas.obtener("habitos_crear").ejecutar(
        usuario_id,
        {"nombre": "Agua", "unidad": "litros"},
    )
    entorno[0].herramientas.obtener("habitos_registrar_progreso").ejecutar(
        usuario_id,
        {
            "habito_id": creado["datos"]["id"],
            "valor": 2,
            "cuando": AHORA.astimezone(entorno[1].zona()),
        },
    )

    resultado = procesar(entorno, "¿cuánto llevo de agua hoy?")

    assert resultado["ok"] is True
    assert resultado["datos"] == 2


def test_consulta_racha_de_habito_por_nombre_y_dia(entorno):
    usuario_id = entorno[1].id
    creado = entorno[0].herramientas.obtener("habitos_crear").ejecutar(
        usuario_id,
        {"nombre": "Correr"},
    )
    entorno[0].herramientas.obtener("habitos_registrar_progreso").ejecutar(
        usuario_id,
        {
            "habito_id": creado["datos"]["id"],
            "valor": 1,
            "cuando": AHORA.astimezone(entorno[1].zona()),
        },
    )

    resultado = procesar(entorno, "¿qué racha tengo de correr hoy?")

    assert resultado["ok"] is True
    assert resultado["datos"] == 1


def test_pregunta_por_el_dia_que_falta_en_consulta_de_habito(entorno):
    entorno[0].herramientas.obtener("habitos_crear").ejecutar(
        entorno[1].id,
        {"nombre": "Agua"},
    )

    resultado = procesar(entorno, "¿cuánto llevo de agua?")

    assert resultado["ok"] is False
    assert "¿Para qué día" in resultado["error"]


def test_nombre_ambiguo_de_habito_devuelve_candidatos_y_pregunta(entorno):
    usuario_id = entorno[1].id
    for nombre in ("Agua", "Água"):
        entorno[0].herramientas.obtener("habitos_crear").ejecutar(
            usuario_id,
            {"nombre": nombre},
        )

    resultado = procesar(entorno, "¿cuánto llevo de agua hoy?")

    assert resultado["ok"] is False
    assert "¿Cuál quieres decir?" in resultado["error"]
    assert len(resultado["candidatos"]) == 2


def test_actualiza_progreso_de_objetivo_por_nombre_y_porcentaje(entorno):
    usuario_id = entorno[1].id
    creado = entorno[0].herramientas.obtener("objetivos_crear").ejecutar(
        usuario_id,
        {"nombre": "Leer 10 libros"},
    )

    resultado = procesar(
        entorno,
        "actualiza mi objetivo Leer 10 libros al 25%",
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["id"] == creado["datos"]["id"]
    assert resultado["datos"]["progreso"] == 25


def test_pregunta_por_el_porcentaje_que_falta_para_el_objetivo(entorno):
    resultado = procesar(entorno, "actualiza mi objetivo Leer 10 libros")

    assert resultado["ok"] is False
    assert "¿A qué porcentaje" in resultado["error"]


def test_ambiguedad_de_objetivo_pide_aclaracion(entorno):
    usuario_id = entorno[1].id
    for nombre in ("Correr", "Córrer"):
        entorno[0].herramientas.obtener("objetivos_crear").ejecutar(
            usuario_id,
            {"nombre": nombre},
        )

    resultado = procesar(entorno, "actualiza mi objetivo correr al 20%")

    assert resultado["ok"] is False
    assert "¿Cuál quieres decir?" in resultado["error"]
    assert len(resultado["candidatos"]) == 2


@pytest.mark.parametrize(
    "texto",
    ("lista lo de hoy", "lista mis eventos de hoy", "¿Qué hay para hoy?"),
)
def test_listar_lo_de_hoy_usa_resumen_y_no_consulta_el_motor(entorno, texto):
    resultado = procesar(entorno, texto)

    assert resultado["ok"] is True
    assert resultado["datos"]["dia"] == "2026-10-23"
    assert entorno[2].ultimo_historial == []

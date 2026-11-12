from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.composicion import crear_composicion
from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.llm import MotorFalso

AHORA = datetime(2026, 11, 12, 14, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def _entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    aplicacion = crear_composicion(
        conexion,
        lambda: AHORA,
        motor=MotorFalso(),
    )
    usuario = aplicacion.usuarios.registrar(
        "Ana",
        zona_horaria="Europe/Madrid",
    )
    return aplicacion, usuario


def test_consulta_la_proxima_cita():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-13T16:00:00+01:00",
            "termina": "2026-11-13T17:00:00+01:00",
        },
    )

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cual es mi proxima cita?",
    )

    assert resultado["ok"] is True
    assert "Gimnasio" in resultado["datos"]
    assert "13/11/2026" in resultado["datos"]
    assert "16:00" in resultado["datos"]


def test_consulta_huecos_libres_de_una_franja():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-13T16:00:00+01:00",
            "termina": "2026-11-13T17:00:00+01:00",
        },
    )

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "huecos libres el viernes de 10 a 18",
    )

    assert resultado["ok"] is True
    assert "10:00 a 16:00" in resultado["datos"]
    assert "17:00 a 18:00" in resultado["datos"]


def test_pide_el_dia_para_consultar_huecos():
    aplicacion, usuario = _entorno()

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "huecos libres",
    )

    assert resultado["ok"] is False
    assert "¿De qué día" in resultado["error"]

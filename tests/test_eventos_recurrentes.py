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


def test_propone_tres_eventos_recurrentes():
    aplicacion, usuario = _entorno()

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "gimnasio lunes, miercoles y viernes a las 15 durante 1 hora",
    )

    assert propuesta["ok"] is True
    assert "3 eventos" in propuesta["datos"]
    assert "gimnasio" in propuesta["datos"].lower()
    assert "16/11/2026 15:00" in propuesta["datos"]
    assert "18/11/2026 15:00" in propuesta["datos"]
    assert "13/11/2026 15:00" in propuesta["datos"]

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert "3 eventos" in resultado["datos"]

    for dia in (16, 18, 13):
        eventos = aplicacion.herramientas.obtener(
            "agenda_eventos_del_dia"
        ).ejecutar(
            usuario.id,
            {"dia": f"2026-11-{dia:02d}"},
        )
        assert len(eventos["datos"]) == 1


def test_rechaza_si_un_dia_choca():
    aplicacion, usuario = _entorno()
    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Dentista",
            "comienza": "2026-11-16T15:00:00+01:00",
            "termina": "2026-11-16T16:00:00+01:00",
        },
    )

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "gimnasio lunes, miercoles y viernes a las 15 durante 1 hora",
    )

    assert resultado["ok"] is False
    assert "Ya tienes" in resultado["error"]


def test_cancela_eventos_recurrentes_pendientes():
    aplicacion, usuario = _entorno()

    aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "gimnasio lunes, miercoles y viernes a las 15 durante 1 hora",
    )

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "no")

    assert resultado["ok"] is True
    assert "cancelado" in resultado["datos"].lower()

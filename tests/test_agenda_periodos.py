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


def _crear_evento(aplicacion, usuario, dia, hora):
    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": f"2026-11-{dia:02d}T{hora:02d}:00:00+01:00",
            "termina": f"2026-11-{dia:02d}T{hora + 1:02d}:00:00+01:00",
        },
    )


def test_consulta_semana_actual_vacia():
    aplicacion, usuario = _entorno()
    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "que tengo esta semana?",
    )
    assert resultado["ok"] is True
    assert "no tienes eventos esta semana" in resultado["datos"].lower()


def test_consulta_proxima_semana():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, 16, 10)
    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "que tengo la proxima semana?",
    )
    assert resultado["ok"] is True
    assert "Gimnasio" in resultado["datos"]


def test_consulta_mes_actual():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, 20, 18)
    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "que tengo este mes?",
    )
    assert resultado["ok"] is True
    assert "Gimnasio" in resultado["datos"]


def test_consulta_fin_de_semana_vacia():
    aplicacion, usuario = _entorno()
    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "que tengo este fin de semana?",
    )
    assert resultado["ok"] is True
    assert "no tienes eventos este fin de semana" in resultado["datos"].lower()


def test_rechaza_evento_que_solapa():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, 13, 10)

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento reunion manana a las 10 durante 1 hora",
    )

    assert resultado["ok"] is False
    assert "Ya tienes" in resultado["error"]


def test_avisa_si_repite_nombre_otra_hora():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, 13, 10)

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento gimnasio manana a las 18 durante 1 hora",
    )

    assert resultado["ok"] is True
    assert "Ya tienes un evento con ese nombre" in resultado["datos"]

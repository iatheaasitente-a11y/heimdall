from datetime import UTC, datetime

from app.composicion import crear_composicion
from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema


def test_composicion_usa_reloj_y_zona_del_usuario_para_el_dia():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    reloj = lambda: datetime(2026, 11, 12, 1, 0, tzinfo=UTC)
    try:
        aplicacion = crear_composicion(conexion, reloj)
        usuario = aplicacion.usuarios.registrar(
            "Ana",
            zona_horaria="America/Los_Angeles",
        )

        resultado = aplicacion.router.procesar(
            usuario.id,
            usuario.id,
            "¿Qué tengo hoy?",
        )

        assert resultado == {
            "ok": True,
            "datos": {
                "dia": "2026-11-11",
                "eventos": [],
                "habitos_pendientes": [],
                "recordatorios": [],
            },
        }
    finally:
        conexion.close()

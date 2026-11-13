from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda

MAD = ZoneInfo("Europe/Madrid")


def madrid(dia, hora, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=MAD)


def _crear_entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    usuarios = RepositorioUsuariosSQLite(conexion)
    eventos = RepositorioEventosSQLite(conexion)
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    agenda = ServicioAgenda(usuarios, eventos)
    return agenda, usuario, conexion


def test_crear_evento_todo_el_dia_ajusta_horas():
    agenda, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id,
        "Día libre",
        madrid(23, 10),
        madrid(23, 18),
        todo_el_dia=True,
    )
    assert evento.todo_el_dia is True
    assert evento.comienza == madrid(23, 0, 0)
    assert evento.termina.hour == 23
    assert evento.termina.minute == 59
    conexion.close()


def test_evento_todo_el_dia_bloquea_todo_el_dia():
    agenda, usuario, conexion = _crear_entorno()
    agenda.crear_evento(
        usuario.id,
        "Día libre",
        madrid(23, 10),
        madrid(23, 18),
        todo_el_dia=True,
    )
    import pytest
    from app.services.errores import ConflictoDeHorario
    with pytest.raises(ConflictoDeHorario):
        agenda.crear_evento(
            usuario.id,
            "Reunión",
            madrid(23, 15),
            madrid(23, 16),
        )
    conexion.close()


def test_evento_normal_no_afectado_por_todo_el_dia():
    agenda, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id,
        "Reunión",
        madrid(23, 10),
        madrid(23, 11),
    )
    assert evento.todo_el_dia is False
    assert evento.comienza == madrid(23, 10)
    conexion.close()

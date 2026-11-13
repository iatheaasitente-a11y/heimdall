from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda
from app.services.agenda_titulo import ServicioAgendaPorTitulo
from app.services.errores import EventoNoEncontrado

MAD = ZoneInfo("Europe/Madrid")


def madrid(dia, hora, minuto=0):
    return datetime(2026, 11, dia, hora, minuto, tzinfo=MAD)


def _crear_entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    usuarios = RepositorioUsuariosSQLite(conexion)
    eventos = RepositorioEventosSQLite(conexion)
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    agenda = ServicioAgenda(usuarios, eventos)
    por_titulo = ServicioAgendaPorTitulo(agenda)
    return agenda, por_titulo, usuario, conexion


def test_cancelar_por_titulo_cancela_el_evento():
    agenda, por_titulo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Dentista", madrid(20, 10), madrid(20, 11)
    )
    por_titulo.cancelar_por_titulo(usuario.id, "Dentista")
    actualizado = agenda.obtener_evento(usuario.id, evento.id)
    assert actualizado.estado.value == "cancelado"
    conexion.close()


def test_reprogramar_por_titulo_cambia_las_horas():
    agenda, por_titulo, usuario, conexion = _crear_entorno()
    agenda.crear_evento(
        usuario.id, "Reunión", madrid(20, 10), madrid(20, 11)
    )
    por_titulo.reprogramar_por_titulo(
        usuario.id, "Reunión", madrid(20, 15), madrid(20, 16)
    )
    eventos = agenda.listar_eventos(usuario.id)
    assert eventos[0].comienza == madrid(20, 15)
    conexion.close()


def test_cancelar_por_titulo_inexistente_lanza_error():
    agenda, por_titulo, usuario, conexion = _crear_entorno()
    with pytest.raises(EventoNoEncontrado):
        por_titulo.cancelar_por_titulo(usuario.id, "No existe")
    conexion.close()


def test_reprogramar_por_titulo_inexistente_lanza_error():
    agenda, por_titulo, usuario, conexion = _crear_entorno()
    with pytest.raises(EventoNoEncontrado):
        por_titulo.reprogramar_por_titulo(
            usuario.id, "No existe", madrid(20, 10), madrid(20, 11)
        )
    conexion.close()

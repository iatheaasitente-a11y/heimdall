from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.reminder import EstadoRecordatorio
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_recordatorios import RepositorioRecordatoriosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda

MAD = ZoneInfo("Europe/Madrid")
AHORA = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)


def madrid(dia, hora, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=MAD)


def _crear_entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    usuarios = RepositorioUsuariosSQLite(conexion)
    eventos = RepositorioEventosSQLite(conexion)
    repo = RepositorioRecordatoriosSQLite(conexion)
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    agenda = ServicioAgenda(usuarios, eventos, repo)
    return agenda, repo, usuario, conexion


def test_crear_evento_genera_recordatorio_automatico():
    agenda, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Dentista", madrid(23, 18), madrid(23, 19)
    )
    recordatorios = repo.listar_de_evento(evento.id)
    assert len(recordatorios) == 1
    recordatorio = recordatorios[0]
    assert recordatorio.evento_id == evento.id
    assert recordatorio.programado_para == evento.comienza
    assert recordatorio.estado == EstadoRecordatorio.PENDIENTE
    conexion.close()


def test_recordatorio_automatico_usa_zona_del_usuario():
    agenda, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Reunión", madrid(23, 18), madrid(23, 19)
    )
    recordatorios = repo.listar_de_evento(evento.id)
    assert len(recordatorios) == 1
    assert "Reunión empieza a las 18:00" in recordatorios[0].mensaje
    conexion.close()


def test_cancelar_evento_cancela_recordatorio_automatico():
    agenda, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Gimnasio", madrid(23, 18), madrid(23, 19)
    )
    recordatorios = repo.listar_de_evento(evento.id)
    assert len(recordatorios) == 1
    agenda.cancelar_evento(usuario.id, evento.id)
    recordatorio = repo.obtener(recordatorios[0].id)
    assert recordatorio.estado == EstadoRecordatorio.CANCELADO
    conexion.close()


def test_completar_evento_cancela_recordatorio_automatico():
    agenda, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Reunión", madrid(23, 18), madrid(23, 19)
    )
    recordatorios = repo.listar_de_evento(evento.id)
    assert len(recordatorios) == 1
    agenda.completar_evento(usuario.id, evento.id)
    recordatorio = repo.obtener(recordatorios[0].id)
    assert recordatorio.estado == EstadoRecordatorio.CANCELADO
    conexion.close()


def test_reprogramar_evento_desplaza_recordatorio_automatico():
    agenda, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Reunión", madrid(23, 18), madrid(23, 19)
    )
    recordatorios = repo.listar_de_evento(evento.id)
    assert len(recordatorios) == 1
    agenda.reprogramar_evento(
        usuario.id, evento.id, madrid(23, 20), madrid(23, 21)
    )
    recordatorio = repo.obtener(recordatorios[0].id)
    assert recordatorio.programado_para == madrid(23, 20)
    assert recordatorio.estado == EstadoRecordatorio.PENDIENTE
    conexion.close()

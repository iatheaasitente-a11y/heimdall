from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.reminder import EstadoRecordatorio
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_recordatorios import RepositorioRecordatoriosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda
from app.services.avisos_previos import ServicioAvisosPrevios
from app.services.recordatorios import ServicioRecordatorios

MAD = ZoneInfo("Europe/Madrid")
AHORA = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)


def madrid(dia, hora, minuto=0):
    return datetime(2026, 11, dia, hora, minuto, tzinfo=MAD)


def _crear_entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    usuarios = RepositorioUsuariosSQLite(conexion)
    eventos = RepositorioEventosSQLite(conexion)
    repo = RepositorioRecordatoriosSQLite(conexion)
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    agenda = ServicioAgenda(usuarios, eventos, repo)
    avisos = ServicioRecordatorios(usuarios, eventos, repo, reloj=lambda: AHORA)
    previos = ServicioAvisosPrevios(avisos)
    return agenda, previos, repo, usuario, conexion


def test_programar_aviso_previo_30_minutos():
    agenda, previos, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Dentista", madrid(20, 18), madrid(20, 19)
    )
    r = previos.programar_aviso_previo(usuario.id, evento.id, 30)
    assert r.programado_para == madrid(20, 17, 30)
    assert r.estado == EstadoRecordatorio.PENDIENTE
    conexion.close()


def test_programar_aviso_previo_60_minutos():
    agenda, previos, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Reunión", madrid(20, 18), madrid(20, 19)
    )
    r = previos.programar_aviso_previo(usuario.id, evento.id, 60)
    assert r.programado_para == madrid(20, 17, 0)
    conexion.close()


def test_aviso_previo_se_cancela_con_el_evento():
    agenda, previos, repo, usuario, conexion = _crear_entorno()
    evento = agenda.crear_evento(
        usuario.id, "Gimnasio", madrid(20, 18), madrid(20, 19)
    )
    r = previos.programar_aviso_previo(usuario.id, evento.id, 30)
    agenda.cancelar_evento(usuario.id, evento.id)
    assert repo.obtener(r.id).estado == EstadoRecordatorio.CANCELADO
    conexion.close()

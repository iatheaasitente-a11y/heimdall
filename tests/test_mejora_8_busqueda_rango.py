from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.schedule import EstadoEvento
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda
from app.services.busqueda_eventos import ServicioBusquedaEventos

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
    busqueda = ServicioBusquedaEventos(agenda)
    return agenda, busqueda, usuario, conexion


def test_busqueda_por_rango_devuelve_eventos_en_rango():
    agenda, busqueda, usuario, conexion = _crear_entorno()
    agenda.crear_evento(usuario.id, "Dentista", madrid(20, 10), madrid(20, 11))
    agenda.crear_evento(usuario.id, "Reunión", madrid(22, 10), madrid(22, 11))
    resultados = busqueda.buscar(
        usuario.id, madrid(20, 0), madrid(21, 23, 59)
    )
    assert len(resultados) == 1
    assert resultados[0].titulo == "Dentista"
    conexion.close()


def test_busqueda_con_filtro_titulo():
    agenda, busqueda, usuario, conexion = _crear_entorno()
    agenda.crear_evento(usuario.id, "Dentista", madrid(20, 10), madrid(20, 11))
    agenda.crear_evento(usuario.id, "Reunión", madrid(20, 15), madrid(20, 16))
    resultados = busqueda.buscar(
        usuario.id, madrid(20, 0), madrid(20, 23, 59), titulo="dent"
    )
    assert len(resultados) == 1
    assert resultados[0].titulo == "Dentista"
    conexion.close()


def test_busqueda_con_filtro_estado():
    agenda, busqueda, usuario, conexion = _crear_entorno()
    e1 = agenda.crear_evento(usuario.id, "Dentista", madrid(20, 10), madrid(20, 11))
    agenda.crear_evento(usuario.id, "Reunión", madrid(20, 15), madrid(20, 16))
    agenda.cancelar_evento(usuario.id, e1.id)
    resultados = busqueda.buscar(
        usuario.id, madrid(20, 0), madrid(20, 23, 59), estado=EstadoEvento.CANCELADO
    )
    assert len(resultados) == 1
    assert resultados[0].titulo == "Dentista"
    conexion.close()


def test_busqueda_sin_resultados_devuelve_lista_vacia():
    agenda, busqueda, usuario, conexion = _crear_entorno()
    resultados = busqueda.buscar(
        usuario.id, madrid(20, 0), madrid(20, 23, 59)
    )
    assert resultados == []
    conexion.close()

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.message import Conversacion, Mensaje, RolMensaje
from app.domain.relations import historial_para_modelo
from app.domain.user import Usuario
from app.repositories.interfaces import RepositorioConversaciones, RepositorioMensajes
from app.repositories.sqlite_conversaciones import (
    RepositorioConversacionesSQLite,
    RepositorioMensajesSQLite,
)
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite


@pytest.fixture
def repos():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    try:
        yield (
            RepositorioUsuariosSQLite(conexion),
            RepositorioConversacionesSQLite(conexion),
            RepositorioMensajesSQLite(conexion),
        )
    finally:
        conexion.close()


def hora(h, minuto=0):
    return datetime(2026, 10, 23, h, minuto, tzinfo=UTC)


def crear_conversacion(usuarios, conversaciones, titulo="Planes", fecha=None):
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    conversacion = Conversacion(usuario.id, titulo)
    if fecha is not None:
        conversacion.fecha_creacion = fecha
    conversaciones.guardar(conversacion)
    return usuario, conversacion


def test_conversacion_guardar_y_obtener_devuelve_la_misma(repos):
    usuarios, conversaciones, _ = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    c.activa = False
    conversaciones.guardar(c)
    assert conversaciones.obtener(c.id) == c


def test_obtener_conversacion_inexistente_devuelve_none(repos):
    _, conversaciones, _ = repos
    assert conversaciones.obtener(uuid4()) is None


def test_conversacion_de_usuario_inexistente_falla(repos):
    _, conversaciones, _ = repos
    with pytest.raises(sqlite3.IntegrityError):
        conversaciones.guardar(Conversacion(Usuario(nombre="A").id, "X"))


def test_guardar_conversacion_de_nuevo_actualiza_sin_duplicar(repos):
    usuarios, conversaciones, _ = repos
    u, c = crear_conversacion(usuarios, conversaciones)
    c.titulo = "Nuevo título"
    conversaciones.guardar(c)
    assert conversaciones.obtener(c.id).titulo == "Nuevo título"
    assert len(conversaciones.listar_por_usuario(u.id)) == 1


def test_listar_conversaciones_recientes_primero_y_filtra(repos):
    usuarios, conversaciones, _ = repos
    a, b = Usuario(nombre="A"), Usuario(nombre="B")
    usuarios.guardar(a)
    usuarios.guardar(b)
    vieja = Conversacion(a.id, "Vieja", fecha_creacion=hora(8))
    nueva = Conversacion(a.id, "Nueva", fecha_creacion=hora(18))
    cerrada = Conversacion(a.id, "Cerrada", fecha_creacion=hora(12), activa=False)
    ajena = Conversacion(b.id, "Ajena", fecha_creacion=hora(20))
    for c in (vieja, ajena, cerrada, nueva):
        conversaciones.guardar(c)
    todas = [c.titulo for c in conversaciones.listar_por_usuario(a.id)]
    activas = [c.titulo for c in conversaciones.listar_por_usuario(a.id, solo_activas=True)]
    assert todas == ["Nueva", "Cerrada", "Vieja"]
    assert activas == ["Nueva", "Vieja"]


def test_eliminar_conversacion_indica_si_existia(repos):
    usuarios, conversaciones, _ = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    assert conversaciones.eliminar(c.id) is True
    assert conversaciones.eliminar(c.id) is False


def test_eliminar_usuario_con_mensajes_no_borra_el_historial(repos):
    usuarios, conversaciones, mensajes = repos
    u, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.USUARIO, "Hola")
    mensajes.guardar(m)

    with pytest.raises(sqlite3.IntegrityError, match="mensajes son inmutables"):
        usuarios.eliminar(u.id)

    assert usuarios.obtener(u.id) is not None
    assert conversaciones.obtener(c.id) is not None
    assert mensajes.obtener(m.id) == m


def test_mensaje_guardar_y_obtener_devuelve_el_mismo(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.ASISTENTE, "Qué tal, ¿añadimos un evento?",
                metadatos={"modelo": "x", "tokens": 12, "nota": "ñandú"})
    mensajes.guardar(m)
    assert mensajes.obtener(m.id) == m


def test_mensaje_con_contenido_vacio_se_conserva(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.HERRAMIENTA, "", metadatos={"herramienta": "agenda"})
    mensajes.guardar(m)
    assert mensajes.obtener(m.id) == m


def test_mensaje_de_conversacion_inexistente_falla(repos):
    _, _, mensajes = repos
    with pytest.raises(sqlite3.IntegrityError):
        mensajes.guardar(Mensaje(uuid4(), RolMensaje.USUARIO, "Hola"))


def test_guardar_mensaje_existente_no_permite_editarlo(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.ASISTENTE, "Borrador")
    mensajes.guardar(m)
    m.contenido = "Versión final"
    with pytest.raises(sqlite3.IntegrityError, match="mensajes son inmutables"):
        mensajes.guardar(m)
    assert mensajes.obtener(m.id).contenido == "Borrador"
    assert len(mensajes.listar_por_conversacion(c.id)) == 1


def test_listar_mensajes_ordena_y_filtra_por_conversacion(repos):
    usuarios, conversaciones, mensajes = repos
    u, c1 = crear_conversacion(usuarios, conversaciones, "Una")
    c2 = Conversacion(u.id, "Otra")
    conversaciones.guardar(c2)
    tarde = Mensaje(c1.id, RolMensaje.ASISTENTE, "Tarde", fecha_creacion=hora(10))
    pronto = Mensaje(c1.id, RolMensaje.USUARIO, "Pronto", fecha_creacion=hora(9))
    ajeno = Mensaje(c2.id, RolMensaje.USUARIO, "Ajeno", fecha_creacion=hora(8))
    for m in (tarde, ajeno, pronto):
        mensajes.guardar(m)
    assert [m.contenido for m in mensajes.listar_por_conversacion(c1.id)] == ["Pronto", "Tarde"]


def test_listar_ultimos_devuelve_los_ultimos_en_orden_cronologico(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    for minuto in range(5):
        mensajes.guardar(
            Mensaje(c.id, RolMensaje.USUARIO, f"M{minuto}", fecha_creacion=hora(9, minuto))
        )
    ultimos = mensajes.listar_ultimos(c.id, 3)
    assert [m.contenido for m in ultimos] == ["M2", "M3", "M4"]
    assert len(mensajes.listar_ultimos(c.id, 50)) == 5


def test_listar_ultimos_desempata_fechas_iguales_por_insercion(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    instante = hora(9)
    for contenido in ("Propuesta", "Respuesta"):
        mensajes.guardar(
            Mensaje(
                c.id,
                RolMensaje.ASISTENTE,
                contenido,
                fecha_creacion=instante,
            )
        )

    assert [
        mensaje.contenido for mensaje in mensajes.listar_ultimos(c.id, 2)
    ] == ["Propuesta", "Respuesta"]


@pytest.mark.parametrize("limite", [0, -1])
def test_listar_ultimos_rechaza_limite_no_valido(repos, limite):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    with pytest.raises(ValueError):
        mensajes.listar_ultimos(c.id, limite)


def test_los_mensajes_leidos_sirven_para_el_historial_del_modelo(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    mensajes.guardar(Mensaje(c.id, RolMensaje.USUARIO, "Hola", fecha_creacion=hora(9)))
    mensajes.guardar(Mensaje(c.id, RolMensaje.HERRAMIENTA, "  ", fecha_creacion=hora(10)))
    mensajes.guardar(Mensaje(c.id, RolMensaje.ASISTENTE, "Buenas", fecha_creacion=hora(11)))
    historial = historial_para_modelo(mensajes.listar_por_conversacion(c.id))
    assert historial == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Buenas"},
    ]


def test_eliminar_mensaje_no_puede_borrar_el_historial(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.USUARIO, "Hola")
    mensajes.guardar(m)
    with pytest.raises(sqlite3.IntegrityError, match="mensajes son inmutables"):
        mensajes.eliminar(m.id)
    assert mensajes.obtener(m.id) == m


def test_eliminar_conversacion_con_mensajes_no_borra_el_historial(repos):
    usuarios, conversaciones, mensajes = repos
    _, c = crear_conversacion(usuarios, conversaciones)
    m = Mensaje(c.id, RolMensaje.USUARIO, "Hola")
    mensajes.guardar(m)
    with pytest.raises(sqlite3.IntegrityError, match="mensajes son inmutables"):
        conversaciones.eliminar(c.id)
    assert conversaciones.obtener(c.id) is not None
    assert mensajes.obtener(m.id) == m


def test_las_interfaces_no_se_pueden_instanciar():
    with pytest.raises(TypeError):
        RepositorioConversaciones()
    with pytest.raises(TypeError):
        RepositorioMensajes()

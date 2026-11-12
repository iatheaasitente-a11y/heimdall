from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.message import RolMensaje
from app.domain.user import Usuario
from app.repositories.sqlite_conversaciones import (
    RepositorioConversacionesSQLite,
    RepositorioMensajesSQLite,
)
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.conversaciones import ServicioConversaciones
from app.services.errores import (
    ConversacionCerrada,
    ConversacionNoEncontrada,
    UsuarioNoEncontrado,
)

AHORA = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


@pytest.fixture
def entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    try:
        usuarios = RepositorioUsuariosSQLite(conexion)
        conversaciones = RepositorioConversacionesSQLite(conexion)
        mensajes = RepositorioMensajesSQLite(conexion)
        usuario = Usuario(nombre="A")
        usuarios.guardar(usuario)
        segundos = 0

        def reloj():
            nonlocal segundos
            actual = AHORA + timedelta(seconds=segundos)
            segundos += 1
            return actual

        servicio = ServicioConversaciones(
            usuarios, conversaciones, mensajes, reloj=reloj
        )
        yield servicio, usuarios, conversaciones, mensajes, usuario
    finally:
        conexion.close()


@pytest.fixture
def otro_usuario(entorno):
    _, usuarios, _, _, _ = entorno
    usuario = Usuario(nombre="B")
    usuarios.guardar(usuario)
    return usuario


def test_iniciar_conversacion_guarda_y_recorta_titulo(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "  Semana  ")
    assert conversacion.titulo == "Semana"
    assert conversacion.fecha_creacion == AHORA
    assert repositorio.obtener(conversacion.id) == conversacion


def test_iniciar_conversacion_rechaza_titulo_vacio(entorno):
    servicio, _, repositorio, _, usuario = entorno
    with pytest.raises(ValidationError):
        servicio.iniciar_conversacion(usuario.id, "  ")
    assert repositorio.listar_por_usuario(usuario.id) == []


def test_iniciar_conversacion_rechaza_usuario_inexistente(entorno):
    servicio, _, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.iniciar_conversacion(uuid4(), "Título")


def test_listar_conversaciones_de_usuario_inexistente_falla(entorno):
    servicio, _, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.listar_conversaciones(uuid4())


def test_listar_conversaciones_ordena_de_mas_reciente_a_mas_antigua(entorno):
    servicio, _, _, _, usuario = entorno
    anterior = servicio.iniciar_conversacion(usuario.id, "Anterior")
    posterior = servicio.iniciar_conversacion(usuario.id, "Posterior")
    assert servicio.listar_conversaciones(usuario.id) == [posterior, anterior]


def test_listar_conversaciones_filtra_activas_si_se_solicita(entorno):
    servicio, _, _, _, usuario = entorno
    activa = servicio.iniciar_conversacion(usuario.id, "Activa")
    cerrada = servicio.iniciar_conversacion(usuario.id, "Cerrada")
    servicio.cerrar_conversacion(usuario.id, cerrada.id)
    todas = servicio.listar_conversaciones(usuario.id)
    solo_activas = servicio.listar_conversaciones(usuario.id, solo_activas=True)
    assert [conversacion.id for conversacion in todas] == [cerrada.id, activa.id]
    assert [conversacion.id for conversacion in solo_activas] == [activa.id]


def test_obtener_conversacion_inexistente_falla(entorno):
    servicio, _, _, _, usuario = entorno
    with pytest.raises(ConversacionNoEncontrada):
        servicio.obtener_conversacion(usuario.id, uuid4())


def test_renombrar_conversacion_recorta_y_guarda_el_titulo(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Antes")
    actualizada = servicio.renombrar_conversacion(
        usuario.id, conversacion.id, "  Después  "
    )
    assert actualizada.titulo == "Después"
    assert repositorio.obtener(conversacion.id).titulo == "Después"


def test_renombrar_conversacion_rechaza_titulo_vacio_sin_cambiarlo(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Conservar")
    with pytest.raises(ValidationError):
        servicio.renombrar_conversacion(usuario.id, conversacion.id, " ")
    assert repositorio.obtener(conversacion.id).titulo == "Conservar"


def test_cerrar_conversacion_conserva_y_persiste_el_cierre(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Cerrar")
    cerrada = servicio.cerrar_conversacion(usuario.id, conversacion.id)
    assert cerrada.activa is False
    assert repositorio.obtener(conversacion.id).activa is False


def test_cerrar_conversacion_dos_veces_devuelve_la_misma(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Cerrar")
    primera = servicio.cerrar_conversacion(usuario.id, conversacion.id)
    segunda = servicio.cerrar_conversacion(usuario.id, conversacion.id)
    assert segunda == primera
    assert repositorio.obtener(conversacion.id).activa is False


def test_no_se_puede_renombrar_una_conversacion_cerrada(entorno):
    servicio, _, repositorio, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Cerrada")
    servicio.cerrar_conversacion(usuario.id, conversacion.id)
    with pytest.raises(ConversacionCerrada, match="La conversación «Cerrada» está cerrada."):
        servicio.renombrar_conversacion(usuario.id, conversacion.id, "Nuevo título")
    assert repositorio.obtener(conversacion.id).titulo == "Cerrada"


def test_no_se_puede_agregar_mensaje_a_conversacion_cerrada(entorno):
    servicio, _, _, mensajes, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Cerrada")
    servicio.cerrar_conversacion(usuario.id, conversacion.id)
    with pytest.raises(ConversacionCerrada):
        servicio.agregar_mensaje(
            usuario.id, conversacion.id, RolMensaje.USUARIO, "Hola"
        )
    assert mensajes.listar_por_conversacion(conversacion.id) == []


@pytest.mark.parametrize("rol", [RolMensaje.ASISTENTE, RolMensaje.HERRAMIENTA])
@pytest.mark.parametrize("contenido", ["", "  "])
def test_asistente_y_herramienta_pueden_tener_contenido_vacio(
    entorno, rol, contenido
):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Herramientas")
    mensaje = servicio.agregar_mensaje(
        usuario.id, conversacion.id, rol, contenido
    )
    assert mensaje.contenido == contenido


@pytest.mark.parametrize("rol", [RolMensaje.USUARIO, RolMensaje.SISTEMA])
@pytest.mark.parametrize("contenido", ["", "  "])
def test_usuario_y_sistema_no_pueden_tener_contenido_vacio(
    entorno, rol, contenido
):
    servicio, _, _, mensajes, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Mensajes")
    with pytest.raises(ValueError):
        servicio.agregar_mensaje(usuario.id, conversacion.id, rol, contenido)
    assert mensajes.listar_por_conversacion(conversacion.id) == []


def test_agregar_mensaje_acepta_rol_como_texto(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Mensajes")
    mensaje = servicio.agregar_mensaje(
        usuario.id, conversacion.id, "usuario", "Hola"
    )
    assert mensaje.rol == RolMensaje.USUARIO


def test_agregar_mensaje_rechaza_rol_desconocido(entorno):
    servicio, _, _, mensajes, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Mensajes")
    with pytest.raises(ValueError):
        servicio.agregar_mensaje(
            usuario.id, conversacion.id, "robot", "Hola"
        )
    assert mensajes.listar_por_conversacion(conversacion.id) == []


def test_agregar_mensaje_copia_metadatos_incluidos_los_anidados(entorno):
    servicio, _, _, mensajes, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Mensajes")
    metadatos = {"herramienta": {"nombre": "agenda"}}
    mensaje = servicio.agregar_mensaje(
        usuario.id, conversacion.id, "asistente", "Llamada", metadatos
    )
    metadatos["herramienta"]["nombre"] = "otra"
    guardado = mensajes.obtener(mensaje.id)
    assert guardado.metadatos == {"herramienta": {"nombre": "agenda"}}


def test_listar_mensajes_devuelve_orden_cronologico(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Mensajes")
    primero = servicio.agregar_mensaje(
        usuario.id, conversacion.id, "usuario", "Primero"
    )
    segundo = servicio.agregar_mensaje(
        usuario.id, conversacion.id, "asistente", "Segundo"
    )
    assert servicio.listar_mensajes(usuario.id, conversacion.id) == [
        primero,
        segundo,
    ]


def test_historial_para_modelo_traduce_roles_y_omite_mensajes_vacios(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Historial")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "usuario", "Hola")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "asistente", " ")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "asistente", "Buenas")
    assert servicio.historial_para_modelo(usuario.id, conversacion.id) == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Buenas"},
    ]


def test_historial_para_modelo_solicita_limite_al_repositorio(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Historial")
    for texto in ("Primero", "Segundo", "Tercero"):
        servicio.agregar_mensaje(usuario.id, conversacion.id, "usuario", texto)
    assert servicio.historial_para_modelo(
        usuario.id, conversacion.id, limite=2
    ) == [
        {"role": "user", "content": "Segundo"},
        {"role": "user", "content": "Tercero"},
    ]


def test_historial_puede_devolver_menos_que_limite_por_mensajes_vacios(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Historial")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "usuario", "Hola")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "asistente", "")
    assert servicio.historial_para_modelo(
        usuario.id, conversacion.id, limite=2
    ) == [{"role": "user", "content": "Hola"}]


@pytest.mark.parametrize("limite", [0, -1])
def test_historial_rechaza_limite_no_positivo(entorno, limite):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Historial")
    with pytest.raises(ValueError):
        servicio.historial_para_modelo(usuario.id, conversacion.id, limite)


def test_historial_conversacion_inexistente_falla(entorno):
    servicio, _, _, _, usuario = entorno
    with pytest.raises(ConversacionNoEncontrada):
        servicio.historial_para_modelo(usuario.id, uuid4())


def test_historial_sigue_disponible_al_cerrar_la_conversacion(entorno):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Historial")
    servicio.agregar_mensaje(usuario.id, conversacion.id, "usuario", "Conservar")
    servicio.cerrar_conversacion(usuario.id, conversacion.id)
    assert servicio.historial_para_modelo(usuario.id, conversacion.id) == [
        {"role": "user", "content": "Conservar"}
    ]


def test_usuario_no_puede_obtener_conversacion_ajena(entorno, otro_usuario):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Privada")
    with pytest.raises(ConversacionNoEncontrada):
        servicio.obtener_conversacion(otro_usuario.id, conversacion.id)


@pytest.mark.parametrize(
    "accion",
    ["renombrar", "cerrar", "agregar", "listar_mensajes", "historial"],
)
def test_operaciones_no_revelan_conversaciones_ajenas(
    entorno, otro_usuario, accion
):
    servicio, _, _, _, usuario = entorno
    conversacion = servicio.iniciar_conversacion(usuario.id, "Privada")
    with pytest.raises(ConversacionNoEncontrada):
        if accion == "renombrar":
            servicio.renombrar_conversacion(
                otro_usuario.id, conversacion.id, "Nuevo"
            )
        elif accion == "cerrar":
            servicio.cerrar_conversacion(otro_usuario.id, conversacion.id)
        elif accion == "agregar":
            servicio.agregar_mensaje(
                otro_usuario.id, conversacion.id, "usuario", "Hola"
            )
        elif accion == "listar_mensajes":
            servicio.listar_mensajes(otro_usuario.id, conversacion.id)
        else:
            servicio.historial_para_modelo(otro_usuario.id, conversacion.id)


def test_el_servicio_no_expone_operaciones_para_borrar_o_editar(entorno):
    servicio, _, _, _, _ = entorno
    assert not hasattr(servicio, "eliminar_conversacion")
    assert not hasattr(servicio, "eliminar_mensaje")
    assert not hasattr(servicio, "editar_mensaje")

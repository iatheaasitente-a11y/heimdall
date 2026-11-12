from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.errores import UsuarioNoEncontrado
from app.services.usuarios import ServicioUsuarios


@pytest.fixture
def entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    repo = RepositorioUsuariosSQLite(conexion)
    try:
        yield ServicioUsuarios(repo), repo
    finally:
        conexion.close()


def test_registrar_guarda_y_devuelve_el_usuario(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("Álvaro")
    assert repo.obtener(usuario.id) == usuario
    assert (usuario.idioma, usuario.zona_horaria) == ("es-ES", "Europe/Madrid")


def test_registrar_recorta_los_espacios_del_nombre(entorno):
    servicio, _ = entorno
    assert servicio.registrar("  Álvaro  ").nombre == "Álvaro"


def test_registrar_rechaza_nombre_vacio_y_no_guarda(entorno):
    servicio, repo = entorno
    with pytest.raises(ValidationError):
        servicio.registrar("   ")
    assert repo.listar() == []


def test_registrar_rechaza_zona_horaria_desconocida(entorno):
    servicio, repo = entorno
    with pytest.raises(ValidationError):
        servicio.registrar("A", zona_horaria="Marte/Olimpo")
    assert repo.listar() == []


def test_obtener_usuario_inexistente_lanza_error(entorno):
    servicio, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.obtener(uuid4())


def test_cambiar_zona_horaria_se_guarda(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("A")
    servicio.cambiar_zona_horaria(usuario.id, "America/Mexico_City")
    assert repo.obtener(usuario.id).zona_horaria == "America/Mexico_City"


def test_cambiar_preferencia_se_guarda(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("A")

    servicio.cambiar_preferencia(usuario.id, "telegram_zona_confirmada", True)

    assert repo.obtener(usuario.id).preferencias["telegram_zona_confirmada"] is True


def test_cambiar_preferencia_rechaza_clave_vacia(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("A")

    with pytest.raises(ValueError, match="clave"):
        servicio.cambiar_preferencia(usuario.id, " ", True)

    assert repo.obtener(usuario.id).preferencias == {}


def test_cambiar_a_zona_invalida_no_modifica_lo_guardado(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("A")
    with pytest.raises(ValidationError):
        servicio.cambiar_zona_horaria(usuario.id, "Marte/Olimpo")
    assert repo.obtener(usuario.id).zona_horaria == "Europe/Madrid"


def test_desactivar_se_guarda(entorno):
    servicio, repo = entorno
    usuario = servicio.registrar("A")
    servicio.desactivar(usuario.id)
    assert repo.obtener(usuario.id).activo is False


def test_desactivar_usuario_inexistente_lanza_error(entorno):
    servicio, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.desactivar(uuid4())

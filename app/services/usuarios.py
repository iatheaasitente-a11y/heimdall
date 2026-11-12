"""Casos de uso relacionados con los usuarios."""

from uuid import UUID

from app.domain.user import Usuario
from app.repositories.interfaces import RepositorioUsuarios
from app.schemas.user import UsuarioSchema, usuario_a_dict
from app.services.errores import exigir_usuario


class ServicioUsuarios:
    """Registro y mantenimiento de usuarios.

    No hace ``commit``: de eso se encarga quien abre la conexión del repositorio.
    """

    def __init__(self, usuarios: RepositorioUsuarios) -> None:
        """Crea el servicio sobre un repositorio de usuarios."""
        self._usuarios = usuarios

    def registrar(
        self,
        nombre: str,
        idioma: str = "es-ES",
        zona_horaria: str = "Europe/Madrid",
    ) -> Usuario:
        """Crea y guarda un usuario nuevo.

        Raises:
            pydantic.ValidationError: Si el nombre está vacío o la zona horaria
                no existe.
        """
        usuario = Usuario(nombre=nombre.strip(), idioma=idioma, zona_horaria=zona_horaria)
        UsuarioSchema.model_validate(usuario)
        self._usuarios.guardar(usuario)
        return usuario

    def obtener(self, usuario_id: UUID) -> Usuario:
        """Devuelve el usuario indicado.

        Raises:
            UsuarioNoEncontrado: Si no existe.
        """
        return exigir_usuario(self._usuarios.obtener, usuario_id)

    def cambiar_zona_horaria(self, usuario_id: UUID, zona_horaria: str) -> Usuario:
        """Cambia la zona horaria del usuario y guarda el cambio.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            pydantic.ValidationError: Si la zona horaria no existe. En ese caso no
                se modifica nada.
        """
        usuario = self.obtener(usuario_id)
        UsuarioSchema.model_validate({**usuario_a_dict(usuario), "zona_horaria": zona_horaria})
        usuario.zona_horaria = zona_horaria
        self._usuarios.guardar(usuario)
        return usuario

    def cambiar_preferencia(self, usuario_id: UUID, clave: str, valor: object) -> Usuario:
        """Guarda una preferencia del usuario.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            ValueError: Si la clave está vacía.
        """
        if not isinstance(clave, str) or not clave.strip():
            raise ValueError("La clave de preferencia no puede estar vacía.")
        usuario = self.obtener(usuario_id)
        usuario.cambiar_preferencia(clave.strip(), valor)
        UsuarioSchema.model_validate(usuario)
        self._usuarios.guardar(usuario)
        return usuario

    def desactivar(self, usuario_id: UUID) -> Usuario:
        """Marca al usuario como inactivo y guarda el cambio.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        usuario = self.obtener(usuario_id)
        usuario.desactivar()
        self._usuarios.guardar(usuario)
        return usuario

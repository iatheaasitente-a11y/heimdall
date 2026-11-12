"""Casos de uso de las conversaciones y sus mensajes."""

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.message import Conversacion, Mensaje, RolMensaje
from app.domain.relations import historial_para_modelo as preparar_historial
from app.repositories.interfaces import (
    RepositorioConversaciones,
    RepositorioMensajes,
    RepositorioUsuarios,
)
from app.schemas.message import ConversacionSchema, MensajeSchema
from app.services.errores import (
    ConversacionCerrada,
    ConversacionNoEncontrada,
    exigir_usuario,
    obtener_entidad_de_usuario,
)


class ServicioConversaciones:
    """Gestiona conversaciones y añade mensajes que se conservan sin editar.

    Recibe un reloj para fijar las fechas en las pruebas. No hace ``commit``:
    de eso se encarga quien abre la conexión del repositorio.
    """

    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        conversaciones: RepositorioConversaciones,
        mensajes: RepositorioMensajes,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        """Crea el servicio; si no se indica reloj, usa la hora actual en UTC."""
        self._usuarios = usuarios
        self._conversaciones = conversaciones
        self._mensajes = mensajes
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def iniciar_conversacion(self, usuario_id: UUID, titulo: str) -> Conversacion:
        """Crea y guarda una conversación nueva para el usuario.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            pydantic.ValidationError: Si el título queda vacío o la fecha no
                lleva zona horaria.
        """
        exigir_usuario(self._usuarios.obtener, usuario_id)
        conversacion = Conversacion(
            usuario_id=usuario_id,
            titulo=titulo.strip(),
            fecha_creacion=self._reloj(),
        )
        ConversacionSchema.model_validate(conversacion)
        self._conversaciones.guardar(conversacion)
        return conversacion

    def obtener_conversacion(
        self, usuario_id: UUID, conversacion_id: UUID
    ) -> Conversacion:
        """Devuelve una conversación del usuario indicado.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
        """
        return self._obtener(usuario_id, conversacion_id)

    def listar_conversaciones(
        self, usuario_id: UUID, solo_activas: bool = False
    ) -> list[Conversacion]:
        """Devuelve las conversaciones del usuario, de más reciente a más antigua.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        exigir_usuario(self._usuarios.obtener, usuario_id)
        return self._conversaciones.listar_por_usuario(
            usuario_id, solo_activas=solo_activas
        )

    def renombrar_conversacion(
        self, usuario_id: UUID, conversacion_id: UUID, titulo: str
    ) -> Conversacion:
        """Cambia el título de una conversación activa y guarda el cambio.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
            ConversacionCerrada: Si la conversación está cerrada.
            pydantic.ValidationError: Si el título queda vacío.
        """
        conversacion = self._obtener(usuario_id, conversacion_id)
        self._exigir_activa(conversacion)
        actualizada = Conversacion(
            usuario_id=conversacion.usuario_id,
            titulo=titulo.strip(),
            id=conversacion.id,
            fecha_creacion=conversacion.fecha_creacion,
            activa=conversacion.activa,
        )
        ConversacionSchema.model_validate(actualizada)
        self._conversaciones.guardar(actualizada)
        return actualizada

    def cerrar_conversacion(
        self, usuario_id: UUID, conversacion_id: UUID
    ) -> Conversacion:
        """Cierra y conserva la conversación; cerrarla de nuevo es inocuo.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
        """
        conversacion = self._obtener(usuario_id, conversacion_id)
        if conversacion.activa:
            conversacion.activa = False
            self._conversaciones.guardar(conversacion)
        return conversacion

    def agregar_mensaje(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        rol: RolMensaje | str,
        contenido: str,
        metadatos: dict[str, Any] | None = None,
    ) -> Mensaje:
        """Añade un mensaje a una conversación activa y guarda una copia.

        El contenido vacío solo se admite para mensajes de asistente o
        herramienta.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
            ConversacionCerrada: Si la conversación no está activa.
            ValueError: Si ``rol`` no existe o el contenido está vacío para un
                rol que lo requiere.
            pydantic.ValidationError: Si la fecha del reloj no lleva zona.
        """
        conversacion = self._obtener(usuario_id, conversacion_id)
        self._exigir_activa(conversacion)
        rol_validado = RolMensaje(rol)
        if (
            not contenido.strip()
            and rol_validado not in {RolMensaje.ASISTENTE, RolMensaje.HERRAMIENTA}
        ):
            raise ValueError("El contenido vacío solo se permite al asistente o a herramientas.")
        mensaje = Mensaje(
            conversacion_id=conversacion.id,
            rol=rol_validado,
            contenido=contenido,
            fecha_creacion=self._reloj(),
            metadatos=deepcopy(metadatos) if metadatos is not None else {},
        )
        MensajeSchema.model_validate(mensaje)
        self._mensajes.guardar(mensaje)
        return mensaje

    def listar_mensajes(
        self, usuario_id: UUID, conversacion_id: UUID
    ) -> list[Mensaje]:
        """Devuelve los mensajes de la conversación, en orden cronológico.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
        """
        conversacion = self._obtener(usuario_id, conversacion_id)
        return self._mensajes.listar_por_conversacion(conversacion.id)

    def historial_para_modelo(
        self, usuario_id: UUID, conversacion_id: UUID, limite: int = 20
    ) -> list[dict[str, str]]:
        """Prepara los mensajes recientes para el modelo, omitiendo los vacíos.

        Raises:
            ConversacionNoEncontrada: Si no existe o pertenece a otro usuario.
            ValueError: Si ``limite`` no es mayor que cero.
        """
        if limite <= 0:
            raise ValueError("El límite debe ser mayor que cero.")
        conversacion = self._obtener(usuario_id, conversacion_id)
        ultimos = self._mensajes.listar_ultimos(conversacion.id, limite)
        return preparar_historial(ultimos, limite)

    def _obtener(self, usuario_id: UUID, conversacion_id: UUID) -> Conversacion:
        return obtener_entidad_de_usuario(
            self._conversaciones.obtener,
            usuario_id,
            conversacion_id,
            ConversacionNoEncontrada,
        )

    @staticmethod
    def _exigir_activa(conversacion: Conversacion) -> None:
        """Lanza ``ConversacionCerrada`` si la conversación no está activa."""
        if not conversacion.activa:
            raise ConversacionCerrada(conversacion.titulo)

"""Casos de uso de los objetivos: crearlos, consultarlos y gestionar su progreso."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID

from app.domain.goal import EstadoObjetivo, Objetivo
from app.domain.user import Usuario
from app.repositories.interfaces import RepositorioObjetivos, RepositorioUsuarios
from app.schemas.goal import ObjetivoSchema
from app.services.resolucion import resolver_por_nombre
from app.services.errores import (
    FechaLimiteEnElPasado,
    ObjetivoNoActivo,
    ObjetivoNoEncontrado,
    exigir_usuario,
    obtener_entidad_de_usuario,
    transicion_de_estado,
)


class ServicioObjetivos:
    """Gestión de los objetivos de un usuario.

    Recibe un reloj para poder fijar la fecha actual en las pruebas. No hace
    ``commit``: de eso se encarga quien abre la conexión.

    Las operaciones sobre un objetivo reciben el ``usuario_id`` de quien las
    pide; si el objetivo es de otra persona, responden como si no existiera.
    """

    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        objetivos: RepositorioObjetivos,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        """Crea el servicio; si no se indica reloj, usa la hora actual en UTC."""
        self._usuarios = usuarios
        self._objetivos = objetivos
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def crear_objetivo(
        self,
        usuario_id: UUID,
        nombre: str,
        descripcion: str | None = None,
        fecha_limite: date | None = None,
    ) -> Objetivo:
        """Crea y guarda un objetivo si su fecha límite no ha pasado.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            FechaLimiteEnElPasado: Si la fecha límite es anterior al día actual
                en la zona horaria del usuario.
            pydantic.ValidationError: Si el nombre está vacío.
        """
        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        if fecha_limite is not None and fecha_limite < self._hoy(usuario):
            raise FechaLimiteEnElPasado(fecha_limite)
        objetivo = Objetivo(
            usuario_id=usuario_id,
            nombre=nombre.strip(),
            descripcion=(descripcion.strip() or None) if descripcion is not None else None,
            fecha_limite=fecha_limite,
        )
        ObjetivoSchema.model_validate(objetivo)
        self._objetivos.guardar(objetivo)
        return objetivo

    def obtener_objetivo(self, usuario_id: UUID, objetivo_id: UUID) -> Objetivo:
        """Devuelve un objetivo del usuario indicado.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
        """
        return self._obtener(usuario_id, objetivo_id)

    def listar_objetivos(
        self,
        usuario_id: UUID,
        estado: EstadoObjetivo | str | None = None,
    ) -> list[Objetivo]:
        """Devuelve los objetivos del usuario, ordenados por fecha límite.

        ``estado`` puede ser un miembro de ``EstadoObjetivo`` o su valor textual.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            ValueError: Si ``estado`` no representa un estado conocido.
        """
        exigir_usuario(self._usuarios.obtener, usuario_id)
        estado_validado = EstadoObjetivo(estado) if estado is not None else None
        return self._objetivos.listar_por_usuario(usuario_id, estado=estado_validado)

    def resolver_objetivo_id(self, usuario_id: UUID, nombre: str) -> UUID:
        """Resuelve el nombre exacto de un objetivo propio a su identificador."""
        return resolver_por_nombre(
            nombre,
            self.listar_objetivos(usuario_id),
            lambda objetivo: objetivo.nombre,
            "objetivos",
        )

    def actualizar_progreso(
        self, usuario_id: UUID, objetivo_id: UUID, progreso: float
    ) -> Objetivo:
        """Actualiza el progreso de un objetivo activo y guarda el cambio.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
            ObjetivoNoActivo: Si el objetivo no está activo.
            ValueError: Si el progreso queda fuera del rango 0-100.
        """
        objetivo = self._obtener(usuario_id, objetivo_id)
        if objetivo.estado != EstadoObjetivo.ACTIVO:
            raise ObjetivoNoActivo(objetivo.nombre)
        objetivo.actualizar_progreso(progreso)
        self._objetivos.guardar(objetivo)
        return objetivo

    def pausar_objetivo(self, usuario_id: UUID, objetivo_id: UUID) -> Objetivo:
        """Pausa un objetivo activo y guarda el cambio.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
            CambioDeEstadoNoPermitido: Si el objetivo no está activo.
        """
        objetivo = self._obtener(usuario_id, objetivo_id)
        with transicion_de_estado():
            objetivo.pausar()
        self._objetivos.guardar(objetivo)
        return objetivo

    def reanudar_objetivo(self, usuario_id: UUID, objetivo_id: UUID) -> Objetivo:
        """Reanuda un objetivo pausado y guarda el cambio.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
            CambioDeEstadoNoPermitido: Si el objetivo no está pausado.
        """
        objetivo = self._obtener(usuario_id, objetivo_id)
        with transicion_de_estado():
            objetivo.reanudar()
        self._objetivos.guardar(objetivo)
        return objetivo

    def cancelar_objetivo(self, usuario_id: UUID, objetivo_id: UUID) -> Objetivo:
        """Cancela un objetivo activo o pausado y guarda el cambio.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
            CambioDeEstadoNoPermitido: Si el objetivo ya está cerrado.
        """
        objetivo = self._obtener(usuario_id, objetivo_id)
        with transicion_de_estado():
            objetivo.cancelar()
        self._objetivos.guardar(objetivo)
        return objetivo

    def dias_restantes(
        self,
        usuario_id: UUID,
        objetivo_id: UUID,
        hoy: date | None = None,
    ) -> int | None:
        """Devuelve los días hasta la fecha límite usando la zona del usuario.

        Raises:
            ObjetivoNoEncontrado: Si no existe o pertenece a otro usuario.
            UsuarioNoEncontrado: Si no existe y se debe calcular el día actual.
        """
        objetivo = self._obtener(usuario_id, objetivo_id)
        if hoy is None:
            hoy = self._hoy(exigir_usuario(self._usuarios.obtener, usuario_id))
        return objetivo.dias_restantes(hoy)

    def vencidos(self, usuario_id: UUID, hoy: date | None = None) -> list[Objetivo]:
        """Devuelve los objetivos activos cuya fecha límite ya pasó.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        dia = hoy if hoy is not None else self._hoy(usuario)
        activos = self._objetivos.listar_por_usuario(
            usuario_id, estado=EstadoObjetivo.ACTIVO
        )
        return [objetivo for objetivo in activos if objetivo.esta_vencido(dia)]

    def _obtener(self, usuario_id: UUID, objetivo_id: UUID) -> Objetivo:
        return obtener_entidad_de_usuario(
            self._objetivos.obtener, usuario_id, objetivo_id, ObjetivoNoEncontrado
        )

    def _hoy(self, usuario: Usuario) -> date:
        """Devuelve la fecha actual en la zona horaria del usuario."""
        return self._reloj().astimezone(usuario.zona()).date()

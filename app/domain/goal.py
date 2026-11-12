"""Modelo de dominio de los objetivos a medio y largo plazo."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.errores import TransicionNoPermitida


class EstadoObjetivo(StrEnum):
    """Situación de un objetivo."""

    ACTIVO = "activo"
    COMPLETADO = "completado"
    PAUSADO = "pausado"
    CANCELADO = "cancelado"


@dataclass
class Objetivo:
    """Meta personal con una fecha límite opcional y un progreso medido en porcentaje.

    Attributes:
        usuario_id: Identificador del usuario propietario.
        nombre: Nombre de la meta, por ejemplo "Aprender Python".
        id: Identificador único (UUID), generado automáticamente.
        descripcion: Detalles opcionales.
        fecha_limite: Fecha objetivo opcional, sin hora.
        progreso: Avance de 0 a 100.
        estado: Situación actual; por defecto ``ACTIVO``.
    """

    usuario_id: UUID
    nombre: str
    id: UUID = field(default_factory=uuid4)
    descripcion: str | None = None
    fecha_limite: date | None = None
    progreso: float = 0.0
    estado: EstadoObjetivo = EstadoObjetivo.ACTIVO

    def actualizar_progreso(self, progreso: float) -> None:
        """Fija el progreso y completa el objetivo si llega a 100.

        Args:
            progreso: Nuevo avance, entre 0 y 100 ambos incluidos.

        Raises:
            ValueError: Si el valor queda fuera del rango 0-100.
        """
        if not 0 <= progreso <= 100:
            raise ValueError("El progreso debe estar entre 0 y 100.")
        self.progreso = progreso
        if progreso == 100:
            self.estado = EstadoObjetivo.COMPLETADO

    def pausar(self) -> None:
        """Pasa el objetivo de ``ACTIVO`` a ``PAUSADO``.

        Raises:
            TransicionNoPermitida: Si el objetivo no está activo.
        """
        self._cambiar_desde({EstadoObjetivo.ACTIVO}, EstadoObjetivo.PAUSADO)

    def reanudar(self) -> None:
        """Pasa el objetivo de ``PAUSADO`` a ``ACTIVO``.

        Raises:
            TransicionNoPermitida: Si el objetivo no está pausado.
        """
        self._cambiar_desde({EstadoObjetivo.PAUSADO}, EstadoObjetivo.ACTIVO)

    def cancelar(self) -> None:
        """Pasa el objetivo activo o pausado a ``CANCELADO``.

        Raises:
            TransicionNoPermitida: Si el objetivo está completado o cancelado.
        """
        self._cambiar_desde(
            {EstadoObjetivo.ACTIVO, EstadoObjetivo.PAUSADO},
            EstadoObjetivo.CANCELADO,
        )

    def restablecer(self) -> None:
        """Devuelve el objetivo a ``ACTIVO`` sin modificar su progreso."""
        self.estado = EstadoObjetivo.ACTIVO

    def _cambiar_desde(
        self, origenes: set[EstadoObjetivo], destino: EstadoObjetivo
    ) -> None:
        """Cambia el estado únicamente si está dentro de los estados permitidos.

        Raises:
            TransicionNoPermitida: Si el estado actual no se permite como origen.
        """
        if self.estado not in origenes:
            raise TransicionNoPermitida(self.estado, destino)
        self.estado = destino

    def dias_restantes(self, hoy: date) -> int | None:
        """Devuelve los días que faltan hasta la fecha límite.

        Args:
            hoy: Fecha de referencia.

        Returns:
            Número de días (negativo si ya pasó) o ``None`` si no hay fecha límite.
        """
        if self.fecha_limite is None:
            return None
        return (self.fecha_limite - hoy).days

    def esta_vencido(self, hoy: date) -> bool:
        """Indica si el objetivo sigue activo y ya pasó su fecha límite."""
        return (
            self.estado == EstadoObjetivo.ACTIVO
            and self.fecha_limite is not None
            and hoy > self.fecha_limite
        )

"""Modelo de dominio de los recordatorios."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.errores import TransicionNoPermitida


class EstadoRecordatorio(StrEnum):
    """Situación de un recordatorio."""

    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    CANCELADO = "cancelado"


class RepeticionRecordatorio(StrEnum):
    """Patrón de repetición de un recordatorio."""

    SEMANAL = "semanal"
    MENSUAL = "mensual"


@dataclass
class Recordatorio:
    """Aviso programado para un momento concreto.

    Attributes:
        usuario_id: Identificador del usuario destinatario.
        mensaje: Texto que se mostrará al usuario.
        programado_para: Momento del aviso, con zona horaria.
        id: Identificador único (UUID), generado automáticamente.
        evento_id: Evento asociado, si el aviso es de un evento.
        habito_id: Hábito asociado, si el aviso es de un hábito.
        estado: Situación actual; por defecto ``PENDIENTE``.
        repeticion: Patrón de repetición (semanal o mensual), o ``None``.
    """

    usuario_id: UUID
    mensaje: str
    programado_para: datetime
    id: UUID = field(default_factory=uuid4)
    evento_id: UUID | None = None
    habito_id: UUID | None = None
    estado: EstadoRecordatorio = EstadoRecordatorio.PENDIENTE
    repeticion: RepeticionRecordatorio | None = None

    def marcar_enviado(self) -> None:
        """Pasa el recordatorio de ``PENDIENTE`` a ``ENVIADO``.

        Raises:
            TransicionNoPermitida: Si el recordatorio ya está enviado o cancelado.
        """
        self._cambiar_desde_pendiente(EstadoRecordatorio.ENVIADO)

    def cancelar(self) -> None:
        """Pasa el recordatorio de ``PENDIENTE`` a ``CANCELADO``.

        Raises:
            TransicionNoPermitida: Si el recordatorio ya está enviado o cancelado.
        """
        self._cambiar_desde_pendiente(EstadoRecordatorio.CANCELADO)

    def restablecer(self) -> None:
        """Devuelve el recordatorio a ``PENDIENTE`` desde cualquier estado.

        Es la corrección manual explícita de un cambio hecho por error; los
        métodos normales no permiten volver atrás.
        """
        self.estado = EstadoRecordatorio.PENDIENTE

    def _cambiar_desde_pendiente(self, destino: EstadoRecordatorio) -> None:
        """Cambia el estado solo si el recordatorio está pendiente."""
        if self.estado != EstadoRecordatorio.PENDIENTE:
            raise TransicionNoPermitida(self.estado, destino)
        self.estado = destino

    def siguiente_ocurrencia(self) -> datetime | None:
        """Calcula la próxima ocurrencia del recordatorio según su patrón.

        Returns:
            La próxima fecha programada, o ``None`` si el recordatorio no se repite.
        """
        if self.repeticion is None:
            return None
        if self.repeticion == RepeticionRecordatorio.SEMANAL:
            return self.programado_para + timedelta(weeks=1)
        if self.repeticion == RepeticionRecordatorio.MENSUAL:
            mes = self.programado_para.month + 1
            anio = self.programado_para.year
            if mes > 12:
                mes = 1
                anio += 1
            try:
                return self.programado_para.replace(year=anio, month=mes)
            except ValueError:
                import calendar
                ultimo_dia = calendar.monthrange(anio, mes)[1]
                return self.programado_para.replace(
                    year=anio, month=mes, day=ultimo_dia
                )
        return None

    def esta_vencido(self, ahora: datetime) -> bool:
        """Indica si sigue pendiente y su hora ya ha llegado o pasado.

        Args:
            ahora: Momento de referencia, con zona horaria.
        """
        return self.estado == EstadoRecordatorio.PENDIENTE and self.programado_para <= ahora

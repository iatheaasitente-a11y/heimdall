"""Errores previstos al usar los servicios de aplicación."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from uuid import UUID

from app.domain.errores import TransicionNoPermitida


class ErrorDeServicio(Exception):
    """Clase base de los errores previstos de los servicios."""


class UsuarioNoEncontrado(ErrorDeServicio):
    """No existe el usuario solicitado."""

    def __init__(self, usuario_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el usuario {usuario_id}.")
        self.usuario_id = usuario_id


class EventoNoEncontrado(ErrorDeServicio):
    """No existe el evento solicitado."""

    def __init__(self, evento_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el evento {evento_id}.")
        self.evento_id = evento_id


class ConflictoDeHorario(ErrorDeServicio):
    """El evento choca con otro ya programado del mismo usuario."""

    def __init__(self, titulo: str) -> None:
        """Guarda el título del evento y construye el mensaje."""
        super().__init__(f"El evento «{titulo}» choca con otro ya programado.")
        self.titulo = titulo


class RecordatorioNoEncontrado(ErrorDeServicio):
    """No existe el recordatorio solicitado."""

    def __init__(self, recordatorio_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el recordatorio {recordatorio_id}.")
        self.recordatorio_id = recordatorio_id


class RecordatorioEnElPasado(ErrorDeServicio):
    """La hora del recordatorio ya ha pasado."""

    def __init__(self, cuando: datetime) -> None:
        """Guarda la hora indicada y construye el mensaje."""
        super().__init__(f"La hora del recordatorio ({cuando:%Y-%m-%d %H:%M}) ya ha pasado.")
        self.cuando = cuando


class EventoNoActivo(ErrorDeServicio):
    """El evento está cancelado o completado y no admite la operación."""

    def __init__(self, titulo: str) -> None:
        """Guarda el título del evento y construye el mensaje."""
        super().__init__(f"El evento «{titulo}» está cancelado o completado.")
        self.titulo = titulo


class CambioDeEstadoNoPermitido(ErrorDeServicio):
    """Se pidió un cambio de estado que las reglas no permiten."""

    def __init__(self, detalle: str) -> None:
        """Guarda el detalle y construye el mensaje."""
        super().__init__(detalle)
        self.detalle = detalle


class HabitoNoEncontrado(ErrorDeServicio):
    """No existe el hábito solicitado."""

    def __init__(self, habito_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el hábito {habito_id}.")
        self.habito_id = habito_id


class HabitoInactivo(ErrorDeServicio):
    """El hábito está desactivado y no admite nuevos registros."""

    def __init__(self, nombre: str) -> None:
        """Guarda el nombre del hábito y construye el mensaje."""
        super().__init__(f"El hábito «{nombre}» está desactivado.")
        self.nombre = nombre


class RegistroNoEncontrado(ErrorDeServicio):
    """No existe el registro de hábito solicitado."""

    def __init__(self, registro_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el registro {registro_id}.")
        self.registro_id = registro_id


class ObjetivoNoEncontrado(ErrorDeServicio):
    """No existe el objetivo solicitado."""

    def __init__(self, objetivo_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe el objetivo {objetivo_id}.")
        self.objetivo_id = objetivo_id


class ObjetivoNoActivo(ErrorDeServicio):
    """El objetivo no está activo y no admite cambios de progreso."""

    def __init__(self, nombre: str) -> None:
        """Guarda el nombre del objetivo y construye el mensaje."""
        super().__init__(f"El objetivo «{nombre}» no está activo.")
        self.nombre = nombre


class FechaLimiteEnElPasado(ErrorDeServicio):
    """La fecha límite indicada ya ha pasado."""

    def __init__(self, fecha_limite: date) -> None:
        """Guarda la fecha límite rechazada y construye el mensaje."""
        super().__init__(f"La fecha límite ({fecha_limite:%Y-%m-%d}) ya ha pasado.")
        self.fecha_limite = fecha_limite


class ConversacionNoEncontrada(ErrorDeServicio):
    """No existe la conversación solicitada."""

    def __init__(self, conversacion_id: UUID) -> None:
        """Guarda el identificador buscado y construye el mensaje."""
        super().__init__(f"No existe la conversación {conversacion_id}.")
        self.conversacion_id = conversacion_id


class ConversacionCerrada(ErrorDeServicio):
    """La conversación está cerrada y no admite cambios."""

    def __init__(self, titulo: str) -> None:
        """Guarda el título de la conversación y construye el mensaje."""
        super().__init__(f"La conversación «{titulo}» está cerrada.")
        self.titulo = titulo


@contextmanager
def transicion_de_estado() -> Iterator[None]:
    """Convierte ``TransicionNoPermitida`` del dominio en ``CambioDeEstadoNoPermitido``."""
    try:
        yield
    except TransicionNoPermitida as error:
        raise CambioDeEstadoNoPermitido(str(error)) from error

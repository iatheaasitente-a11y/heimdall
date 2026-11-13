"""Modelo de dominio de la agenda: eventos y horario."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.domain.errores import TransicionNoPermitida


class EstadoEvento(StrEnum):
    """Ciclo de vida de un evento."""

    PROGRAMADO = "programado"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class Repeticion(StrEnum):
    """Patrón de repetición de un evento."""

    SEMANAL = "semanal"
    MENSUAL = "mensual"


@dataclass
class Evento:
    """Actividad con hora de inicio y de fin en la agenda de un usuario.

    Attributes:
        usuario_id: Identificador del usuario propietario.
        titulo: Nombre corto del evento.
        comienza: Inicio, con zona horaria.
        termina: Fin, con zona horaria. Debe ser posterior a ``comienza``.
        id: Identificador único (UUID), generado automáticamente.
        descripcion: Detalles opcionales.
        ubicacion: Lugar opcional.
        estado: Estado actual; por defecto ``PROGRAMADO``.
        todo_el_dia: Si es ``True``, el evento ocupa el día completo.
        repeticion: Patrón de repetición (semanal o mensual), o ``None``.
    """

    usuario_id: UUID
    titulo: str
    comienza: datetime
    termina: datetime
    id: UUID = field(default_factory=uuid4)
    descripcion: str | None = None
    ubicacion: str | None = None
    estado: EstadoEvento = EstadoEvento.PROGRAMADO
    todo_el_dia: bool = False
    repeticion: Repeticion | None = None

    def __post_init__(self) -> None:
        """Valida el evento al crearlo.

        Raises:
            ValueError: Si ``termina`` no es posterior a ``comienza``.
        """
        if self.termina <= self.comienza:
            raise ValueError(
                "La fecha de finalización debe ser posterior a la de inicio."
            )

    def cancelar(self) -> None:
        """Pasa el evento de ``PROGRAMADO`` a ``CANCELADO``.

        Raises:
            TransicionNoPermitida: Si el evento ya está completado o cancelado.
        """
        self._cambiar_desde_programado(EstadoEvento.CANCELADO)

    def completar(self) -> None:
        """Pasa el evento de ``PROGRAMADO`` a ``COMPLETADO``.

        Raises:
            TransicionNoPermitida: Si el evento ya está completado o cancelado.
        """
        self._cambiar_desde_programado(EstadoEvento.COMPLETADO)

    def restablecer(self) -> None:
        """Devuelve el evento a ``PROGRAMADO`` desde cualquier estado.

        Es la corrección manual explícita de un cambio hecho por error; los
        métodos normales no permiten volver atrás.
        """
        self.estado = EstadoEvento.PROGRAMADO

    def _cambiar_desde_programado(self, destino: EstadoEvento) -> None:
        """Cambia el estado solo si el evento está programado."""
        if self.estado != EstadoEvento.PROGRAMADO:
            raise TransicionNoPermitida(self.estado, destino)
        self.estado = destino

    def esta_activo(self) -> bool:
        """Indica si el evento sigue programado (ni cancelado ni completado)."""
        return self.estado == EstadoEvento.PROGRAMADO

    def duracion(self) -> timedelta:
        """Devuelve el tiempo que dura el evento."""
        return self.termina - self.comienza

    def siguiente_ocurrencia(self, desde: datetime) -> datetime | None:
        """Calcula la próxima ocurrencia del evento según su patrón de repetición.

        Args:
            desde: Fecha desde la que buscar la próxima ocurrencia.

        Returns:
            La próxima fecha de inicio, o ``None`` si el evento no se repite.
        """
        if self.repeticion is None:
            return None
        if self.repeticion == Repeticion.SEMANAL:
            return self.comienza + timedelta(weeks=1)
        if self.repeticion == Repeticion.MENSUAL:
            mes = self.comienza.month + 1
            anio = self.comienza.year
            if mes > 12:
                mes = 1
                anio += 1
            try:
                return self.comienza.replace(year=anio, month=mes)
            except ValueError:
                import calendar
                ultimo_dia = calendar.monthrange(anio, mes)[1]
                return self.comienza.replace(year=anio, month=mes, day=ultimo_dia)
        return None

    def se_solapa_con(self, otro: "Evento") -> bool:
        """Indica si dos eventos coinciden en algún tramo de tiempo.

        El solape es estricto: si uno termina justo cuando empieza el otro
        (10:00-11:00 y 11:00-12:00), no se consideran solapados.
        """
        return self.comienza < otro.termina and otro.comienza < self.termina


class Horario:
    """Conjunto de eventos sobre el que se hacen consultas de agenda.

    Attributes:
        eventos: Eventos que forman el horario.
    """

    def __init__(self, eventos: list[Evento]) -> None:
        """Crea el horario con la lista de eventos indicada."""
        self.eventos = eventos

    def eventos_ordenados(self) -> list[Evento]:
        """Devuelve todos los eventos ordenados por hora de inicio."""
        return sorted(self.eventos, key=lambda evento: evento.comienza)

    def eventos_del_dia(self, dia: date, zona: ZoneInfo) -> list[Evento]:
        """Devuelve los eventos activos que empiezan en un día concreto.

        Args:
            dia: Día buscado.
            zona: Zona horaria con la que se decide a qué día pertenece cada evento.

        Returns:
            Eventos activos de ese día, ordenados por hora de inicio.
        """
        del_dia = [
            e for e in self.eventos
            if e.esta_activo() and e.comienza.astimezone(zona).date() == dia
        ]
        return sorted(del_dia, key=lambda evento: evento.comienza)

    def hay_conflicto(self, nuevo: Evento) -> bool:
        """Indica si un evento nuevo choca con alguno ya existente.

        Solo se comparan los eventos activos del mismo usuario y se ignora el propio
        evento (mismo ``id``), de modo que editar un evento no choca consigo mismo.
        """
        return any(
            e.id != nuevo.id
            and e.usuario_id == nuevo.usuario_id
            and e.esta_activo()
            and e.se_solapa_con(nuevo)
            for e in self.eventos
        )

    def celdas_del_dia(self, dia: date, zona: ZoneInfo, minutos: int = 15) -> list[bool]:
        """Divide un día en tramos y marca cuáles están ocupados.

        Args:
            dia: Día a analizar.
            zona: Zona horaria que define el inicio y el fin del día.
            minutos: Duración de cada tramo; por defecto 15.

        Returns:
            Una lista con un booleano por tramo (``True`` = ocupado). Un día de
            15 minutos tiene 96 tramos; los días de cambio de hora tienen 92 o 100.
            Las celdas se calculan al momento y no se guardan.
        """
        inicio = datetime.combine(dia, time.min, tzinfo=zona).astimezone(UTC)
        fin = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=zona).astimezone(UTC)
        paso = timedelta(minutes=minutos)
        total = int((fin - inicio) / paso)
        activos = [e for e in self.eventos if e.esta_activo()]
        celdas = []
        for i in range(total):
            desde = inicio + i * paso
            hasta = desde + paso
            celdas.append(any(e.comienza < hasta and desde < e.termina for e in activos))
        return celdas

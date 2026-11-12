"""Casos de uso de la agenda: crear, mover y consultar eventos."""

from datetime import date, datetime, time, timedelta
from uuid import UUID

from app.domain.reminder import EstadoRecordatorio, Recordatorio
from app.domain.schedule import Evento, Horario
from app.repositories.interfaces import (
    RepositorioEventos,
    RepositorioRecordatorios,
    RepositorioUsuarios,
)
from app.schemas.schedule import EventoSchema
from app.services.resolucion import resolver_por_nombre
from app.services.errores import (
    ConflictoDeHorario,
    EventoNoActivo,
    EventoNoEncontrado,
    exigir_usuario,
    obtener_entidad_de_usuario,
    transicion_de_estado,
)


class ServicioAgenda:
    """Gestión de la agenda de un usuario.

    Valida los datos con los esquemas, impide solapes entre eventos activos del
    mismo usuario y delega el almacenamiento en los repositorios. No hace
    ``commit``: de eso se encarga quien abre la conexión.

    Toda operación sobre un evento concreto recibe también el ``usuario_id`` de
    quien la pide y solo actúa si el evento es suyo; si es de otro usuario,
    responde igual que si no existiera, para no revelar que existe.

    Si se le da un repositorio de recordatorios, mantiene coherentes los avisos
    de cada evento: al crearlo genera un aviso automático para su inicio, al
    cancelarlo o completarlo cancela los pendientes y al reprogramarlo los
    desplaza lo mismo que se movió el evento.
    """

    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        eventos: RepositorioEventos,
        recordatorios: RepositorioRecordatorios | None = None,
    ) -> None:
        """Crea el servicio sobre los repositorios de usuarios, eventos y recordatorios."""
        self._usuarios = usuarios
        self._eventos = eventos
        self._recordatorios = recordatorios

    def crear_evento(
        self,
        usuario_id: UUID,
        titulo: str,
        comienza: datetime,
        termina: datetime,
        descripcion: str | None = None,
        ubicacion: str | None = None,
        todo_el_dia: bool = False,
    ) -> Evento:
        """Crea y guarda un evento si no choca con ninguno activo del usuario.

        Si ``todo_el_dia`` es ``True``, ajusta las horas al día completo en la
        zona horaria del usuario (00:00 a 23:59:59.999999).

        Si hay repositorio de recordatorios, crea también un aviso automático
        para el inicio del evento.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            ValueError: Si ``termina`` no es posterior a ``comienza``.
            pydantic.ValidationError: Si el título está vacío o las fechas no
                llevan zona horaria.
            ConflictoDeHorario: Si se solapa con otro evento activo.
        """
        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        if todo_el_dia:
            zona = usuario.zona()
            dia = comienza.astimezone(zona).date()
            comienza = datetime.combine(dia, time.min, tzinfo=zona)
            termina = datetime.combine(
                dia, time(23, 59, 59, 999999), tzinfo=zona
            )
        evento = Evento(
            usuario_id,
            titulo.strip(),
            comienza,
            termina,
            descripcion=descripcion,
            ubicacion=ubicacion,
            todo_el_dia=todo_el_dia,
        )
        EventoSchema.model_validate(evento)
        self._exigir_sin_conflicto(evento)
        self._eventos.guardar(evento)
        self._crear_recordatorio_automatico(usuario, evento)
        return evento

    def obtener_evento(self, usuario_id: UUID, evento_id: UUID) -> Evento:
        """Devuelve un evento del usuario indicado.

        Raises:
            EventoNoEncontrado: Si no existe o pertenece a otro usuario.
        """
        return obtener_entidad_de_usuario(
            self._eventos.obtener, usuario_id, evento_id, EventoNoEncontrado
        )

    def cancelar_evento(self, usuario_id: UUID, evento_id: UUID) -> Evento:
        """Cancela el evento, cancela sus recordatorios pendientes y guarda el cambio.

        Raises:
            EventoNoEncontrado: Si no existe o pertenece a otro usuario.
            CambioDeEstadoNoPermitido: Si el evento ya está cancelado o completado.
        """
        evento = self.obtener_evento(usuario_id, evento_id)
        with transicion_de_estado():
            evento.cancelar()
        self._eventos.guardar(evento)
        self._cancelar_recordatorios_pendientes(evento.id)
        return evento

    def completar_evento(self, usuario_id: UUID, evento_id: UUID) -> Evento:
        """Marca el evento como completado, cancela sus recordatorios pendientes y guarda.

        Raises:
            EventoNoEncontrado: Si no existe o pertenece a otro usuario.
            CambioDeEstadoNoPermitido: Si el evento ya está cancelado o completado.
        """
        evento = self.obtener_evento(usuario_id, evento_id)
        with transicion_de_estado():
            evento.completar()
        self._eventos.guardar(evento)
        self._cancelar_recordatorios_pendientes(evento.id)
        return evento

    def reprogramar_evento(
        self,
        usuario_id: UUID,
        evento_id: UUID,
        comienza: datetime,
        termina: datetime,
    ) -> Evento:
        """Cambia las horas de un evento comprobando que no choque con otros.

        El evento no se considera en conflicto consigo mismo. Solo se pueden
        reprogramar eventos programados. Los recordatorios pendientes del evento se
        desplazan lo mismo que se movió el evento.

        Raises:
            EventoNoEncontrado: Si el evento no existe o pertenece a otro usuario.
            EventoNoActivo: Si el evento está cancelado o completado.
            ValueError: Si ``termina`` no es posterior a ``comienza``.
            pydantic.ValidationError: Si las fechas no llevan zona horaria.
            ConflictoDeHorario: Si las nuevas horas se solapan con otro evento activo.
        """
        actual = self.obtener_evento(usuario_id, evento_id)
        if not actual.esta_activo():
            raise EventoNoActivo(actual.titulo)
        candidato = Evento(
            actual.usuario_id,
            actual.titulo,
            comienza,
            termina,
            id=actual.id,
            descripcion=actual.descripcion,
            ubicacion=actual.ubicacion,
            estado=actual.estado,
            todo_el_dia=actual.todo_el_dia,
        )
        EventoSchema.model_validate(candidato)
        self._exigir_sin_conflicto(candidato)
        self._eventos.guardar(candidato)
        self._desplazar_recordatorios_pendientes(candidato.id, comienza - actual.comienza)
        return candidato

    def eventos_del_dia(self, usuario_id: UUID, dia: date) -> list[Evento]:
        """Devuelve los eventos programados del usuario que empiezan ese día.

        El día se calcula en la zona horaria del usuario.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        return self._eventos.listar_activos_del_dia(usuario_id, dia, usuario.zona())

    def listar_eventos(self, usuario_id: UUID) -> list[Evento]:
        """Lista todos los eventos del usuario en orden cronológico.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        exigir_usuario(self._usuarios.obtener, usuario_id)
        return self._eventos.listar_por_usuario(usuario_id)

    def resolver_evento_id(self, usuario_id: UUID, titulo: str) -> UUID:
        """Resuelve el título exacto de un evento propio a su identificador."""
        return resolver_por_nombre(
            titulo, self.listar_eventos(usuario_id), lambda evento: evento.titulo, "eventos"
        )

    def celdas_del_dia(
        self, usuario_id: UUID, dia: date, minutos: int = 15
    ) -> list[bool]:
        """Devuelve los tramos del día marcados como ocupados (``True``) o libres.

        El día se calcula en la zona horaria del usuario.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        horario = Horario(self._eventos.listar_por_usuario(usuario_id))
        return horario.celdas_del_dia(dia, usuario.zona(), minutos)

    def proximo_evento(
        self,
        usuario_id: UUID,
        ahora: datetime,
    ) -> Evento | None:
        """Devuelve el siguiente evento activo que aun no ha terminado."""

        exigir_usuario(self._usuarios.obtener, usuario_id)
        eventos = [
            evento
            for evento in self._eventos.listar_por_usuario(usuario_id)
            if evento.esta_activo() and evento.termina > ahora
        ]
        eventos.sort(key=lambda evento: evento.comienza)
        return eventos[0] if eventos else None

    def huecos_libres(
        self,
        usuario_id: UUID,
        dia: date,
        desde: datetime,
        hasta: datetime,
        minutos: int = 30,
    ) -> list[dict[str, str]]:
        """Devuelve los huecos libres de al menos ``minutos`` en una franja."""

        usuario = exigir_usuario(self._usuarios.obtener, usuario_id)
        eventos = sorted(
            self._eventos.listar_activos_del_dia(
                usuario_id,
                dia,
                usuario.zona(),
            ),
            key=lambda evento: evento.comienza,
        )

        huecos: list[tuple[datetime, datetime]] = []
        cursor = desde

        for evento in eventos:
            if evento.termina <= desde or evento.comienza >= hasta:
                continue

            if evento.comienza > cursor:
                huecos.append((cursor, min(evento.comienza, hasta)))

            cursor = max(cursor, evento.termina)

        if cursor < hasta:
            huecos.append((cursor, hasta))

        return [
            {
                "comienza": inicio.isoformat(),
                "termina": fin.isoformat(),
            }
            for inicio, fin in huecos
            if fin - inicio >= timedelta(minutes=minutos)
        ]

    def _exigir_sin_conflicto(self, evento: Evento) -> None:
        """Lanza ``ConflictoDeHorario`` si un evento activo choca con otro."""
        if not evento.esta_activo():
            return
        horario = Horario(self._eventos.listar_por_usuario(evento.usuario_id))
        if horario.hay_conflicto(evento):
            raise ConflictoDeHorario(evento.titulo)

    def _crear_recordatorio_automatico(self, usuario, evento: Evento) -> None:
        """Crea un aviso para el inicio del evento si hay repositorio de recordatorios."""
        if self._recordatorios is None:
            return
        hora = evento.comienza.astimezone(usuario.zona())
        recordatorio = Recordatorio(
            usuario.id,
            f"{evento.titulo} empieza a las {hora:%H:%M}",
            evento.comienza,
            evento_id=evento.id,
        )
        self._recordatorios.guardar(recordatorio)

    def _recordatorios_pendientes(self, evento_id: UUID) -> list[Recordatorio]:
        """Devuelve los recordatorios pendientes de un evento (vacío si no hay repositorio)."""
        if self._recordatorios is None:
            return []
        return [
            r
            for r in self._recordatorios.listar_de_evento(evento_id)
            if r.estado == EstadoRecordatorio.PENDIENTE
        ]

    def _cancelar_recordatorios_pendientes(self, evento_id: UUID) -> None:
        """Cancela los recordatorios pendientes de un evento."""
        for recordatorio in self._recordatorios_pendientes(evento_id):
            recordatorio.cancelar()
            self._recordatorios.guardar(recordatorio)

    def _desplazar_recordatorios_pendientes(
        self, evento_id: UUID, desplazamiento: timedelta
    ) -> None:
        """Mueve los recordatorios pendientes de un evento la misma duración que el evento."""
        for recordatorio in self._recordatorios_pendientes(evento_id):
            recordatorio.programado_para += desplazamiento
            self._recordatorios.guardar(recordatorio)

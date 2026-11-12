"""Modelos Pydantic de los argumentos expuestos a los motores de lenguaje."""

from datetime import date
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.goal import EstadoObjetivo
from app.domain.habit import FrecuenciaHabito


class Parametros(BaseModel):
    """Esquema base que rechaza propiedades no declaradas."""

    model_config = ConfigDict(extra="forbid")


class CrearEvento(Parametros):
    """Parámetros para crear un evento."""

    titulo: str = Field(max_length=500)
    comienza: AwareDatetime
    termina: AwareDatetime
    descripcion: str | None = Field(default=None, max_length=500)
    ubicacion: str | None = Field(default=None, max_length=500)


class IdentificadorEvento(Parametros):
    """Identificador UUID o título de un evento."""

    evento_id: UUID | None = None
    titulo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "IdentificadorEvento":
        """Exige un UUID o un título, pero no ambos."""
        _validar_selector(self.evento_id, self.titulo)
        return self


class ReprogramarEvento(IdentificadorEvento):
    """Identificador y nuevo intervalo de un evento."""

    comienza: AwareDatetime
    termina: AwareDatetime


class Dia(Parametros):
    """Día sobre el que se consulta."""

    dia: date


class CrearHabito(Parametros):
    """Parámetros para crear un hábito."""

    nombre: str = Field(max_length=500)
    frecuencia: FrecuenciaHabito = FrecuenciaHabito.DIARIA
    objetivo: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    unidad: str = Field(default="veces", max_length=500)
    descripcion: str | None = Field(default=None, max_length=500)


class RegistrarProgresoHabito(Parametros):
    """Parámetros para registrar progreso por UUID o nombre de hábito."""

    habito_id: UUID | None = None
    nombre: str | None = Field(default=None, max_length=500)
    valor: float = Field(ge=0, allow_inf_nan=False)
    cuando: AwareDatetime | None = None
    notas: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "RegistrarProgresoHabito":
        """Exige un UUID o un nombre, pero no ambos."""
        _validar_selector(self.habito_id, self.nombre)
        return self


class ConsultarHabito(Parametros):
    """Parámetros para consultar un hábito por UUID o nombre."""

    habito_id: UUID | None = None
    nombre: str | None = Field(default=None, max_length=500)
    dia: date | None = None

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "ConsultarHabito":
        """Exige un UUID o un nombre, pero no ambos."""
        _validar_selector(self.habito_id, self.nombre)
        return self


class CrearObjetivo(Parametros):
    """Parámetros para crear un objetivo."""

    nombre: str = Field(max_length=500)
    descripcion: str | None = Field(default=None, max_length=500)
    fecha_limite: date | None = None


class ActualizarProgresoObjetivo(Parametros):
    """Parámetros para actualizar progreso por UUID o nombre de objetivo."""

    objetivo_id: UUID | None = None
    nombre: str | None = Field(default=None, max_length=500)
    progreso: float = Field(ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "ActualizarProgresoObjetivo":
        """Exige un UUID o un nombre, pero no ambos."""
        _validar_selector(self.objetivo_id, self.nombre)
        return self


class CambiarEstadoObjetivo(Parametros):
    """Identificador UUID o nombre del objetivo que cambia de estado."""

    objetivo_id: UUID | None = None
    nombre: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "CambiarEstadoObjetivo":
        """Exige un UUID o un nombre, pero no ambos."""
        _validar_selector(self.objetivo_id, self.nombre)
        return self


class ListarObjetivos(Parametros):
    """Parámetros opcionales para filtrar objetivos."""

    estado: EstadoObjetivo | None = None


class ProgramarRecordatorio(Parametros):
    """Parámetros para programar un recordatorio libre."""

    mensaje: str = Field(max_length=500)
    cuando: AwareDatetime


class IdentificadorRecordatorio(Parametros):
    """Identificador UUID o texto de un recordatorio."""

    recordatorio_id: UUID | None = None
    mensaje: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exigir_un_selector(self) -> "IdentificadorRecordatorio":
        """Exige un UUID o un mensaje, pero no ambos."""
        _validar_selector(self.recordatorio_id, self.mensaje)
        return self


class ListarHabitos(Parametros):
    """Filtro opcional para listar hábitos."""

    solo_activos: bool = False


class ListarRecordatorios(Parametros):
    """Consulta para listar recordatorios del usuario."""


class ResumenDia(Parametros):
    """Día que se quiere resumir."""

    dia: date


class ConsultaNBA(Parametros):
    """Consulta de texto libre para la fuente NBA."""

    consulta: str = Field(min_length=1, max_length=500)


def _validar_selector(identificador: UUID | None, nombre: str | None) -> None:
    """Exige exactamente uno de los selectores de una entidad."""
    if (identificador is None) == (nombre is None):
        raise ValueError("Indica un identificador o un nombre, pero no ambos.")
    if nombre is not None and not nombre.strip():
        raise ValueError("El nombre no puede estar vacío.")


class Momento(Parametros):
    """Momento de referencia para consultas de agenda."""

    ahora: AwareDatetime


class ConsultaHuecos(Parametros):
    """Franja en la que buscar huecos libres."""

    dia: date
    desde: AwareDatetime
    hasta: AwareDatetime
    minutos: int = Field(default=30, gt=0)


class RecordatorioDeEvento(IdentificadorEvento):
    """Recordatorio previo a un evento."""

    minutos: int = Field(gt=0, le=10080)

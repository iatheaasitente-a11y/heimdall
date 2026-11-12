"""Modelos Pydantic de los argumentos expuestos a los motores de lenguaje."""

from datetime import date
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.goal import EstadoObjetivo
from app.domain.habit import FrecuenciaHabito


class Parametros(BaseModel):
    """Esquema base que rechaza propiedades no declaradas."""

    model_config = ConfigDict(extra="forbid")


class CrearEvento(Parametros):
    """Parámetros para crear un evento."""

    titulo: str
    comienza: AwareDatetime
    termina: AwareDatetime
    descripcion: str | None = None
    ubicacion: str | None = None


class IdentificadorEvento(Parametros):
    """Identificador de un evento."""

    evento_id: UUID


class ReprogramarEvento(IdentificadorEvento):
    """Identificador y nuevo intervalo de un evento."""

    comienza: AwareDatetime
    termina: AwareDatetime


class Dia(Parametros):
    """Día sobre el que se consulta."""

    dia: date


class CrearHabito(Parametros):
    """Parámetros para crear un hábito."""

    nombre: str
    frecuencia: FrecuenciaHabito = FrecuenciaHabito.DIARIA
    objetivo: float = Field(default=1.0, gt=0)
    unidad: str = "veces"
    descripcion: str | None = None


class RegistrarProgresoHabito(Parametros):
    """Parámetros para registrar progreso de un hábito."""

    habito_id: UUID
    valor: float = Field(ge=0)
    cuando: AwareDatetime | None = None
    notas: str | None = None


class ConsultarHabito(Parametros):
    """Parámetros para consultar un hábito y su fecha."""

    habito_id: UUID
    dia: date | None = None


class CrearObjetivo(Parametros):
    """Parámetros para crear un objetivo."""

    nombre: str
    descripcion: str | None = None
    fecha_limite: date | None = None


class ActualizarProgresoObjetivo(Parametros):
    """Parámetros para actualizar el progreso de un objetivo."""

    objetivo_id: UUID
    progreso: float = Field(ge=0, le=100)


class CambiarEstadoObjetivo(Parametros):
    """Identificador del objetivo que cambia de estado."""

    objetivo_id: UUID


class ListarObjetivos(Parametros):
    """Parámetros opcionales para filtrar objetivos."""

    estado: EstadoObjetivo | None = None


class ProgramarRecordatorio(Parametros):
    """Parámetros para programar un recordatorio libre."""

    mensaje: str
    cuando: AwareDatetime


class IdentificadorRecordatorio(Parametros):
    """Identificador de un recordatorio."""

    recordatorio_id: UUID


class ResumenDia(Parametros):
    """Día que se quiere resumir."""

    dia: date

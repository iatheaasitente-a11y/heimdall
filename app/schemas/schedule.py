"""Esquema de validación y conversión de los eventos de la agenda."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.domain.schedule import EstadoEvento, Evento, Repeticion
from app.schemas.comunes import TextoNoVacio


class EventoSchema(BaseModel):
    """Forma válida de un evento cuando entra o sale del sistema.

    Exige título con texto, fechas con zona horaria y un fin posterior al inicio.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    titulo: TextoNoVacio
    comienza: AwareDatetime
    termina: AwareDatetime
    descripcion: str | None = None
    ubicacion: str | None = None
    estado: EstadoEvento = EstadoEvento.PROGRAMADO
    todo_el_dia: bool = False
    repeticion: Repeticion | None = None

    @model_validator(mode="after")
    def termina_despues_de_empezar(self):
        """Comprueba que ``termina`` sea posterior a ``comienza``."""
        if self.termina <= self.comienza:
            raise ValueError("termina debe ser posterior a comienza.")
        return self


def evento_a_dict(evento: Evento) -> dict:
    """Convierte un ``Evento`` en un diccionario listo para JSON.

    Los UUID, las fechas y el estado se transforman en texto.
    """
    return EventoSchema.model_validate(evento).model_dump(mode="json")


def evento_desde_dict(datos: dict) -> Evento:
    """Crea un ``Evento`` a partir de un diccionario, validándolo antes.

    Raises:
        pydantic.ValidationError: Si algún dato no cumple las reglas del esquema.
    """
    esquema = EventoSchema.model_validate(datos)
    return Evento(**esquema.model_dump())

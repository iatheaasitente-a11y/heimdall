"""Herramienta para consultar una fuente NBA inyectada."""

from app.domain.nba.fuente import FuenteNBA
from app.tools.base import Herramienta
from app.tools.esquemas import ConsultaNBA


def herramienta_nba(fuente: FuenteNBA) -> Herramienta:
    """Crea una herramienta de consulta NBA sobre la fuente proporcionada."""
    return Herramienta(
        "nba_consultar",
        "Consulta información NBA disponible en la fuente configurada.",
        ConsultaNBA,
        lambda _usuario_id, argumentos: fuente.consultar(argumentos["consulta"]),
    )

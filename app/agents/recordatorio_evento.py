"""Detecta recordatorios ligados a una cita existente."""

import re
from datetime import datetime, timedelta
from uuid import UUID

from app.tools.registro import RegistroHerramientas

_PATRON = re.compile(
    r"recuerdame\s+(?P<titulo>.+?)\s+"
    r"(?P<minutos>\d+)\s+minutos?\s+antes",
    re.IGNORECASE,
)


def detectar_recordatorio_de_evento(
    herramientas: RegistroHerramientas,
    usuario_id: UUID,
    texto: str,
    ahora: datetime,
) -> dict[str, object] | None:
    """Propone un recordatorio N minutos antes de una cita existente."""
    coincidencia = _PATRON.search(texto)
    if coincidencia is None:
        return None

    titulo = coincidencia.group("titulo").strip()
    titulo = re.sub(
        r"^(el|la|los|las)\s+",
        "",
        titulo,
        flags=re.IGNORECASE,
    ).strip()
    minutos = int(coincidencia.group("minutos"))

    try:
        resultado = herramientas.obtener(
            "agenda_consultar_evento"
        ).ejecutar(
            usuario_id,
            {"evento_id": None, "titulo": titulo},
        )
    except KeyError:
        return None

    if resultado.get("ok") is not True:
        return None

    evento = resultado.get("datos")
    if not isinstance(evento, dict):
        return None

    comienza = datetime.fromisoformat(evento["comienza"])
    cuando = (comienza - timedelta(minutes=minutos)).astimezone(ahora.tzinfo)
    mensaje = f"Recordatorio de {titulo}"

    return {
        "propuesta": (
            f"Voy a programar un recordatorio de {titulo} "
            f"{minutos} minutos antes "
            f"({cuando.strftime('%d/%m/%Y %H:%M')}).\n\n"
            "Responde si para confirmar o no para cancelar."
        ),
        "herramienta": "recordatorios_programar",
        "argumentos": {
            "mensaje": mensaje,
            "cuando": cuando,
        },
    }

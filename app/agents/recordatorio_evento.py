"""Deteccion de recordatorios ligados a un evento existente."""

import re
from datetime import datetime, timedelta
from uuid import UUID

from app.tools.registro import RegistroHerramientas

_PATRON = re.compile(
    r"\brecu[eé]rdame\s+(?:el\s+|la\s+)?"
    r"(?P<titulo>.+?)\s+"
    r"(?P<minutos>\d+)\s+minutos?\s+antes\b",
    re.IGNORECASE,
)


def detectar_recordatorio_de_evento(
    herramientas: RegistroHerramientas,
    usuario_id: UUID,
    texto: str,
    ahora: datetime,
) -> dict[str, object] | None:
    """Detecta avisos del tipo: recuerdame el dentista 30 minutos antes."""

    coincidencia = _PATRON.search(texto)
    if coincidencia is None:
        return None

    titulo = coincidencia.group("titulo").strip()
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
    if comienza.tzinfo is None:
        comienza = comienza.replace(tzinfo=ahora.tzinfo)

    aviso = comienza - timedelta(minutes=minutos)

    if aviso <= ahora:
        return {
            "ok": False,
            "error": (
                f"No puedo programar un aviso para '{titulo}' porque "
                "el momento elegido ya ha pasado."
            ),
        }

    propuesta = (
        f"Voy a recordarte '{titulo}' {minutos} minutos antes, "
        f"el {aviso.strftime('%d/%m/%Y')} a las {aviso.strftime('%H:%M')}.\n\n"
        "Responde si para confirmar o no para cancelar."
    )

    return {
        "herramienta": "recordatorios_programar_para_evento",
        "argumentos": {
            "evento_id": evento.get("id"),
            "titulo": titulo,
            "minutos": minutos,
        },
        "propuesta": propuesta,
    }
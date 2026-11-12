"""Herramienta compuesta que resume agenda, hábitos y recordatorios del día."""

from datetime import date
from uuid import UUID

from app.domain.relations import resumen_del_dia
from app.services.agenda import ServicioAgenda
from app.services.habitos import ServicioHabitos
from app.services.recordatorios import ServicioRecordatorios
from app.services.usuarios import ServicioUsuarios
from app.tools.base import Herramienta
from app.tools.esquemas import ResumenDia


def herramienta_resumen_del_dia(
    usuarios: ServicioUsuarios,
    agenda: ServicioAgenda,
    habitos: ServicioHabitos,
    recordatorios: ServicioRecordatorios,
) -> Herramienta:
    """Crea la herramienta de resumen sin trasladar reglas al modelo."""

    def resumir(usuario_id: UUID, argumentos: dict) -> dict:
        dia: date = argumentos["dia"]
        usuario = usuarios.obtener(usuario_id)
        eventos = agenda.eventos_del_dia(usuario_id, dia)
        lista_habitos = habitos.listar_habitos(usuario_id)
        registros = [
            registro
            for habito in lista_habitos
            for registro in habitos.listar_registros(usuario_id, habito.id)
        ]
        avisos = recordatorios.pendientes_del_dia(usuario_id, dia)
        return resumen_del_dia(
            usuario, dia, eventos, lista_habitos, registros, avisos
        )

    return Herramienta(
        "resumen_del_dia",
        "Resume eventos, hábitos diarios pendientes y recordatorios de una fecha.",
        ResumenDia,
        resumir,
    )

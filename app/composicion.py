"""Composición de servicios, repositorios SQLite, herramientas y agentes."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.agents.fabrica import crear_agente
from app.agents.router import Router
from app.domain.nba.fuente import FuenteNBA
from app.llm.interfaz import MotorLLM
from app.repositories.sqlite_conversaciones import (
    RepositorioConversacionesSQLite,
    RepositorioMensajesSQLite,
)
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_habitos import (
    RepositorioHabitosSQLite,
    RepositorioRegistrosHabitoSQLite,
)
from app.repositories.sqlite_objetivos import RepositorioObjetivosSQLite
from app.repositories.sqlite_recordatorios import RepositorioRecordatoriosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda
from app.services.conversaciones import ServicioConversaciones
from app.services.habitos import ServicioHabitos
from app.services.objetivos import ServicioObjetivos
from app.services.recordatorios import ServicioRecordatorios
from app.services.usuarios import ServicioUsuarios
from app.tools.registro import RegistroHerramientas, registrar_herramientas


@dataclass(frozen=True)
class Composicion:
    """Servicios e interfaces públicas de una aplicación compuesta."""

    usuarios: ServicioUsuarios
    conversaciones: ServicioConversaciones
    herramientas: RegistroHerramientas
    router: Router


def crear_composicion(
    conexion: sqlite3.Connection,
    reloj: Callable[[], datetime],
    motor: MotorLLM | None = None,
    modo_llm: str | None = None,
    fuente_nba: FuenteNBA | None = None,
) -> Composicion:
    """Compone la aplicación sobre una conexión y dependencias inyectadas."""
    repositorio_usuarios = RepositorioUsuariosSQLite(conexion)
    repositorio_eventos = RepositorioEventosSQLite(conexion)
    repositorio_habitos = RepositorioHabitosSQLite(conexion)
    repositorio_registros = RepositorioRegistrosHabitoSQLite(conexion)
    repositorio_objetivos = RepositorioObjetivosSQLite(conexion)
    repositorio_recordatorios = RepositorioRecordatoriosSQLite(conexion)
    repositorio_conversaciones = RepositorioConversacionesSQLite(conexion)
    repositorio_mensajes = RepositorioMensajesSQLite(conexion)

    usuarios = ServicioUsuarios(repositorio_usuarios)
    agenda = ServicioAgenda(
        repositorio_usuarios,
        repositorio_eventos,
        repositorio_recordatorios,
    )
    habitos = ServicioHabitos(
        repositorio_usuarios,
        repositorio_habitos,
        repositorio_registros,
        reloj,
    )
    objetivos = ServicioObjetivos(
        repositorio_usuarios,
        repositorio_objetivos,
        reloj,
    )
    recordatorios = ServicioRecordatorios(
        repositorio_usuarios,
        repositorio_eventos,
        repositorio_recordatorios,
        reloj,
    )
    conversaciones = ServicioConversaciones(
        repositorio_usuarios,
        repositorio_conversaciones,
        repositorio_mensajes,
        reloj,
    )
    herramientas = registrar_herramientas(
        RegistroHerramientas(),
        usuarios,
        agenda,
        habitos,
        objetivos,
        recordatorios,
        fuente_nba,
    )

    def ahora_por_usuario(usuario_id: UUID) -> datetime:
        usuario = usuarios.obtener(usuario_id)
        return reloj().astimezone(usuario.zona())

    def hoy_por_usuario(usuario_id: UUID) -> date:
        return ahora_por_usuario(usuario_id).date()

    agente = crear_agente(
        "personal",
        herramientas,
        hoy_por_usuario,
        motor=motor,
        modo_llm=modo_llm,
        ahora_por_usuario=ahora_por_usuario,
    )
    return Composicion(
        usuarios,
        conversaciones,
        herramientas,
        Router(agente),
    )

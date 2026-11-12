"""Chatbot sencillo de terminal, ejecutable con ``python -m app.chatbot``."""

import argparse
import json
import sys
from datetime import UTC, datetime
from uuid import UUID

from app.composicion import crear_composicion
from app.database.connection import DEFAULT_DATABASE_PATH, sesion_sqlite
from app.database.init_db import inicializar_base_datos
from app.domain.message import RolMensaje
from app.llm.configuracion import crear_motor
from app.llm.ollama import MotorOllama


def main() -> None:
    """Inicia una conversación por terminal sobre la base SQLite local."""
    parser = argparse.ArgumentParser(description="Chatbot personal de Heimdall.")
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE_PATH),
        help="Ruta de la base de datos SQLite.",
    )
    parser.add_argument(
        "--usuario-id",
        help="UUID de un usuario existente; sin él se registra uno nuevo.",
    )
    parser.add_argument("--nombre", default="Usuario", help="Nombre del usuario nuevo.")
    parser.add_argument(
        "--titulo",
        default="Conversación de terminal",
        help="Título de la conversación nueva.",
    )
    argumentos = parser.parse_args()
    inicializar_base_datos(argumentos.database)
    with sesion_sqlite(argumentos.database) as conexion:
        motor = crear_motor()
        aplicacion = crear_composicion(
            conexion,
            reloj=lambda: datetime.now(UTC),
            motor=motor,
        )
        if isinstance(motor, MotorOllama):
            try:
                motor.calentar()
            except OSError as error:
                print(
                    f"Aviso: no se pudo precalentar Ollama ({error}); "
                    "se continuará con las reglas.",
                    file=sys.stderr,
                )
        if argumentos.usuario_id:
            usuario_id = UUID(argumentos.usuario_id)
            aplicacion.usuarios.obtener(usuario_id)
        else:
            usuario_id = aplicacion.usuarios.registrar(argumentos.nombre).id
            print(f"Usuario creado: {usuario_id}")
        conversacion = aplicacion.conversaciones.iniciar_conversacion(
            usuario_id,
            argumentos.titulo,
        )
        print("Escribe /salir para terminar.")
        while True:
            try:
                texto = input("Tú: ").strip()
            except EOFError:
                break
            if texto.casefold() in {"/salir", "/exit"}:
                break
            if not texto:
                continue
            aplicacion.conversaciones.agregar_mensaje(
                usuario_id,
                conversacion.id,
                RolMensaje.USUARIO,
                texto,
            )
            historial = aplicacion.conversaciones.historial_para_modelo(
                usuario_id,
                conversacion.id,
            )
            resultado = aplicacion.router.procesar(
                usuario_id,
                conversacion.id,
                texto,
                historial,
            )
            salida = resultado or {
                "ok": False,
                "error": "No he podido interpretar la solicitud.",
            }
            respuesta = json.dumps(salida, ensure_ascii=False)
            print(respuesta)
            aplicacion.conversaciones.agregar_mensaje(
                usuario_id,
                conversacion.id,
                RolMensaje.ASISTENTE,
                respuesta,
                {"resultado": salida},
            )
            conexion.commit()


if __name__ == "__main__":
    main()

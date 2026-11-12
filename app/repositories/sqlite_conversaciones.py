"""Repositorios de conversaciones y mensajes sobre SQLite."""

import json
import sqlite3
from uuid import UUID

from app.database.fechas import a_texto, desde_texto
from app.domain.message import Conversacion, Mensaje, RolMensaje
from app.repositories.interfaces import RepositorioConversaciones, RepositorioMensajes


class RepositorioConversacionesSQLite(RepositorioConversaciones):
    """Guarda y lee conversaciones en la tabla ``conversaciones``.

    No hace ``commit``: de eso se encarga quien abre la conexión.
    """

    def __init__(self, conexion: sqlite3.Connection) -> None:
        """Crea el repositorio sobre una conexión ya abierta."""
        self._conexion = conexion

    def guardar(self, conversacion: Conversacion) -> None:
        """Inserta o actualiza la conversación.

        Raises:
            sqlite3.IntegrityError: Si el usuario de la conversación no existe.
        """
        self._conexion.execute(
            """
            INSERT INTO conversaciones (
                id, usuario_id, titulo, fecha_creacion, activa
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                usuario_id = excluded.usuario_id,
                titulo = excluded.titulo,
                fecha_creacion = excluded.fecha_creacion,
                activa = excluded.activa
            """,
            (
                str(conversacion.id),
                str(conversacion.usuario_id),
                conversacion.titulo,
                a_texto(conversacion.fecha_creacion),
                int(conversacion.activa),
            ),
        )

    def obtener(self, conversacion_id: UUID) -> Conversacion | None:
        """Devuelve la conversación con ese ``id`` o ``None`` si no existe."""
        fila = self._conexion.execute(
            "SELECT * FROM conversaciones WHERE id = ?", (str(conversacion_id),)
        ).fetchone()
        return None if fila is None else _a_conversacion(fila)

    def listar_por_usuario(
        self, usuario_id: UUID, solo_activas: bool = False
    ) -> list[Conversacion]:
        """Devuelve las conversaciones de un usuario, las más recientes primero.

        Con ``solo_activas=True`` se omiten las conversaciones cerradas.
        """
        consulta = "SELECT * FROM conversaciones WHERE usuario_id = ?"
        if solo_activas:
            consulta += " AND activa = 1"
        consulta += " ORDER BY fecha_creacion DESC, id"
        filas = self._conexion.execute(consulta, (str(usuario_id),)).fetchall()
        return [_a_conversacion(fila) for fila in filas]

    def eliminar(self, conversacion_id: UUID) -> bool:
        """Elimina la conversación y, en cascada, sus mensajes. ``True`` si existía."""
        cursor = self._conexion.execute(
            "DELETE FROM conversaciones WHERE id = ?", (str(conversacion_id),)
        )
        return cursor.rowcount > 0


class RepositorioMensajesSQLite(RepositorioMensajes):
    """Guarda y lee mensajes en la tabla ``mensajes``.

    No hace ``commit``: de eso se encarga quien abre la conexión.
    """

    def __init__(self, conexion: sqlite3.Connection) -> None:
        """Crea el repositorio sobre una conexión ya abierta."""
        self._conexion = conexion

    def guardar(self, mensaje: Mensaje) -> None:
        """Inserta o actualiza el mensaje.

        Raises:
            sqlite3.IntegrityError: Si la conversación del mensaje no existe.
        """
        self._conexion.execute(
            """
            INSERT INTO mensajes (
                id, conversacion_id, rol, contenido,
                fecha_creacion, metadatos_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                conversacion_id = excluded.conversacion_id,
                rol = excluded.rol,
                contenido = excluded.contenido,
                fecha_creacion = excluded.fecha_creacion,
                metadatos_json = excluded.metadatos_json
            """,
            (
                str(mensaje.id),
                str(mensaje.conversacion_id),
                mensaje.rol.value,
                mensaje.contenido,
                a_texto(mensaje.fecha_creacion),
                json.dumps(mensaje.metadatos, ensure_ascii=False),
            ),
        )

    def obtener(self, mensaje_id: UUID) -> Mensaje | None:
        """Devuelve el mensaje con ese ``id`` o ``None`` si no existe."""
        fila = self._conexion.execute(
            "SELECT * FROM mensajes WHERE id = ?", (str(mensaje_id),)
        ).fetchone()
        return None if fila is None else _a_mensaje(fila)

    def listar_por_conversacion(self, conversacion_id: UUID) -> list[Mensaje]:
        """Devuelve los mensajes de una conversación, del más antiguo al más reciente."""
        filas = self._conexion.execute(
            "SELECT * FROM mensajes WHERE conversacion_id = ? ORDER BY fecha_creacion, id",
            (str(conversacion_id),),
        ).fetchall()
        return [_a_mensaje(fila) for fila in filas]

    def listar_ultimos(self, conversacion_id: UUID, limite: int) -> list[Mensaje]:
        """Devuelve los últimos ``limite`` mensajes, en orden cronológico.

        Pueden incluir mensajes vacíos. ``historial_para_modelo`` los descarta, así
        que puede devolver menos de ``limite`` entradas.

        Raises:
            ValueError: Si ``limite`` no es mayor que cero.
        """
        if limite <= 0:
            raise ValueError("El límite debe ser mayor que cero.")
        filas = self._conexion.execute(
            """
            SELECT * FROM (
                SELECT rowid AS orden_insercion, * FROM mensajes
                WHERE conversacion_id = ?
                ORDER BY rowid DESC
                LIMIT ?
            )
            ORDER BY orden_insercion
            """,
            (str(conversacion_id), limite),
        ).fetchall()
        return [_a_mensaje(fila) for fila in filas]

    def eliminar(self, mensaje_id: UUID) -> bool:
        """Elimina el mensaje. Devuelve ``True`` si existía."""
        cursor = self._conexion.execute(
            "DELETE FROM mensajes WHERE id = ?", (str(mensaje_id),)
        )
        return cursor.rowcount > 0


def _a_conversacion(fila: sqlite3.Row) -> Conversacion:
    """Convierte una fila de la tabla ``conversaciones`` en una ``Conversacion``."""
    return Conversacion(
        id=UUID(fila["id"]),
        usuario_id=UUID(fila["usuario_id"]),
        titulo=fila["titulo"],
        fecha_creacion=desde_texto(fila["fecha_creacion"]),
        activa=bool(fila["activa"]),
    )


def _a_mensaje(fila: sqlite3.Row) -> Mensaje:
    """Convierte una fila de la tabla ``mensajes`` en un ``Mensaje``."""
    return Mensaje(
        id=UUID(fila["id"]),
        conversacion_id=UUID(fila["conversacion_id"]),
        rol=RolMensaje(fila["rol"]),
        contenido=fila["contenido"],
        fecha_creacion=desde_texto(fila["fecha_creacion"]),
        metadatos=json.loads(fila["metadatos_json"]),
    )

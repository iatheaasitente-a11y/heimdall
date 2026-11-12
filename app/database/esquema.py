"""Creación y comprobación del esquema SQLite."""

import sqlite3
from collections.abc import Callable
from importlib.resources import files

TABLAS_REQUERIDAS = {
    "schema_version",
    "usuarios",
    "conversaciones",
    "mensajes",
    "eventos",
    "habitos",
    "registros_habito",
    "objetivos",
    "recordatorios",
}

VERSION_ESQUEMA = 1


def cargar_schema() -> str:
    """Devuelve el contenido del archivo ``schema.sql``."""
    return files("app.database").joinpath("schema.sql").read_text(encoding="utf-8")


def aplicar_schema(conexion: sqlite3.Connection) -> None:
    """Crea el esquema y aplica las migraciones pendientes en una transacción.

    Se puede ejecutar varias veces sin efectos secundarios.

    Raises:
        RuntimeError: Si la base tiene una versión más reciente o falta una
            migración intermedia.
        sqlite3.Error: Si SQLite no puede crear el esquema o aplicar una migración.
    """
    try:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript("BEGIN IMMEDIATE;\n" + cargar_schema())
        fila = conexion.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        if fila is None:
            conexion.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, 0)"
            )
            version_actual = 0
        else:
            version_actual = int(fila["version"])
        if version_actual > VERSION_ESQUEMA:
            raise RuntimeError(
                "La base de datos es más reciente que esta versión de Heimdall."
            )
        for version in range(version_actual + 1, VERSION_ESQUEMA + 1):
            migracion = _MIGRACIONES.get(version)
            if migracion is None:
                raise RuntimeError(f"Falta la migración de esquema {version}.")
            migracion(conexion)
            conexion.execute(
                "UPDATE schema_version SET version = ? WHERE id = 1",
                (version,),
            )
        conexion.commit()
    except Exception:
        if conexion.in_transaction:
            conexion.rollback()
        raise


def tablas_existentes(conexion: sqlite3.Connection) -> set[str]:
    """Devuelve los nombres de las tablas de usuario presentes en la base."""
    filas = conexion.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {fila["name"] for fila in filas}


def esquema_completo(conexion: sqlite3.Connection) -> bool:
    """Indica si existen las tablas requeridas y se aplicó la última migración."""
    if not TABLAS_REQUERIDAS.issubset(tablas_existentes(conexion)):
        return False
    fila = conexion.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    ).fetchone()
    return fila is not None and int(fila["version"]) == VERSION_ESQUEMA


def _proteger_mensajes(conexion: sqlite3.Connection) -> None:
    """Añade triggers que impiden modificar o borrar mensajes.

    Raises:
        sqlite3.Error: Si SQLite no puede crear los triggers.
    """
    conexion.execute(
        """
        CREATE TRIGGER IF NOT EXISTS mensajes_inmutables_no_actualizar
        BEFORE UPDATE ON mensajes
        BEGIN
            SELECT RAISE(ABORT, 'Los mensajes son inmutables.');
        END
        """
    )
    conexion.execute(
        """
        CREATE TRIGGER IF NOT EXISTS mensajes_inmutables_no_eliminar
        BEFORE DELETE ON mensajes
        BEGIN
            SELECT RAISE(ABORT, 'Los mensajes son inmutables.');
        END
        """
    )


_MIGRACIONES: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _proteger_mensajes,
}

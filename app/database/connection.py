"""Conexiones SQLite utilizadas por Heimdall."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DATABASE_PATH = Path("data/heimdall.sqlite3")


def crear_conexion(ruta: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Crea una conexión SQLite configurada para el proyecto.

    Args:
        ruta: Ruta del archivo SQLite o ``":memory:"``. Si el archivo está en una
            carpeta que no existe, se crea.

    Returns:
        Conexión con filas accesibles por nombre, claves foráneas activadas y
        una espera máxima de 5 segundos si la base está bloqueada.
    """
    if ruta != ":memory:":
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    try:
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.execute("PRAGMA busy_timeout = 5000")
        if ruta != ":memory:":
            modo = conexion.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if modo.casefold() != "wal":
                raise RuntimeError("SQLite no pudo habilitar el modo WAL.")
    except Exception:
        conexion.close()
        raise
    return conexion


@contextmanager
def sesion_sqlite(ruta: str | Path = DEFAULT_DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Abre una conexión transaccional y la cierra al terminar.

    Hace ``commit`` si el bloque termina sin errores y ``rollback`` si se produce
    una excepción, que se vuelve a lanzar.
    """
    conexion = crear_conexion(ruta)
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

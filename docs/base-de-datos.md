# Base de datos (SQLite)

Archivos en `app/database/`:

| Archivo | Función |
|---|---|
| `schema.sql` | Tablas, restricciones e índices |
| `connection.py` | Conexión y sesión con commit/rollback |
| `esquema.py` | Aplicar y comprobar el esquema |
| `fechas.py` | Conversión de fechas a texto UTC |
| `init_db.py` | Comando `python -m app.database.init_db` |

`schema_version` conserva la última migración aplicada. `aplicar_schema`
ejecuta migraciones secuenciales dentro de una transacción y rechaza bases con
una versión posterior a la que soporta el código actual.

## Tablas
schema_version, usuarios, conversaciones, mensajes, eventos, habitos,
registros_habito, objetivos y recordatorios.

La migración 1 impide con triggers actualizar o borrar filas de `mensajes`.
Las claves `ON DELETE CASCADE` existentes no se modifican. Como los triggers
también impiden la eliminación en cascada de mensajes, borrar una conversación o
un usuario que tenga mensajes aborta y conserva los datos. La política final
para las cascadas queda pendiente de decisión.

## Formatos
- UUID como texto; booleanos como 0/1; preferencias y metadatos como JSON.
- Fechas con hora: UTC con formato fijo `2026-10-23T18:00:00.000000+00:00`.
  Se generan siempre con `a_texto()`; la base rechaza cualquier otro formato.
- `fecha_limite` de objetivos: fecha simple `2026-12-31`.
- `registros_habito.completado` es informativo; los cálculos usan `valor`.
- `mensajes.contenido` puede estar vacío (llamadas a herramientas).

## Base local
El archivo `data/heimdall.sqlite3` no se sube a Git (ver `.gitignore`).
Las bases en archivo usan WAL; las conexiones `:memory:` conservan el modo
SQLite en memoria.

## Repositorios (`app/repositories/`)
- `interfaces.py`: operaciones que ofrece cada repositorio (clases abstractas).
- `sqlite_usuarios.py`, `sqlite_eventos.py`, `sqlite_habitos.py`, `sqlite_objetivos.py`, `sqlite_recordatorios.py` y `sqlite_conversaciones.py` (conversaciones y mensajes): implementación sobre SQLite.
- `guardar` usa `ON CONFLICT DO UPDATE`; los triggers rechazan las actualizaciones
  de mensajes. Nunca se usa `INSERT OR REPLACE`, porque borraría la fila y, por
  la cascada, los datos que dependen de ella.
- Los repositorios no hacen `commit`; lo hace quien abre la conexión (`sesion_sqlite`).

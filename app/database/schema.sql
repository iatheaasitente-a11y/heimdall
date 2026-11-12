PRAGMA foreign_keys = ON;

-- Convenciones:
--  * UUID como TEXT, booleanos como INTEGER (0/1), JSON como TEXT.
--  * Fechas con hora: texto UTC de formato fijo AAAA-MM-DDTHH:MM:SS.ffffff+00:00.
--    Con ese formato el orden alfabético coincide con el orden cronológico.
--    Se generan con app.database.fechas.a_texto().

CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL CHECK (version >= 0)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0),
    idioma TEXT NOT NULL DEFAULT 'es-ES'
        CHECK (length(trim(idioma)) > 0),
    zona_horaria TEXT NOT NULL DEFAULT 'Europe/Madrid'
        CHECK (length(trim(zona_horaria)) > 0),
    preferencias_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(preferencias_json)),
    fecha_creacion TEXT NOT NULL
        CHECK (fecha_creacion GLOB '????-??-??T??:??:??.??????+00:00'),
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS conversaciones (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    titulo TEXT NOT NULL
        CHECK (length(trim(titulo)) > 0),
    fecha_creacion TEXT NOT NULL
        CHECK (fecha_creacion GLOB '????-??-??T??:??:??.??????+00:00'),
    activa INTEGER NOT NULL DEFAULT 1
        CHECK (activa IN (0, 1)),
    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mensajes (
    id TEXT PRIMARY KEY,
    conversacion_id TEXT NOT NULL,
    rol TEXT NOT NULL
        CHECK (rol IN ('usuario', 'asistente', 'sistema', 'herramienta')),
    contenido TEXT NOT NULL,
    fecha_creacion TEXT NOT NULL
        CHECK (fecha_creacion GLOB '????-??-??T??:??:??.??????+00:00'),
    metadatos_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(metadatos_json)),
    FOREIGN KEY (conversacion_id)
        REFERENCES conversaciones(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS eventos (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    titulo TEXT NOT NULL
        CHECK (length(trim(titulo)) > 0),
    comienza TEXT NOT NULL
        CHECK (comienza GLOB '????-??-??T??:??:??.??????+00:00'),
    termina TEXT NOT NULL
        CHECK (termina GLOB '????-??-??T??:??:??.??????+00:00'),
    descripcion TEXT,
    ubicacion TEXT,
    estado TEXT NOT NULL DEFAULT 'programado'
        CHECK (estado IN ('programado', 'completado', 'cancelado')),
    CHECK (termina > comienza),
    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS habitos (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0),
    frecuencia TEXT NOT NULL
        CHECK (frecuencia IN ('diaria', 'semanal', 'mensual')),
    descripcion TEXT,
    objetivo REAL NOT NULL DEFAULT 1.0
        CHECK (objetivo > 0),
    unidad TEXT NOT NULL DEFAULT 'veces'
        CHECK (length(trim(unidad)) > 0),
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1)),
    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS registros_habito (
    id TEXT PRIMARY KEY,
    habito_id TEXT NOT NULL,
    valor REAL NOT NULL
        CHECK (valor >= 0),
    completado INTEGER NOT NULL DEFAULT 0
        CHECK (completado IN (0, 1)),
    fecha TEXT NOT NULL
        CHECK (fecha GLOB '????-??-??T??:??:??.??????+00:00'),
    notas TEXT,
    FOREIGN KEY (habito_id)
        REFERENCES habitos(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS objetivos (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0),
    descripcion TEXT,
    fecha_limite TEXT
        CHECK (fecha_limite IS NULL OR fecha_limite GLOB '????-??-??'),
    progreso REAL NOT NULL DEFAULT 0
        CHECK (progreso >= 0 AND progreso <= 100),
    estado TEXT NOT NULL DEFAULT 'activo'
        CHECK (estado IN ('activo', 'completado', 'pausado', 'cancelado')),
    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recordatorios (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    mensaje TEXT NOT NULL
        CHECK (length(trim(mensaje)) > 0),
    programado_para TEXT NOT NULL
        CHECK (programado_para GLOB '????-??-??T??:??:??.??????+00:00'),
    evento_id TEXT,
    habito_id TEXT,
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'enviado', 'cancelado')),
    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,
    FOREIGN KEY (evento_id)
        REFERENCES eventos(id)
        ON DELETE CASCADE,
    FOREIGN KEY (habito_id)
        REFERENCES habitos(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversaciones_usuario
    ON conversaciones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion_fecha
    ON mensajes(conversacion_id, fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_eventos_usuario_comienza
    ON eventos(usuario_id, comienza);
CREATE INDEX IF NOT EXISTS idx_habitos_usuario
    ON habitos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_registros_habito_fecha
    ON registros_habito(habito_id, fecha);
CREATE INDEX IF NOT EXISTS idx_objetivos_usuario_estado
    ON objetivos(usuario_id, estado);
CREATE INDEX IF NOT EXISTS idx_recordatorios_usuario_fecha
    ON recordatorios(usuario_id, programado_para);
CREATE INDEX IF NOT EXISTS idx_recordatorios_evento
    ON recordatorios(evento_id);
CREATE INDEX IF NOT EXISTS idx_recordatorios_habito
    ON recordatorios(habito_id);

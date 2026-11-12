# Servicios de aplicación (`app/services/`)

Capa entre los agentes y los repositorios. Cada servicio es un caso de uso:
valida con los esquemas, aplica las reglas del dominio y guarda con los repositorios.

## Reglas
- Reciben los repositorios (interfaces) por el constructor; no conocen SQL.
- Lanzan errores propios (`app/services/errores.py`), no errores de base de datos.
- No hacen `commit`: lo hace quien abre la conexión (`sesion_sqlite`).

## Servicios
| Servicio | Casos de uso |
|---|---|
| `ServicioUsuarios` | registrar, obtener, cambiar zona horaria y preferencias, desactivar |
| `ServicioAgenda` | crear, cancelar, completar y reprogramar eventos; eventos y celdas del día |
| `ServicioRecordatorios` | programar avisos libres o de un evento, cancelar, marcar enviado, pendientes del día y vencidos |
| `ServicioHabitos` | crear, listar y desactivar hábitos; registrar y borrar progreso; progreso del día y racha |
| `ServicioObjetivos` | crear, consultar y listar; actualizar progreso; gestionar estados y vencimientos |
| `ServicioConversaciones` | iniciar, renombrar y cerrar conversaciones; añadir y consultar mensajes e historial |

## Herramientas (`app/tools/`)

Las herramientas validan argumentos con modelos Pydantic y publican su esquema
JSON. Reciben `usuario_id` por separado para que el modelo no pueda elegirlo.
Delegan en servicios y devuelven resultados JSON; los errores de servicio se
representan como `{"ok": false, "error": "…"}`. No se exponen las operaciones
internas `marcar_enviado` ni `vencidos` de recordatorios. La consulta NBA se
registra solo si se inyecta una `FuenteNBA`; por ahora, la fuente disponible es
falsa y no consulta APIs reales.

Las herramientas que operan sobre un hábito, objetivo, evento o recordatorio
aceptan su UUID o su nombre/título. La búsqueda es exacta e ignora mayúsculas,
tildes y espacios exteriores; solo consulta datos del usuario actual. Si no
hay una coincidencia única, devuelve un error con `candidatos` para aclarar la
selección. También se ofrecen herramientas para listar hábitos y recordatorios.

## Adaptador Telegram

`ConectorTelegram` procesa actualizaciones de chats privados y usa el mapeo
inyectado a usuarios existentes. El ciclo recibe callbacks de confirmación,
reversión y pausa para aislar cada actualización: solo avanza el offset después
de procesarla y confirmarla. Los fallos se registran sin el detalle de la
excepción y se vuelven a intentar tras la pausa. El formateador expone texto y
nombres de candidatos, no JSON ni UUID internos. No se añade punto de arranque;
siguen pendientes la política de identidad y la conexión del ciclo a la aplicación.
Si no se puede revertir una actualización fallida, el ciclo se detiene para no
confirmar cambios parciales.

| Hallazgo | Estado en esta fase |
|---|---|
| 18 | Corregido: confirmación por actualización con callback inyectado. |
| 19 | Pendiente: falta decidir el punto de arranque y el origen del mapeo de identidad. |
| 20 | Corregido: el offset solo avanza tras confirmar; un fallo no salta actualizaciones. |
| 21 | Corregido: fallos aislados, registro sin detalles y pausa inyectada. |
| 22 | Corregido: salida de texto sin UUID internos. |
| 23 | Corregido: solo se aceptan chats privados. |

## Coherencia entre agenda y recordatorios
Si `ServicioAgenda` recibe el repositorio de recordatorios:
- Al cancelar o completar un evento se cancelan sus avisos pendientes.
- Al reprogramarlo, sus avisos pendientes se desplazan lo mismo que se movió el evento.
- Los avisos ya enviados no se tocan.

## Transiciones de estado
El dominio solo permite Evento PROGRAMADO a COMPLETADO o CANCELADO, y Recordatorio PENDIENTE a ENVIADO o CANCELADO. Los servicios convierten el error del dominio en `CambioDeEstadoNoPermitido`. `reprogramar_evento` rechaza los eventos que no estén programados (`EventoNoActivo`). El programador de avisos debe capturar `CambioDeEstadoNoPermitido` en `marcar_enviado`, por si el aviso se canceló entre listarlo y enviarlo.

## Estados de los objetivos

Los objetivos pasan de ACTIVO a PAUSADO o CANCELADO, y de PAUSADO a ACTIVO o
CANCELADO. Al llegar al 100 % de progreso pasan a COMPLETADO. Los objetivos
completados y cancelados se conservan y siempre se pueden consultar; no admiten
cambios de progreso ni transiciones normales. El dominio ofrece `restablecer()`
como corrección manual explícita, que vuelve a ACTIVO sin modificar el progreso.
`ServicioObjetivos` solo actualiza progreso de objetivos activos y traduce las
transiciones no permitidas a `CambioDeEstadoNoPermitido`.

## Conversaciones y mensajes

Las conversaciones se cierran y no se borran desde el servicio. Las conversaciones
cerradas pueden consultarse, pero no renombrarse ni recibir nuevos mensajes. Los
mensajes se añaden una sola vez: el servicio no ofrece operaciones para editarlos
o eliminarlos.

## Permisos por usuario
Toda operación sobre un evento o recordatorio concreto recibe el `usuario_id` de quien la pide
y solo actúa si el elemento es suyo. Si es de otro usuario, responde igual que si no existiera
(`EventoNoEncontrado` o `RecordatorioNoEncontrado`), para no revelar que existe.
`marcar_enviado` y `vencidos` son operaciones internas del programador de avisos y no se
ofrecerán como herramientas del chatbot.
Las operaciones sobre objetivos siguen la misma regla y usan
`ObjetivoNoEncontrado` para objetivos inexistentes o ajenos.

## Errores
| Error | Cuándo |
|---|---|
| `UsuarioNoEncontrado` | El usuario no existe |
| `EventoNoEncontrado` | El evento no existe |
| `ConflictoDeHorario` | El evento choca con otro activo del mismo usuario |
| `RecordatorioNoEncontrado` | El recordatorio no existe |
| `RecordatorioEnElPasado` | La hora del aviso ya ha pasado |
| `EventoNoActivo` | El evento está cancelado o completado y no admite avisos ni cambios de hora |
| `CambioDeEstadoNoPermitido` | Cambio de estado que las reglas no permiten, por ejemplo cancelar un evento ya completado |
| `HabitoNoEncontrado` | El hábito no existe o es de otro usuario |
| `HabitoInactivo` | El hábito está desactivado y no admite registros |
| `RegistroNoEncontrado` | El registro no existe o no es del hábito indicado |
| `ObjetivoNoEncontrado` | El objetivo no existe o es de otro usuario |
| `ObjetivoNoActivo` | El objetivo no está activo y no admite cambios de progreso |
| `FechaLimiteEnElPasado` | La fecha límite indicada es anterior al día actual del usuario |
| `ConversacionNoEncontrada` | La conversación no existe o es de otro usuario |
| `ConversacionCerrada` | La conversación está cerrada y no admite cambios |
| `ErrorResolucionNombre` | El nombre no identifica una entidad única; se ofrecen candidatos |

Los datos mal formados (nombre vacío, zona inexistente, fechas sin zona) siguen
lanzando `pydantic.ValidationError` o `ValueError`.

## Ejemplo de uso

    with sesion_sqlite() as conexion:
        usuarios = RepositorioUsuariosSQLite(conexion)
        eventos = RepositorioEventosSQLite(conexion)
        agenda = ServicioAgenda(usuarios, eventos)
        agenda.crear_evento(usuario_id, "Gimnasio", comienza, termina)

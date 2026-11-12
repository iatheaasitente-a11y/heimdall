# Auditoría de Hugin

Se revisaron en modo de solo lectura los 32 módulos Python de `src/hugin/` y
los 36 archivos de pruebas Python de `tests/`. No se importó código de Hugin ni
se copiaron sus implementaciones. Los veredictos se refieren a ideas
portables, no autorizan trasladar código completo. Los módulos de más de 300
líneas se descartan como implementación.

Los veredictos aplican cinco criterios: cubrir un hueco real de Heimdall,
respetar sus capas y fronteras de importación, no añadir estado global,
dependencias ni claves, servir al asistente personal y poder portarse con
pruebas. Los elementos dudosos y las implementaciones extensas no se portan.

| Módulo | Qué hace | Veredicto | Motivo | Capa de destino |
|---|---|---|---|---|
| `__init__.py` | Presenta la biblioteca y su estructura. | descartar | No cubre un comportamiento del asistente. | — |
| `apuntes.py` | Registra actividades y objetivos diarios y genera informes. | descartar | Se solapa con hábitos y objetivos existentes. | — |
| `inquilino.py` | Aísla capacidades y datos por carpeta o inquilino. | descartar | Heimdall ya separa los datos por usuario con otra arquitectura. | — |
| `motores.py` | Selecciona motores y modelos por configuración de entorno. | descartar | Incluye proveedores y configuración ya cubiertos por `app/llm`. | — |
| `guardado/__init__.py` | Presenta el paquete de almacenamiento. | descartar | No aporta comportamiento reutilizable. | — |
| `guardado/ajustes.py` | Lee y modifica archivos de configuración y secretos. | descartar | No es una necesidad de estas fases y gestiona secretos. | — |
| `guardado/almacen.py` | Persiste datos JSON y aplica migraciones. | descartar | Heimdall usa repositorios SQLite. | — |
| `guardado/avisos.py` | Guarda y consulta avisos operativos. | descartar | Es infraestructura ligada al almacenamiento de Hugin. | — |
| `guardado/copias.py` | Copia, limpia y restaura archivos. | descartar | No corresponde al alcance y no tiene test dedicado. | — |
| `guardado/datos.py` | Resuelve rutas y migra carpetas por negocio. | descartar | La organización de datos no corresponde a Heimdall. | — |
| `guardado/postgres.py` | Persiste datos de negocio en PostgreSQL. | descartar | Supera 300 líneas y añade una dependencia fuera de alcance. | — |
| `guardado/sincronizar.py` | Sincroniza datos por medio de Git. | descartar | Requiere procesos externos y no cubre una necesidad actual. | — |
| `mente/__init__.py` | Presenta los componentes de interpretación. | descartar | Es documentación de paquete, no un comportamiento. | — |
| `mente/cerebro.py` | Interpreta mensajes y conversa con un LLM. | descartar | Supera 300 líneas y acopla proveedores y estado global. | — |
| `mente/conocimiento.py` | Responde sobre tarifas y conocimiento empresarial. | descartar | Supera 300 líneas y está orientado a negocios. | — |
| `mente/fechas.py` | Resuelve fechas y horas para reservas. | adaptar | La implementación supera 300 líneas; sus casos sobre fechas relativas y ambigüedad cubren un hueco, pero se reescriben como dominio puro con reloj y zona inyectados. | `app/domain/lenguaje_fechas.py` |
| `mente/memoria.py` | Recupera recuerdos sobre clientes y llamadas. | descartar | Supera 300 líneas y no representa memoria personal de Heimdall. | — |
| `mente/rag.py` | Busca documentos de negocio. | descartar | Supera 300 líneas, usa caché global y no corresponde al asistente personal. | — |
| `mente/recepcion.py` | Coordina reservas y atención telefónica. | descartar | Supera 300 líneas y pertenece a un canal y negocio distintos. | — |
| `negocio/__init__.py` | Presenta el paquete de negocio. | descartar | No aporta comportamiento reutilizable. | — |
| `negocio/agenda.py` | Calcula disponibilidad y reservas de un negocio. | descartar | Supera 300 líneas y su agenda no equivale a la agenda personal. | — |
| `negocio/frases.py` | Carga frases editables y sinónimos desde TOML. | adaptar | La implementación supera 300 líneas y mantiene caché global; solo se adapta la idea de evaluar frases etiquetadas, sin cargador ni caché. | `tests/datos/frases.csv` |
| `negocio/negocio.py` | Carga configuración y capacidades empresariales. | descartar | Su dominio es ajeno al asistente personal. | — |
| `personal/__init__.py` | Separa interpretación personal de reservas. | adaptar | La separación de intenciones evita mezclar dominios; se expresa con las capas existentes. | `app/agents` |
| `personal/citas.py` | Gestiona citas personales. | descartar | Heimdall ya ofrece agenda y repositorios para eventos. | — |
| `personal/conversar.py` | Contesta sobre datos personales con un LLM. | descartar | Depende de proveedores y credenciales, y duplica `app/llm`. | — |
| `personal/diario.py` | Guarda y lee un diario Markdown. | descartar | Introduce una función de producto no incluida en estas fases. | — |
| `personal/entender.py` | Clasifica intenciones personales. | descartar | Supera 300 líneas y acopla LLM, claves y cliente global. | — |
| `personal/fechas.py` | Interpreta expresiones de fecha personales. | adaptar | La implementación supera 300 líneas; se adaptan requisitos y casos de prueba, no su código. | `app/domain/lenguaje_fechas.py` |
| `personal/habitos.py` | Registra hábitos diarios. | descartar | Heimdall ya dispone de servicio, repositorio y herramientas de hábitos. | — |
| `personal/recordatorios.py` | Selecciona citas próximas aún no avisadas. | descartar | Heimdall ya tiene recordatorios y el módulo depende de citas de Hugin. | — |
| `personal/tareas.py` | Gestiona tareas, estados, fechas y aplazamientos. | dudoso | Es personal y tiene pruebas, pero Heimdall no define una entidad de tareas ni esta solicitud contempla añadirla. No se implementa. | — |

## Revisión de pruebas

Se revisaron los archivos de pruebas Python de Hugin para identificar cobertura
de privacidad, límites de importación, aislamiento, clasificación, fechas y
frases. Los casos útiles se expresan como pruebas propias de Heimdall; no se
importan helpers ni se copian conjuntos de frases. Las pruebas específicas de
la estructura interna de Hugin se descartan.

Las ideas de fechas, reglas y banco de frases se implementan únicamente en sus
fases previstas, con pruebas sobre las interfaces de Heimdall. El resto de los
módulos no supera uno o más de los criterios de hueco funcional, arquitectura,
dependencias, enfoque personal y portabilidad verificable.

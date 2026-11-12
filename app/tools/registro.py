"""Catálogo de herramientas y composición de las herramientas iniciales."""

from app.services.agenda import ServicioAgenda
from app.services.habitos import ServicioHabitos
from app.services.objetivos import ServicioObjetivos
from app.services.recordatorios import ServicioRecordatorios
from app.services.usuarios import ServicioUsuarios
from app.tools.agenda import herramientas_agenda
from app.tools.base import Herramienta
from app.tools.habitos import herramientas_habitos
from app.tools.objetivos import herramientas_objetivos
from app.tools.recordatorios import herramientas_recordatorios
from app.tools.resumen import herramienta_resumen_del_dia


class RegistroHerramientas:
    """Catálogo de herramientas indexado por nombre."""

    def __init__(self) -> None:
        """Crea un catálogo vacío."""
        self._herramientas: dict[str, Herramienta] = {}

    def registrar(self, herramienta: Herramienta) -> None:
        """Añade una herramienta al catálogo.

        Raises:
            ValueError: Si ya existe una herramienta con el mismo nombre.
        """
        if herramienta.nombre in self._herramientas:
            raise ValueError(f"Ya existe la herramienta «{herramienta.nombre}».")
        self._herramientas[herramienta.nombre] = herramienta

    def obtener(self, nombre: str) -> Herramienta:
        """Devuelve una herramienta registrada.

        Raises:
            KeyError: Si no hay una herramienta con ese nombre.
        """
        try:
            return self._herramientas[nombre]
        except KeyError as error:
            raise KeyError(f"No existe la herramienta «{nombre}».") from error

    def listar(self) -> list[Herramienta]:
        """Devuelve las herramientas registradas en orden de alta."""
        return list(self._herramientas.values())


def registrar_herramientas(
    registro: RegistroHerramientas,
    usuarios: ServicioUsuarios,
    agenda: ServicioAgenda,
    habitos: ServicioHabitos,
    objetivos: ServicioObjetivos,
    recordatorios: ServicioRecordatorios,
) -> RegistroHerramientas:
    """Registra las herramientas iniciales sobre servicios ya compuestos."""
    herramientas = [
        *herramientas_agenda(agenda),
        *herramientas_habitos(habitos),
        *herramientas_objetivos(objetivos),
        *herramientas_recordatorios(recordatorios),
        herramienta_resumen_del_dia(usuarios, agenda, habitos, recordatorios),
    ]
    for herramienta in herramientas:
        registro.registrar(herramienta)
    return registro

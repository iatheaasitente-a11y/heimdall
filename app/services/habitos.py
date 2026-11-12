"""Casos de uso de los hábitos: crearlos, anotar su progreso y consultar su racha."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from app.domain.habit import FrecuenciaHabito, Habito, RegistroHabito
from app.domain.relations import racha_diaria, total_del_dia
from app.domain.user import Usuario
from app.repositories.interfaces import (
    RepositorioHabitos,
    RepositorioRegistrosHabito,
    RepositorioUsuarios,
)
from app.schemas.habit import HabitoSchema, RegistroHabitoSchema
from app.services.errores import (
    HabitoInactivo,
    HabitoNoEncontrado,
    RegistroNoEncontrado,
    UsuarioNoEncontrado,
)


class ServicioHabitos:
    """Gestión de los hábitos de un usuario y de sus registros de progreso.

    Recibe un reloj (una función que devuelve la hora actual con zona horaria)
    para poder fijar la hora en las pruebas. No hace ``commit``: de eso se
    encarga quien abre la conexión.

    Las operaciones que actúan sobre un hábito concreto reciben el ``usuario_id``
    de quien las pide y solo actúan si el hábito es suyo; si es de otro usuario,
    responden igual que si no existiera. Los días se calculan siempre en la zona
    horaria del usuario.
    """

    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        habitos: RepositorioHabitos,
        registros: RepositorioRegistrosHabito,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        """Crea el servicio; si no se indica reloj, usa la hora actual en UTC."""
        self._usuarios = usuarios
        self._habitos = habitos
        self._registros = registros
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def crear_habito(
        self,
        usuario_id: UUID,
        nombre: str,
        frecuencia: FrecuenciaHabito | str = FrecuenciaHabito.DIARIA,
        objetivo: float = 1.0,
        unidad: str = "veces",
        descripcion: str | None = None,
    ) -> Habito:
        """Crea y guarda un hábito nuevo del usuario.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
            ValueError: Si la frecuencia no existe o ``objetivo`` no es mayor que cero.
            pydantic.ValidationError: Si el nombre está vacío.
        """
        self._exigir_usuario(usuario_id)
        habito = Habito(
            usuario_id,
            nombre.strip(),
            FrecuenciaHabito(frecuencia),
            descripcion=(descripcion.strip() or None) if descripcion is not None else None,
            objetivo=objetivo,
            unidad=unidad.strip(),
        )
        HabitoSchema.model_validate(habito)
        self._habitos.guardar(habito)
        return habito

    def obtener_habito(self, usuario_id: UUID, habito_id: UUID) -> Habito:
        """Devuelve un hábito del usuario.

        Raises:
            HabitoNoEncontrado: Si no existe o es de otro usuario.
        """
        return self._obtener(usuario_id, habito_id)

    def listar_habitos(self, usuario_id: UUID, solo_activos: bool = False) -> list[Habito]:
        """Devuelve los hábitos del usuario ordenados por nombre.

        Raises:
            UsuarioNoEncontrado: Si el usuario no existe.
        """
        self._exigir_usuario(usuario_id)
        return self._habitos.listar_por_usuario(usuario_id, solo_activos=solo_activos)

    def desactivar_habito(self, usuario_id: UUID, habito_id: UUID) -> Habito:
        """Desactiva un hábito del usuario y guarda el cambio. Conserva sus registros.

        Raises:
            HabitoNoEncontrado: Si no existe o es de otro usuario.
        """
        habito = self._obtener(usuario_id, habito_id)
        habito.desactivar()
        self._habitos.guardar(habito)
        return habito

    def registrar_progreso(
        self,
        usuario_id: UUID,
        habito_id: UUID,
        valor: float,
        cuando: datetime | None = None,
        notas: str | None = None,
    ) -> RegistroHabito:
        """Anota cuánto se ha hecho de un hábito y guarda el registro.

        Si no se indica ``cuando``, se usa la hora del reloj. El registro queda
        marcado como ``completado`` si, sumado a lo ya anotado ese mismo día, se
        alcanza el objetivo del hábito. Esa marca es informativa: los cálculos
        usan ``valor``. En hábitos semanales o mensuales la marca también se
        calcula con el total del día.

        Raises:
            HabitoNoEncontrado: Si el hábito no existe o es de otro usuario.
            HabitoInactivo: Si el hábito está desactivado.
            pydantic.ValidationError: Si ``valor`` es negativo o ``cuando`` no
                lleva zona horaria.
        """
        habito = self._obtener(usuario_id, habito_id)
        if not habito.activo:
            raise HabitoInactivo(habito.nombre)
        zona = self._exigir_usuario(usuario_id).zona()
        registro = RegistroHabito(
            habito.id,
            valor,
            False,
            fecha=cuando if cuando is not None else self._reloj(),
            notas=(notas.strip() or None) if notas is not None else None,
        )
        RegistroHabitoSchema.model_validate(registro)
        dia = registro.fecha.astimezone(zona).date()
        acumulado = total_del_dia(habito, self._registros_del_dia(habito, dia, zona), dia, zona)
        registro.completado = habito.cumple(acumulado + valor)
        self._registros.guardar(registro)
        return registro

    def listar_registros(self, usuario_id: UUID, habito_id: UUID) -> list[RegistroHabito]:
        """Devuelve los registros de un hábito del usuario, del más antiguo al más reciente.

        Raises:
            HabitoNoEncontrado: Si el hábito no existe o es de otro usuario.
        """
        habito = self._obtener(usuario_id, habito_id)
        return self._registros.listar_por_habito(habito.id)

    def eliminar_registro(self, usuario_id: UUID, habito_id: UUID, registro_id: UUID) -> None:
        """Borra un registro de un hábito del usuario, por ejemplo si se anotó por error.

        Raises:
            HabitoNoEncontrado: Si el hábito no existe o es de otro usuario.
            RegistroNoEncontrado: Si el registro no existe o no es de ese hábito.
        """
        habito = self._obtener(usuario_id, habito_id)
        registro = self._registros.obtener(registro_id)
        if registro is None or registro.habito_id != habito.id:
            raise RegistroNoEncontrado(registro_id)
        self._registros.eliminar(registro_id)

    def progreso_del_dia(
        self, usuario_id: UUID, habito_id: UUID, dia: date | None = None
    ) -> float:
        """Devuelve la suma de lo anotado en un día; por defecto, hoy.

        El día se calcula en la zona horaria del usuario.

        Raises:
            HabitoNoEncontrado: Si el hábito no existe o es de otro usuario.
        """
        habito = self._obtener(usuario_id, habito_id)
        zona = self._exigir_usuario(usuario_id).zona()
        dia = dia if dia is not None else self._reloj().astimezone(zona).date()
        return total_del_dia(habito, self._registros_del_dia(habito, dia, zona), dia, zona)

    def racha(self, usuario_id: UUID, habito_id: UUID, hoy: date | None = None) -> int:
        """Cuenta los días seguidos en que se alcanzó el objetivo; por defecto, hasta hoy.

        Si hoy aún no se cumple, la cuenta empieza en ayer. Solo tiene sentido en
        hábitos diarios.

        Raises:
            HabitoNoEncontrado: Si el hábito no existe o es de otro usuario.
            ValueError: Si el hábito no es de frecuencia diaria.
        """
        habito = self._obtener(usuario_id, habito_id)
        if habito.frecuencia != FrecuenciaHabito.DIARIA:
            raise ValueError("La racha solo se calcula para hábitos de frecuencia diaria.")
        zona = self._exigir_usuario(usuario_id).zona()
        hoy = hoy if hoy is not None else self._reloj().astimezone(zona).date()
        registros = self._registros.listar_por_habito(habito.id)
        return racha_diaria(habito, registros, hoy, zona)

    def _registros_del_dia(self, habito: Habito, dia: date, zona) -> list[RegistroHabito]:
        """Devuelve los registros del hábito cuyo día, en esa zona, es ``dia``."""
        desde = datetime.combine(dia, time.min, tzinfo=zona)
        hasta = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=zona)
        return self._registros.listar_por_rango(habito.id, desde, hasta)

    def _obtener(self, usuario_id: UUID, habito_id: UUID) -> Habito:
        """Devuelve un hábito del usuario o lanza ``HabitoNoEncontrado``."""
        habito = self._habitos.obtener(habito_id)
        if habito is None or habito.usuario_id != usuario_id:
            raise HabitoNoEncontrado(habito_id)
        return habito

    def _exigir_usuario(self, usuario_id: UUID) -> Usuario:
        """Devuelve el usuario o lanza ``UsuarioNoEncontrado``."""
        usuario = self._usuarios.obtener(usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(usuario_id)
        return usuario

"""Interpretación pura de fechas y horas expresadas en español."""

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}
_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_NUMEROS = {
    "una": 1,
    "un": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
}
_FRANJAS = (
    (re.compile(r"\b(?:de la|por la|esta) manana\b"), "mañana"),
    (re.compile(r"\b(?:de la|por la|esta) tarde\b"), "tarde"),
    (re.compile(r"\b(?:de la|por la|esta) noche\b"), "noche"),
    (re.compile(r"\b(?:de la|por la) madrugada\b|\bmadrugada\b"), "madrugada"),
    (re.compile(r"\b(?:al|del) mediodia\b|\bmediodia\b"), "mediodía"),
)
_PATRON_HORA = re.compile(
    r"\b(?:a\s+las|a\s+la|las)\s+"
    r"(?P<hora>\d{1,2}(?::\d{2})?|una|un|uno|dos|tres|cuatro|cinco|"
    r"seis|siete|ocho|nueve|diez|once|doce)"
    r"(?:\s+y\s+(?P<fraccion>media|cuarto)|\s+menos\s+(?P<menos>cuarto))?"
    r"(?:\s*(?P<meridiano>am|pm))?\b"
)


@dataclass(frozen=True)
class HoraResuelta:
    """Hora interpretada y señal sobre si su franja está suficientemente acotada."""

    hora: time
    acotada: bool
    franja: str | None = None


@dataclass(frozen=True)
class FechaHoraResuelta:
    """Fecha, hora opcional y franja interpretadas desde un texto."""

    fecha: date
    hora: time | None
    hora_acotada: bool
    franja: str | None = None


def resolver_fecha(
    texto: str,
    ahora: datetime,
    permitir_pasado: bool = False,
) -> date | None:
    """Resuelve una fecha en la zona de ``ahora`` sin inferir datos ausentes.

    Raises:
        TypeError: Si ``texto`` no es texto o ``ahora`` no es un datetime.
        ValueError: Si ``ahora`` no lleva zona horaria.
    """
    _validar_ahora(texto, ahora)
    normalizado = _normalizar(texto)
    hoy = ahora.date()

    if re.search(r"\bpasado manana\b", normalizado):
        return hoy + timedelta(days=2)
    if re.search(r"\banteayer\b", normalizado):
        return hoy - timedelta(days=2) if permitir_pasado else None
    if re.search(r"\bayer\b", normalizado):
        return hoy - timedelta(days=1) if permitir_pasado else None
    if re.search(r"\bhoy\b|\besta (?:manana|tarde|noche)\b", normalizado):
        return hoy
    if re.search(r"\bmanana\b", _sin_manana_como_franja(normalizado)):
        return hoy + timedelta(days=1)

    fecha = _fecha_iso(normalizado)
    if fecha is not None:
        return fecha if fecha >= hoy else None

    fecha = _fecha_con_mes(normalizado, hoy)
    if fecha is not None:
        return fecha

    fecha = _fecha_sin_mes(normalizado, hoy)
    if fecha is not None:
        return fecha

    for dia, numero in _DIAS.items():
        if re.search(rf"\b{dia}\b", normalizado):
            if re.search(r"\bpasad[oa]\b", normalizado):
                return None
            diferencia = (numero - hoy.weekday()) % 7
            if re.search(rf"\bproxim[oa] {dia}\b", normalizado):
                diferencia = diferencia or 7
            return hoy + timedelta(days=diferencia)
    return None


def resolver_hora(texto: str) -> HoraResuelta | None:
    """Interpreta una hora; sin franja explícita, la marca como no acotada.

    Returns:
        Hora y franja, o ``None`` si el texto no contiene una hora interpretable.

    Raises:
        TypeError: Si ``texto`` no es texto.
    """
    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")
    normalizado = _normalizar(texto)
    coincidencia = _PATRON_HORA.search(normalizado)
    if coincidencia is None:
        return None

    hora, minuto = _partes_hora(coincidencia)
    franja = _ultima_franja(normalizado)
    meridiano = coincidencia.group("meridiano")
    acotada = franja is not None or meridiano is not None or hora > 12

    if meridiano == "pm" or (franja in {"tarde", "noche"} and 1 <= hora < 12):
        hora += 12
    elif meridiano == "am" or franja in {"mañana", "madrugada"}:
        if hora == 12:
            hora = 0
    elif franja == "noche" and hora == 12:
        hora = 0
    if franja == "mediodía":
        hora = 12
        minuto = 0
        acotada = True
    if hora > 23 or minuto > 59:
        return None
    return HoraResuelta(time(hora, minuto), acotada, franja)


def resolver_fecha_hora(
    texto: str,
    ahora: datetime,
    permitir_pasado: bool = False,
) -> FechaHoraResuelta | None:
    """Resuelve fecha y hora en la zona horaria de ``ahora``.

    La fecha es obligatoria; si no está expresada o no se puede resolver,
    devuelve ``None``. Una hora sin franja se conserva, pero queda marcada como
    no acotada para que el agente pueda pedir aclaración.

    Raises:
        TypeError: Si ``texto`` no es texto o ``ahora`` no es un datetime.
        ValueError: Si ``ahora`` no lleva zona horaria.
    """
    fecha = resolver_fecha(texto, ahora, permitir_pasado)
    if fecha is None:
        return None
    hora = resolver_hora(texto)
    resultado = FechaHoraResuelta(
        fecha,
        None if hora is None else hora.hora,
        False if hora is None else hora.acotada,
        None if hora is None else hora.franja,
    )
    if (
        hora is not None
        and hora.acotada
        and not permitir_pasado
        and datetime.combine(fecha, hora.hora, tzinfo=ahora.tzinfo) <= ahora
    ):
        return None
    return resultado


def decir_fecha(valor: date) -> str:
    """Expresa una fecha en español con día de semana y mes.

    Raises:
        TypeError: Si ``valor`` no es una fecha.
    """
    if not isinstance(valor, date):
        raise TypeError("El valor debe ser una fecha.")
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    meses = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    return f"{dias[valor.weekday()]}, {valor.day} de {meses[valor.month - 1]} de {valor.year}"


def decir_hora(valor: time) -> str:
    """Expresa una hora en palabras con una franja cuando se conoce.

    Raises:
        TypeError: Si ``valor`` no es una hora.
    """
    if not isinstance(valor, time):
        raise TypeError("El valor debe ser una hora.")
    hora = valor.hour % 12 or 12
    texto = f"las {_numero_palabras(hora)}"
    if valor.minute:
        texto += f" y {_numero_palabras(valor.minute)}"
    if 5 <= valor.hour < 12:
        texto += " de la mañana"
    elif 12 <= valor.hour < 19:
        texto += " de la tarde"
    elif valor.hour >= 19 or valor.hour < 5:
        texto += " de la noche"
    return texto


def decir_duracion(valor: timedelta) -> str:
    """Expresa una duración no negativa en horas, minutos y segundos.

    Raises:
        TypeError: Si ``valor`` no es una duración.
        ValueError: Si la duración es negativa.
    """
    if not isinstance(valor, timedelta):
        raise TypeError("El valor debe ser una duración.")
    if valor < timedelta(0):
        raise ValueError("La duración no puede ser negativa.")
    segundos = int(valor.total_seconds())
    partes = []
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    for cantidad, singular, plural in (
        (horas, "hora", "horas"),
        (minutos, "minuto", "minutos"),
        (segundos, "segundo", "segundos"),
    ):
        if cantidad:
            nombre = singular if cantidad == 1 else plural
            cantidad_texto = (
                "una" if cantidad == 1 and singular == "hora"
                else "un" if cantidad == 1
                else _numero_palabras(cantidad)
            )
            partes.append(f"{cantidad_texto} {nombre}")
    return " y ".join(partes) if partes else "cero segundos"


def _validar_ahora(texto: str, ahora: datetime) -> None:
    """Comprueba los tipos y la zona horaria de los datos de entrada."""
    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")
    if not isinstance(ahora, datetime):
        raise TypeError("La referencia debe ser un datetime.")
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("La referencia debe llevar zona horaria.")


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas, quita tildes y normaliza espacios."""
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    sin_tildes = "".join(
        caracter
        for caracter in descompuesto
        if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.split())


def _sin_manana_como_franja(texto: str) -> str:
    """Evita leer «por la mañana» como la fecha de mañana."""
    return re.sub(r"\b(?:por la|de la|esta) manana\b", "", texto)


def _fecha_iso(texto: str) -> date | None:
    """Extrae una fecha ISO sin corregir una fecha explícita pasada."""
    coincidencia = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", texto)
    if coincidencia is None:
        return None
    try:
        return date(*(int(parte) for parte in coincidencia.groups()))
    except ValueError:
        return None


def _fecha_con_mes(texto: str, hoy: date) -> date | None:
    """Resuelve día y mes, avanzando al año siguiente si la fecha ya pasó."""
    for mes, numero_mes in _MESES.items():
        coincidencia = re.search(
            rf"\b(?:el\s+)?(\d{{1,2}})(?:\s+de)?\s+{mes}\b",
            texto,
        )
        if coincidencia is None:
            continue
        dia = int(coincidencia.group(1))
        for anio in range(hoy.year, hoy.year + 9):
            try:
                fecha = date(anio, numero_mes, dia)
            except ValueError:
                continue
            if fecha >= hoy:
                return fecha
    return None


def _fecha_sin_mes(texto: str, hoy: date) -> date | None:
    """Resuelve «el día N» al siguiente mes que contenga ese día."""
    coincidencia = re.search(r"\bel\s+(\d{1,2})\b", texto)
    if coincidencia is None:
        return None
    dia = int(coincidencia.group(1))
    if not 1 <= dia <= 31:
        return None
    anio, mes = hoy.year, hoy.month
    for _ in range(12):
        if dia <= monthrange(anio, mes)[1]:
            fecha = date(anio, mes, dia)
            if fecha >= hoy:
                return fecha
        mes += 1
        if mes == 13:
            mes = 1
            anio += 1
    return None


def _partes_hora(coincidencia: re.Match[str]) -> tuple[int, int]:
    """Convierte la captura de hora y minutos."""
    texto_hora = coincidencia.group("hora")
    if ":" in texto_hora:
        hora_texto, minuto_texto = texto_hora.split(":")
        hora, minuto = int(hora_texto), int(minuto_texto)
    else:
        hora = int(texto_hora) if texto_hora.isdigit() else _NUMEROS.get(texto_hora, 0)
        minuto = 0
    if coincidencia.group("fraccion") == "media":
        minuto = 30
    elif coincidencia.group("fraccion") == "cuarto":
        minuto = 15
    elif coincidencia.group("menos"):
        minuto = 45
        hora = (hora - 1) % 24
    return hora, minuto


def _ultima_franja(texto: str) -> str | None:
    """Devuelve la franja temporal cuya mención aparece más tarde."""
    menciones = [
        (coincidencia.start(), nombre)
        for patron, nombre in _FRANJAS
        for coincidencia in patron.finditer(texto)
    ]
    return max(menciones, default=(0, None))[1]


def _numero_palabras(numero: int) -> str:
    """Convierte enteros frecuentes a palabras sin dependencias externas."""
    unidades = (
        "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
        "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
        "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
    )
    if 0 <= numero <= 20:
        return unidades[numero]
    if numero < 30:
        return f"veinti{unidades[numero - 20]}"
    decenas = {30: "treinta", 40: "cuarenta", 50: "cincuenta"}
    decena = numero // 10 * 10
    if decena in decenas and numero < decena + 10:
        return decenas[decena] if numero == decena else (
            f"{decenas[decena]} y {unidades[numero - decena]}"
        )
    return str(numero)

from typing import cast

import pytest

from app.llm.roles import (
    Catalogo,
    ModeloConfigurado,
    PoliticaRol,
    RolModelo,
    confianza_suficiente,
    normalizar_nombre_modelo,
)


@pytest.mark.parametrize(
    "rol,inferencia",
    [
        (RolModelo.TEXTO, 45),
        (RolModelo.ENRUTADOR, 15),
        (RolModelo.VISION, 60),
        (RolModelo.OCR, 60),
        (RolModelo.VOZ, 45),
    ],
)
def test_catalogo_asigna_plazos_aprobados_por_rol(rol, inferencia):
    configuracion = Catalogo({rol: "modelo-elegido"}).obtener(rol)

    assert configuracion == ModeloConfigurado(
        "modelo-elegido",
        PoliticaRol(150, 10, 60, inferencia, 0.70),
        rol,
    )


def test_catalogo_deja_apagados_los_roles_no_inyectados():
    catalogo = Catalogo({RolModelo.TEXTO: "modelo-elegido"})
    texto = catalogo.obtener(RolModelo.TEXTO)

    assert texto is not None
    assert texto.nombre == "modelo-elegido:latest"
    assert catalogo.obtener(RolModelo.OCR) is None


@pytest.mark.parametrize("nombre", ["", "  "])
def test_catalogo_rechaza_nombres_vacios(nombre):
    with pytest.raises(ValueError, match="no puede estar vacío"):
        Catalogo({RolModelo.TEXTO: nombre})


def test_catalogo_rechaza_clave_que_no_es_rol():
    with pytest.raises(TypeError, match="RolModelo"):
        Catalogo(cast(dict[RolModelo, str], {"texto": "modelo-elegido"}))


def test_catalogo_recorta_el_nombre_de_modelo_inyectado():
    configuracion = Catalogo({RolModelo.TEXTO: "  modelo-elegido  "}).obtener(
        RolModelo.TEXTO
    )

    assert configuracion is not None
    assert configuracion.nombre == "modelo-elegido:latest"


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        (" modelo ", "modelo:latest"),
        ("modelo:latest", "modelo:latest"),
        ("modelo:3b", "modelo:3b"),
        ("equipo/modelo", "equipo/modelo:latest"),
        ("equipo/modelo:3b", "equipo/modelo:3b"),
    ],
)
def test_normaliza_etiqueta_sin_alterar_etiquetas_existentes(entrada, esperado):
    assert normalizar_nombre_modelo(entrada) == esperado


def test_rechaza_etiqueta_de_modelo_vacia():
    with pytest.raises(ValueError, match="etiqueta"):
        normalizar_nombre_modelo("modelo:")


@pytest.mark.parametrize(
    "valores",
    [
        (0, 10, 60, 45, 0.70),
        (150, float("inf"), 60, 45, 0.70),
        (150, 10, 60, 45, float("nan")),
        (150, 10, 60, 45, 1.1),
    ],
)
def test_politica_rechaza_plazos_o_confianza_invalidos(valores):
    with pytest.raises(ValueError):
        PoliticaRol(*valores)


@pytest.mark.parametrize(
    "confianza",
    [
        None,
        "alta",
        True,
        float("nan"),
        float("inf"),
        -0.1,
        1.1,
        pytest.param(10**10000, id="integer-overflow"),
    ],
)
def test_confianza_invalida_se_considera_baja(confianza):
    assert confianza_suficiente(confianza, 0.70) is False


def test_confianza_igual_al_umbral_es_suficiente():
    assert confianza_suficiente(0.70, 0.70) is True

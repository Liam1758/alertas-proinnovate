import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://startup.proinnovate.gob.pe/concursos/"
ARCHIVO = "convocatorias.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def obtener_convocatorias():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
    }

    respuesta = requests.get(
        URL,
        headers=headers,
        timeout=30
    )

    respuesta.raise_for_status()

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    resultados = {}

    for enlace in soup.find_all("a", href=True):

        titulo = enlace.get_text(
            " ",
            strip=True
        )

        url = urljoin(
            URL,
            enlace["href"]
        )

        # Solo enlaces pertenecientes a convocatorias
        if (
            titulo
            and "/concursos/" in url
            and url != URL
            and not url.startswith("mailto:")
        ):
            resultados[url] = titulo

    return resultados


def cargar_anteriores():

    if not os.path.exists(ARCHIVO):
        return {}

    try:

        with open(
            ARCHIVO,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

            if isinstance(datos, dict):
                return datos

            return {}

    except Exception as error:

        print(
            f"Error leyendo {ARCHIVO}: {error}"
        )

        return {}


def guardar_convocatorias(convocatorias):

    with open(
        ARCHIVO,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            convocatorias,
            archivo,
            ensure_ascii=False,
            indent=2
        )


def enviar_mensaje_telegram(mensaje):

    if not BOT_TOKEN or not CHAT_ID:

        print(
            "Telegram no está configurado."
        )

        return

    endpoint = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    respuesta = requests.post(
        endpoint,
        data={
            "chat_id": CHAT_ID,
            "text": mensaje,
            "disable_web_page_preview": False
        },
        timeout=30
    )

    respuesta.raise_for_status()

    print(
        "Mensaje enviado correctamente a Telegram."
    )


def enviar_nueva_convocatoria(titulo, url):

    mensaje = (
        "🚨 NUEVA CONVOCATORIA PROINNÓVATE\n\n"
        f"📌 {titulo}\n\n"
        f"🔗 {url}"
    )

    enviar_mensaje_telegram(mensaje)


def enviar_cambio_convocatoria(
    titulo_anterior,
    titulo_nuevo,
    url
):

    mensaje = (
        "⚠️ CAMBIO DETECTADO EN PROINNÓVATE\n\n"
        "📌 Convocatoria actualizada\n\n"
        f"ANTES:\n{titulo_anterior}\n\n"
        f"AHORA:\n{titulo_nuevo}\n\n"
        f"🔗 {url}"
    )

    enviar_mensaje_telegram(mensaje)


def main():

    print(
        "================================="
    )

    print(
        "MONITOR PROINNÓVATE"
    )

    print(
        "================================="
    )

    actuales = obtener_convocatorias()

    anteriores = cargar_anteriores()

    print(
        f"Convocatorias encontradas: "
        f"{len(actuales)}"
    )

    # Seguridad:
    # Si por algún problema la web devuelve
    # cero convocatorias, NO sobrescribimos
    # el historial.
    if not actuales:

        print(
            "ADVERTENCIA: no se encontraron "
            "convocatorias."
        )

        print(
            "El historial NO será modificado."
        )

        return

    # Primera ejecución
    if not anteriores:

        print(
            "Primera ejecución."
        )

        print(
            "Creando historial inicial."
        )

        guardar_convocatorias(
            actuales
        )

        return

    # ---------------------------------
    # BUSCAR CONVOCATORIAS NUEVAS
    # ---------------------------------

    nuevas = {
        url: titulo
        for url, titulo in actuales.items()
        if url not in anteriores
    }

    if nuevas:

        print(
            f"Nuevas convocatorias: "
            f"{len(nuevas)}"
        )

        for url, titulo in nuevas.items():

            print(
                f"NUEVA: {titulo}"
            )

            enviar_nueva_convocatoria(
                titulo,
                url
            )

    else:

        print(
            "No hay nuevas convocatorias."
        )

    # ---------------------------------
    # BUSCAR CAMBIOS
    # ---------------------------------

    cambios = []

    for url, titulo_nuevo in actuales.items():

        if url in anteriores:

            titulo_anterior = anteriores[url]

            if (
                titulo_anterior.strip()
                != titulo_nuevo.strip()
            ):

                cambios.append(
                    (
                        url,
                        titulo_anterior,
                        titulo_nuevo
                    )
                )

    if cambios:

        print(
            f"Cambios detectados: "
            f"{len(cambios)}"
        )

        for (
            url,
            titulo_anterior,
            titulo_nuevo
        ) in cambios:

            print(
                f"CAMBIO: "
                f"{titulo_anterior} "
                f"-> {titulo_nuevo}"
            )

            enviar_cambio_convocatoria(
                titulo_anterior,
                titulo_nuevo,
                url
            )

    else:

        print(
            "No hay cambios en "
            "convocatorias existentes."
        )

    # ---------------------------------
    # ACTUALIZAR HISTORIAL
    # ---------------------------------

    guardar_convocatorias(
        actuales
    )

    print(
        "Historial actualizado."
    )

    print(
        "Monitor finalizado correctamente."
    )


if __name__ == "__main__":
    main()
    

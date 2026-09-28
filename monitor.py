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
        "User-Agent": "Mozilla/5.0"
    }

    respuesta = requests.get(URL, headers=headers, timeout=30)
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    resultados = {}

    for enlace in soup.find_all("a", href=True):
        titulo = enlace.get_text(" ", strip=True)
        url = urljoin(URL, enlace["href"])

        # Solo enlaces correspondientes a concursos
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
        with open(ARCHIVO, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except Exception:
        return {}


def guardar_convocatorias(convocatorias):
    with open(ARCHIVO, "w", encoding="utf-8") as archivo:
        json.dump(
            convocatorias,
            archivo,
            ensure_ascii=False,
            indent=2
        )


def enviar_telegram(titulo, url):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram todavía no está configurado.")
        return

    mensaje = (
        "🚨 NUEVA CONVOCATORIA PROINNÓVATE\n\n"
        f"📌 {titulo}\n\n"
        f"🔗 {url}"
    )

    endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    respuesta = requests.post(
        endpoint,
        data={
            "chat_id": CHAT_ID,
            "text": mensaje
        },
        timeout=30
    )

    respuesta.raise_for_status()


def main():
    actuales = obtener_convocatorias()
    anteriores = cargar_anteriores()

    print(f"Convocatorias encontradas: {len(actuales)}")

    # Primera ejecución:
    # guarda las convocatorias existentes sin bombardear Telegram.
    if not anteriores:
        print("Primera ejecución. Creando historial inicial.")
        guardar_convocatorias(actuales)
        return

    nuevas = {
        url: titulo
        for url, titulo in actuales.items()
        if url not in anteriores
    }

    if nuevas:
        print(f"Nuevas convocatorias: {len(nuevas)}")

        for url, titulo in nuevas.items():
            print(f"NUEVA: {titulo} - {url}")
            enviar_telegram(titulo, url)

    else:
        print("No hay nuevas convocatorias.")

    guardar_convocatorias(actuales)


if __name__ == "__main__":
    main()

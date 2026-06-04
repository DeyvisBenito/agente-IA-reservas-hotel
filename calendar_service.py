import json
import os
from datetime import datetime, timezone
from anthropic import Anthropic
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import COLLECTION, get_context

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
client = Anthropic()

def get_calendar_service():
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "documentos/credentials-google-calendar.json")
        credentials = service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials)

def normalize_cabin_name(name: str) -> str:
    return name.lower().strip()

def get_all_cabins() -> list:
    context = get_context(COLLECTION, "nombres de todas las cabañas refugios suites chalets tarifa", n_answer=10)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"Basándote en este texto del hotel, lista SOLO los nombres exactos de todas las cabañas, refugios, suites y chalets. Un nombre por línea, sin explicaciones ni texto adicional: {context}"
        }]
    )
    names = response.content[0].text.strip().split("\n")
    return [n.strip() for n in names if n.strip()]

def is_cabin_reserved(room: str, checkin: str, checkout: str) -> bool:
    try:
        service = get_calendar_service()
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

        checkin_dt = datetime.strptime(checkin, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        checkout_dt = datetime.strptime(checkout, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=checkin_dt.isoformat(),
            timeMax=checkout_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        normalized_room = normalize_cabin_name(room)
        return any(
            normalized_room in event.get("summary", "").lower()
            for event in events_result.get("items", [])
        )

    except Exception as e:
        print(f"Error al consultar Google Calendar: {e}")
        return False

def valid_availability(room: str, checkin: str, checkout: str) -> dict:
    reserved = is_cabin_reserved(room, checkin, checkout)
    return {
        "disponible": not reserved,
        "mensaje": "Disponible." if not reserved else "No disponible. La cabaña ya está reservada para esas fechas."
    }

def get_available_cabins(checkin: str, checkout: str) -> list:
    return [
        {"habitacion": cabin}
        for cabin in get_all_cabins()
        if not is_cabin_reserved(cabin, checkin, checkout)
    ]
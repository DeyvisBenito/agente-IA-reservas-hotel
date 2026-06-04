import requests
import os
from calendar_service import valid_availability as valid_availability_calendar, get_available_cabins

def send_answer(data):
    make_webhook_url = os.getenv('MAKE_WEBHOOK_URL')
    if not make_webhook_url:
        print('MAKE_WEBHOOK_URL no configurado en .env')
        return
    try:
        requests.post(make_webhook_url, json=data, timeout=10)
        print(f'Reserva enviada a Make: {data}')
    except Exception as e:
        print(f'Error enviando reserva a Make: {e}')

def cancel_reservation(reservation_code):
    make_cancelation_url = os.getenv('MAKE_WEBHOOK_CANCELAR')
    if not make_cancelation_url:
        print('MAKE_WEBHOOK_CANCELAR no configurado en .env')
        return {"cancelado": False}
    try:
        response = requests.post(make_cancelation_url, json={"codigo_reserva": reservation_code}, timeout=10)
        return response.json()
    except Exception as e:
        print(f'Error cancelando reserva en Make: {e}')
        return {"cancelado": False}

def check_availability(room, checkin, checkout):
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
    calendar_id = os.getenv('GOOGLE_CALENDAR_ID')

    if credentials_path and calendar_id:
        try:
            result = valid_availability_calendar(room, checkin, checkout)
            result["alternativas"] = [] if result["disponible"] else get_alternatives(checkin, checkout)
            return result
        except Exception as e:
            print(f'Error con Google Calendar: {e}')

    return {"disponible": True, "mensaje": "Disponible.", "alternativas": []}

def get_alternatives(checkin, checkout):
    try:
        return get_available_cabins(checkin, checkout)
    except Exception as e:
        print(f'Error obteniendo alternativas: {e}')
        return []
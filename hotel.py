import json
import re
import random
import string
from datetime import datetime
from anthropic import Anthropic
from config import SYSTEM_PROMPT_BASE, COLLECTION, get_context
from make_services import send_answer, check_availability, cancel_reservation

client = Anthropic()

conversations = {}

def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass
    return None

def generate_code_reservation():
    words = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=4))
    return f"NWL-{words}{numbers}"

def extract_rag_prices(room):
    context = get_context(COLLECTION, f"precio tarifa {room}")
    match = re.search(r'Q([\d,]+)/noche', context)
    if match:
        price_str = match.group(1).replace(",", "")
        return int(price_str)
    return 0

def calculate_nights_and_total(data):
    try:
        checkin_dt = datetime.strptime(data.get('checkin', ''), '%Y-%m-%d')
        checkout_dt = datetime.strptime(data.get('checkout', ''), '%Y-%m-%d')
        nights = (checkout_dt - checkin_dt).days
        data['noches'] = nights

        room = data.get('habitacion', '')
        price = extract_rag_prices(room)
        data['total'] = f"Q {price * nights:,.2f}"

        data['codigo_reserva'] = generate_code_reservation()
        data['fecha_creacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        print(f"Error calculando noches/total: {e}")
        data['noches'] = data.get('noches', 0)

    return data

def build_system_prompt(user_message):
    key_words = [
        "opciones", "cabañas", "habitaciones", "alojamiento", "tipos",
        "cuales", "qué tienen", "que tienen", "disponibles", "catalogo",
        "lista", "servicios", "experiencias", "actividades", "que ofrecen",
        "qué ofrecen", "paquetes", "tours", "preguntas", "frecuentes", "faq"
    ]
    is_question = any(p in user_message.lower() for p in key_words)

    n = 10 if is_question else 5
    context = get_context(COLLECTION, user_message, n_answer=n)
    return f"{SYSTEM_PROMPT_BASE}\n\nINFORMACIÓN RELEVANTE DEL ECO-LODGE:\n{context}"

def process_message(session_id, user_message):
    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({
        'role': 'user',
        'content': user_message
    })

    answer = call_claude(session_id, user_message)

    while True:
        json_data = extract_json(answer)

        if json_data and json_data.get('accion') == 'CHECK_AVAILABILITY':
            data = json_data.get('datos', {})

            results = check_availability(
                data.get('habitacion', ''),
                data.get('checkin', ''),
                data.get('checkout', '')
            )

            if results["disponible"]:
                message_result = (
                    f"SISTEMA: Disponibilidad verificada. "
                    f"{results['mensaje']} "
                    f"Procede con el resumen y confirmacion."
                )
            else:
                alternatives = results.get("alternativas", [])
                alt_text = "\n".join(
                    [f"- {a['habitacion']}" for a in alternatives]
                ) if alternatives else "No hay alternativas disponibles para esas fechas."

                message_result = (
                    f"SISTEMA: No hay disponibilidad para {data.get('habitacion')} "
                    f"en las fechas solicitadas. {results['mensaje']} "
                    f"Informa al cliente y sugiere estas alternativas:\n{alt_text}"
                )

            conversations[session_id].append({
                'role': 'user',
                'content': message_result
            })

            answer = call_claude(session_id, message_result)
            continue

        elif json_data and json_data.get('accion') == 'RESERVATION_CONFIRMED':
            data = json_data.get('datos', {})
            data = calculate_nights_and_total(data)
            send_answer(data)
            return {
                'respuesta': (
                    f"Reserva confirmada. Tu código de reserva es: {data['codigo_reserva']}. "
                    f"Guárdalo, lo necesitarás si deseas cancelar. "
                    f"Te enviaremos un correo de confirmación en breve."
                ),
                'reserva_confirmada': True,
                'datos': data
            }

        elif json_data and json_data.get('accion') == 'CANCEL_RESERVATION':
            data = json_data.get('datos', {})
            code = data.get('codigo_reserva', '')

            result = cancel_reservation(code)
            canceled = result.get('cancelado', False)

            message_result = (
                f"SISTEMA: Reserva {code} cancelada exitosamente. Informa al cliente."
                if canceled else
                f"SISTEMA: No se encontró la reserva con código {code} o ya fue cancelada. Informa al cliente."
            )

            conversations[session_id].append({
                'role': 'user',
                'content': message_result
            })

            answer = call_claude(session_id, message_result)
            continue

        else:
            break

    return {
        'respuesta': answer,
        'reserva_confirmada': False
    }

def call_claude(session_id, user_message=""):
    system_prompt = build_system_prompt(user_message)

    response = client.messages.create(
        model='claude-haiku-4-5',
        max_tokens=1024,
        system=system_prompt,
        messages=conversations[session_id]
    )

    answer = response.content[0].text

    conversations[session_id].append({
        'role': 'assistant',
        'content': answer
    })

    return answer
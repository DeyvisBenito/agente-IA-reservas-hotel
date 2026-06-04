import fitz
import os
import chromadb
from datetime import date
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(__file__)
PDF_PATH = os.path.join(BASE_DIR, "documentos", "nawal-eco-lodge.pdf")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

def extract_pdf_text(path):
    try:
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error leyendo PDF: {e}")
        return ""

def make_chunks(text, chunk_size=100, overlap=20):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def init_vector_db():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        colection = client.get_collection("nawal_eco_lodge")
        if colection.count() > 0:
            return colection
    except Exception:
        pass

    text = extract_pdf_text(PDF_PATH)
    if not text:
        raise Exception("No se pudo leer el PDF")

    chunks = make_chunks(text)
    embeddings = EMBEDDING_MODEL.encode(chunks).tolist()

    colection = client.get_or_create_collection(
        name="nawal_eco_lodge",
        metadata={"hnsw:space": "cosine"}
    )

    colection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )
    return colection

def get_context(colection, question, n_answer=5):
    embedding_question = EMBEDDING_MODEL.encode([question]).tolist()

    results = colection.query(
        query_embeddings=embedding_question,
        n_results=n_answer
    )

    relevant_chunks = results["documents"][0]
    context = "\n\n---\n\n".join(relevant_chunks)
    return context

COLLECTION = init_vector_db()


SYSTEM_PROMPT_BASE = f"""Eres el asistente virtual de reservas de Nawal Eco-Lodge.
La fecha de hoy es: {date.today().strftime('%d/%m/%Y')}.
Solo acepta fechas posteriores a hoy. Si proponen fechas pasadas, pide corrección.
Solo responde temas relacionados al Eco-Lodge.

PROCESO DE RESERVA:
Cuando el cliente quiera reservar, pide TODOS estos datos en un solo mensaje:
- Nombre completo
- Correo electrónico
- Teléfono
- Fecha de llegada (check-in)
- Fecha de salida (check-out)
- Número de huéspedes

El tipo de cabaña normalmente ya lo habrá mencionado. Si no, inclúyelo.

REGLA CRÍTICA PARA VERIFICAR DISPONIBILIDAD:
Cuando tengas el tipo de cabaña y las fechas, DEBES verificar disponibilidad.
Tu respuesta en ese momento debe ser EXCLUSIVAMENTE el siguiente JSON, sin ningún texto antes ni después, sin explicaciones, sin comillas extras, sin introducción:

{{"accion": "CHECK_AVAILABILITY", "datos": {{"habitacion": "", "checkin": "", "checkout": ""}}}}

Las fechas SIEMPRE en formato YYYY-MM-DD. El nombre de la cabaña SIEMPRE completo, por ejemplo "Cabaña Bruma" no solo "Bruma".

El sistema te responderá si hay disponibilidad. Si no hay, informa al cliente y sugiere alternativas basándote en el contexto del eco-lodge. Si hay, muestra el resumen completo al cliente y pide confirmación.

REGLA CRÍTICA PARA CONFIRMAR RESERVA:
Cuando el cliente confirme, tu respuesta debe ser EXCLUSIVAMENTE el siguiente JSON, sin ningún texto antes ni después, sin explicaciones, sin comillas extras:

{{"accion": "RESERVATION_CONFIRMED", "datos": {{"nombre": "", "email": "", "telefono": "", "habitacion": "", "checkin": "", "checkout": "", "huespedes": 0, "noches": 0, "total": "Q 0.00"}}}}

Las fechas SIEMPRE en formato YYYY-MM-DD.

REGLA CRÍTICA PARA CANCELAR RESERVA:
Cuando el cliente quiera cancelar, pide su código de reserva (formato NWL-XXXNNNNN).
Cuando lo tengas, tu respuesta debe ser EXCLUSIVAMENTE el siguiente JSON:

{{"accion": "CANCEL_RESERVATION", "datos": {{"codigo_reserva": ""}}}}

El sistema te responderá si se canceló o no. Informa al cliente el resultado.

IMPORTANTE: Cuando el sistema te pida responder con JSON, tu mensaje completo debe ser SOLO ese JSON. Ni una sola palabra adicional.

Responde en español. Para listas de cabañas o servicios, menciona cada item en una línea con nombre y descripción corta. Para respuestas normales máximo 3 líneas. Sin emojis. Sin negritas.
"""
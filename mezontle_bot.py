import os
import re
import httpx
from fastapi import FastAPI, Request

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_API   = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

KB = [
    {"id": 1, "titulo": "Carta Ánimas", "keywords": ["carta", "animas", "ánimas", "comunicado", "aviso"], "respuesta": "Aquí está la Carta Ánimas:", "link": "https://drive.google.com/file/d/1dwMzRG18IbSOVeZ3IjHTkGpQHco1F2u-/view?usp=drive_link"},
    {"id": 2, "titulo": "Mapeo Conjunto Sábado", "keywords": ["mapeo", "sabado", "sábado", "conjunto sabado", "proceso sabado"], "respuesta": "Aquí está el Mapeo Conjunto del Sábado:", "link": "https://docs.google.com/document/d/1C784OFifp_yiw2r2tASxLWXy2DD_CooR/edit?usp=sharing"},
    {"id": 3, "titulo": "Mapeo Conjunto Domingo", "keywords": ["mapeo", "domingo", "conjunto domingo", "proceso domingo"], "respuesta": "Aquí está el Mapeo Conjunto del Domingo:", "link": "https://docs.google.com/document/d/1vtRpBX_oaPmdnPEr37B1gew0ClQde9ZD/edit?usp=sharing"},
    {"id": 4, "titulo": "Directorio", "keywords": ["directorio", "contactos", "telefono", "telefonos", "numeros", "quien llamo"], "respuesta": "Aquí está el Directorio con los contactos:", "link": "https://docs.google.com/spreadsheets/d/11XfIxxRkUw59SKEqSyewYrhEr1pBvFMl/edit?usp=sharing"},
    {"id": 5, "titulo": "Lista de Correos para Envío de RDC y Bitácora", "keywords": ["correo", "correos", "email", "rdc", "bitacora correo", "envio", "a quien envio"], "respuesta": "Aquí está la Lista de Correos para envío de RDC y Bitácora:", "link": "https://docs.google.com/document/d/1bc6OlemhFaPAoKj5wd-ckQ-ataTLAjIM/edit?usp=sharing"},
    {"id": 6, "titulo": "Organigrama", "keywords": ["organigrama", "org", "estructura", "jerarquia", "jefe", "responsable", "areas", "puesto"], "respuesta": "Aquí está el Organigrama de Mezontle:", "link": "https://drive.google.com/file/d/1MfxSIGurmkJbl1hqKiZPTfwHVIQRc2N6/view?usp=sharing"},
    {"id": 7, "titulo": "Croquis Interior", "keywords": ["croquis", "mapa", "plano", "interior", "ubicacion", "donde esta", "como llego"], "respuesta": "Aquí tienes el Croquis del Interior:", "link": "https://drive.google.com/file/d/1BvA4G3BOQ4EB9SUODDdDRcgCkPwo3PAs/view?usp=sharing"}
]

def buscar_local(pregunta: str):
    p = pregunta.lower()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u")]:
        p = p.replace(a, b)
    mejor, max_score = None, 0
    for doc in KB:
        score = sum(len(kw) for kw in doc["keywords"] if kw in p)
        if score > max_score:
            max_score, mejor = score, doc
    return mejor if max_score > 3 else None

async def buscar_con_ia(pregunta: str):
    lista = "\n".join([f"ID {d['id']}: {d['titulo']}" for d in KB])
    prompt = f"Tengo estos documentos:\n{lista}\n\nEl usuario pregunta: \"{pregunta}\"\n\nResponde SOLO con el número ID del documento más relevante. Si ninguno aplica responde 0."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            data = r.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            texto = candidates[0]["content"]["parts"][0]["text"].strip()
            m = re.search(r"\d+", texto)
            if m:
                doc_id = int(m.group())
                return next((d for d in KB if d["id"] == doc_id), None)
    except Exception:
        return None
    return None

async def buscar(pregunta: str):
    resultado = buscar_local(pregunta)
    return resultado if resultado else await buscar_con_ia(pregunta)

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

async def send_typing(chat_id: int):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Asistente Mezontle activo 🟢"}

@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        if "message" not in data:
            return {"ok": True}
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()
        if not text:
            return {"ok": True}
        if text in ["/start", "/inicio"]:
            await send_message(chat_id, "👋 ¡Hola! Soy el <b>Asistente Mezontle</b>.\n\nHazme cualquier pregunta y buscaré el documento correcto para ti.\n\nPuedes preguntar sobre:\n📋 Mapeos · Directorio · Correos RDC\n🗺 Croquis · Organigrama · Carta Ánimas")
            return {"ok": True}
        await send_typing(chat_id)
        resultado = await buscar(text)
        if resultado:
            respuesta = f"{resultado['respuesta']}\n\n🔗 <a href=\"{resultado['link']}\">{resultado['titulo']}</a>"
        else:
            respuesta = "No encontré un documento específico sobre eso. 🤔\n\nIntenta preguntar sobre:\n📋 Mapeo sábado/domingo\n📞 Directorio o correos RDC\n🗺 Croquis u organigrama\n📄 Carta Ánimas"
        await send_message(chat_id, respuesta)
    except Exception as e:
        print(f"Error: {e}")
    return {"ok": True}

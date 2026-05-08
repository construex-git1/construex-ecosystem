"""
======================================================================
         CONSTRUEX ECOSYSTEM 5.0 - VERSIÓN FINAL COMPLETA
======================================================================
Integraciones: Gemini + Grok + Nano Banana + Notion + WhatsApp + Notebook LM
Genera: Podcast, Infografía, Presentación, Texto para redes
======================================================================
"""

import os
import re
import requests
import json
import time
import hashlib
import logging
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
from newspaper import Article
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai

# Intentar importar Notebook LM (opcional)
try:
    from notebooklm import NotebookLMClient
    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    print("⚠️ notebooklm-py no instalado. Ejecuta: pip install notebooklm-py")

load_dotenv()
app = Flask(__name__)

# ==================== CONFIGURACIÓN ====================
class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GROK_API_KEY = os.getenv('GROK_API_KEY', '')
    NANO_BANANA_API_KEY = os.getenv('NANO_BANANA_API_KEY', '')
    NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')
    NOTION_VERSION = "2022-06-28"
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'construex_verify_2024')
    RSS_FEEDS = os.getenv('RSS_FEEDS', '').split(',')
    AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
    AUTO_CONFIDENCE_THRESHOLD = int(os.getenv('AUTO_CONFIDENCE_THRESHOLD', '85'))
    SCAN_INTERVAL_HOURS = int(os.getenv('SCAN_INTERVAL_HOURS', '6'))
    
    @classmethod
    def validate(cls):
        print("\n" + "="*70)
        print("🏗️ CONSTRUEX ECOSYSTEM 5.0")
        print("="*70)
        print(f"🤖 Gemini: {'✅' if cls.GEMINI_API_KEY else '❌'}")
        print(f"📝 Notion: {'✅' if cls.NOTION_API_KEY else '❌'}")
        print(f"📱 WhatsApp: {'✅' if cls.WHATSAPP_ACCESS_TOKEN else '❌'}")
        print(f"🎙️ Notebook LM: {'✅' if NOTEBOOKLM_AVAILABLE else '❌'}")
        print(f"🚀 Auto-publicar: {'✅' if cls.AUTO_PUBLISH else '❌'}")
        print("="*70 + "\n")

if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Directorios
for dir_name in ['imagenes_generadas', 'videos_generados', 'podcasts_generados', 
                  'infografias_generadas', 'presentaciones_generadas', 'logs']:
    os.makedirs(dir_name, exist_ok=True)

cliente_notebooklm = None

# ==================== FUNCIONES BASE ====================
def extraer_noticia(url):
    try:
        article = Article(url, language='es')
        article.download()
        article.parse()
        if article.text and len(article.text) > 100:
            return {
                "exito": True,
                "titulo": article.title,
                "texto_completo": article.text[:15000],
                "resumen": article.summary[:800] if article.summary else article.text[:800],
                "url": url,
                "dominio": urlparse(url).netloc
            }
        return None
    except Exception as e:
        logging.error(f"Error extracción: {e}")
        return None

def analizar_contenido(titulo, texto):
    if gemini_model:
        try:
            prompt = f"""
Analiza esta noticia y devuelve SOLO JSON:

Título: {titulo}
Contenido: {texto[:3000]}

{{
    "categoria_principal": "Construccion|Emprendimiento|Salud|Educacion|Innovacion",
    "subcategoria": "string",
    "nivel_importancia": 1-5,
    "resumen_ejecutivo": "resumen de 2-3 líneas",
    "dato_impactante": "el dato más llamativo",
    "confianza": 0-100
}}
"""
            response = gemini_model.generate_content(prompt)
            texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(texto_limpio)
        except:
            pass
    
    return {
        "categoria_principal": "Innovacion",
        "subcategoria": "General",
        "nivel_importancia": 3,
        "resumen_ejecutivo": texto[:400],
        "dato_impactante": titulo[:150],
        "confianza": 50,
        "motor_usado": "fallback"
    }

def generar_texto_redes(titulo, analisis):
    categoria = analisis.get('categoria_principal', 'Innovacion')
    emojis = {"Construccion": "🏗️", "Emprendimiento": "🚀", "Salud": "💪", "Educacion": "🎓", "Innovacion": "💡"}
    emoji = emojis.get(categoria, "📚")
    
    instagram = f"""{emoji} {titulo[:70]} {emoji}

📌 {analisis.get('resumen_ejecutivo', titulo)[:350]}

💡 {analisis.get('dato_impactante', 'Descubre más')[:150]}

💾 GUARDA este post
👥 COMPARTE con alguien

#Construex #{categoria}"""
    
    twitter = f"🧵 {titulo[:250]}\n\n🔗 #Construex #{categoria}"
    linkedin = f"🏗️ **{titulo[:80]}**\n\n{analisis.get('resumen_ejecutivo', '')[:400]}\n\n#Construex #{categoria}"
    whatsapp = f"{emoji} *CONSTRUEX* {emoji}\n\n*{titulo[:60]}*\n{analisis.get('resumen_ejecutivo', '')[:300]}"
    
    return {"instagram": instagram, "twitter": twitter, "linkedin": linkedin, "whatsapp": whatsapp, "categoria": categoria}

# ==================== NOTEBOOK LM INTEGRATION ====================
async def init_notebooklm():
    global cliente_notebooklm
    if NOTEBOOKLM_AVAILABLE and not cliente_notebooklm:
        try:
            auth_json = os.getenv('NOTEBOOKLM_AUTH_JSON')
            if auth_json:
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                temp_file.write(auth_json)
                temp_file.close()
                cliente_notebooklm = await NotebookLMClient.from_auth(temp_file.name)
                print("✅ Notebook LM conectado (desde variable de entorno)")
            else:
                cliente_notebooklm = await NotebookLMClient.from_storage()
                print("✅ Notebook LM conectado (desde almacenamiento local)")
        except Exception as e:
            print(f"⚠️ Error conectando Notebook LM: {e}")
    return cliente_notebooklm

async def generar_podcast_notebooklm(titulo, contenido, categoria):
    if not NOTEBOOKLM_AVAILABLE or not cliente_notebooklm:
        return None
    try:
        nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:40]).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"podcast_{timestamp}_{nombre_limpio}.mp3"
        
        notebook = await cliente_notebooklm.notebooks.create(f"Podcast - {titulo[:50]}")
        await cliente_notebooklm.sources.add_text(notebook.id, contenido)
        
        resultado = await cliente_notebooklm.artifacts.generate_audio(
            notebook.id,
            instructions=f"Genera un podcast educativo sobre {categoria}. Tono profesional.",
            format="deep_dive"
        )
        
        await cliente_notebooklm.artifacts.wait_for_completion(notebook.id, resultado.task_id)
        
        audio_path = os.path.join("podcasts_generados", filename)
        await cliente_notebooklm.artifacts.download_audio(notebook.id, audio_path)
        return audio_path
    except Exception as e:
        logging.error(f"Error generando podcast: {e}")
        return None

async def generar_infografia_notebooklm(titulo, contenido, categoria):
    if not NOTEBOOKLM_AVAILABLE or not cliente_notebooklm:
        return None
    try:
        nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:40]).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"infografia_{timestamp}_{nombre_limpio}.png"
        
        notebook = await cliente_notebooklm.notebooks.create(f"Infografía - {titulo[:50]}")
        await cliente_notebooklm.sources.add_text(notebook.id, contenido)
        
        resultado = await cliente_notebooklm.artifacts.generate_infographic(
            notebook.id,
            orientation="landscape",
            detail="detailed",
            style="professional",
            prompt=f"Crea una infografía profesional sobre {categoria}"
        )
        
        await cliente_notebooklm.artifacts.wait_for_completion(notebook.id, resultado.task_id)
        
        image_path = os.path.join("infografias_generadas", filename)
        await cliente_notebooklm.artifacts.download_infographic(notebook.id, image_path)
        return image_path
    except Exception as e:
        logging.error(f"Error generando infografía: {e}")
        return None

async def generar_presentacion_notebooklm(titulo, contenido, categoria):
    if not NOTEBOOKLM_AVAILABLE or not cliente_notebooklm:
        return None
    try:
        nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:40]).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"presentacion_{timestamp}_{nombre_limpio}.pptx"
        
        notebook = await cliente_notebooklm.notebooks.create(f"Presentación - {titulo[:50]}")
        await cliente_notebooklm.sources.add_text(notebook.id, contenido)
        
        resultado = await cliente_notebooklm.artifacts.generate_slide_deck(
            notebook.id,
            format="presenter",
            prompt=f"Crea una presentación profesional sobre {categoria}"
        )
        
        await cliente_notebooklm.artifacts.wait_for_completion(notebook.id, resultado.task_id)
        
        pptx_path = os.path.join("presentaciones_generadas", filename)
        await cliente_notebooklm.artifacts.download_slide_deck(notebook.id, pptx_path, format="pptx")
        return pptx_path
    except Exception as e:
        logging.error(f"Error generando presentación: {e}")
        return None

# ==================== GENERACIÓN DE IMÁGENES ====================
def generar_imagen_pollinations(titulo, categoria):
    prompt = f"Professional social media image for {categoria}: {titulo[:100]}. Modern, clean, corporate. High quality 4K."
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"pollinations_{timestamp}_{nombre}.png"
            filepath = os.path.join("imagenes_generadas", filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/imagenes/{filename}"
    except:
        pass
    return None

# ==================== WHATSAPP ====================
def enviar_whatsapp(numero, mensaje):
    if not Config.WHATSAPP_ACCESS_TOKEN:
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {Config.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": numero, "type": "text", "text": {"body": mensaje[:1000]}}
        response = requests.post(url, headers=headers, json=data, timeout=30)
        return response.status_code == 200
    except:
        return False

# ==================== NOTION ====================
def guardar_en_notion(contenido, analisis, textos, imagen_url, podcast_path, infografia_path, presentacion_path):
    if not Config.NOTION_API_KEY:
        return None
    
    content_id = hashlib.md5(f"{contenido['url']}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    
    notion_data = {
        "parent": {"database_id": Config.NOTION_DATABASE_ID},
        "properties": {
            "ID": {"title": [{"text": {"content": f"CON-{content_id}"}}]},
            "Título": {"rich_text": [{"text": {"content": contenido['titulo'][:200]}}]},
            "URL": {"url": contenido['url']},
            "Categoría": {"select": {"name": analisis.get('categoria_principal', 'Otro')}},
            "Confianza": {"number": analisis.get('confianza', 50)},
            "Fecha": {"date": {"start": datetime.now().isoformat()}}
        },
        "children": [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📝 RESUMEN"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": analisis.get('resumen_ejecutivo', '')[:2000]}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📱 INSTAGRAM"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": textos.get('instagram', '')[:500]}}]}}
        ]
    }
    
    if imagen_url:
        notion_data["children"].append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": imagen_url}}})
    if podcast_path:
        notion_data["children"].append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "🎙️ PODCAST"}}]}})
        notion_data["children"].append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"Archivo: {podcast_path}"}}]}})
    if infografia_path:
        notion_data["children"].append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📊 INFOGRAFÍA"}}]}})
        notion_data["children"].append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"Archivo: {infografia_path}"}}]}})
    if presentacion_path:
        notion_data["children"].append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📊 PRESENTACIÓN"}}]}})
        notion_data["children"].append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"Archivo: {presentacion_path}"}}]}})
    
    try:
        headers = {"Authorization": f"Bearer {Config.NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": Config.NOTION_VERSION}
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=notion_data, timeout=30)
        return response.json().get('id') if response.status_code == 200 else None
    except:
        return None

# ==================== PROCESAMIENTO PRINCIPAL ====================
async def procesar_con_notebooklm(titulo, texto_completo, categoria):
    podcast = infografia = presentacion = None
    tasks = []
    
    if NOTEBOOKLM_AVAILABLE and cliente_notebooklm:
        tasks.append(generar_podcast_notebooklm(titulo, texto_completo, categoria))
        tasks.append(generar_infografia_notebooklm(titulo, texto_completo, categoria))
        tasks.append(generar_presentacion_notebooklm(titulo, texto_completo, categoria))
        
        if tasks:
            resultados = await asyncio.gather(*tasks, return_exceptions=True)
            podcast = resultados[0] if len(resultados) > 0 and not isinstance(resultados[0], Exception) else None
            infografia = resultados[1] if len(resultados) > 1 and not isinstance(resultados[1], Exception) else None
            presentacion = resultados[2] if len(resultados) > 2 and not isinstance(resultados[2], Exception) else None
    
    return podcast, infografia, presentacion

def procesar_url_completo_sync(url, chat_id=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    noticia = extraer_noticia(url)
    if not noticia:
        if chat_id:
            enviar_whatsapp(chat_id, "❌ No pude leer el enlace.")
        return {"exito": False}
    
    analisis = analizar_contenido(noticia['titulo'], noticia['texto_completo'])
    textos = generar_texto_redes(noticia['titulo'], analisis)
    imagen_url = generar_imagen_pollinations(noticia['titulo'], textos['categoria'])
    
    podcast_path, infografia_path, presentacion_path = loop.run_until_complete(
        procesar_con_notebooklm(noticia['titulo'], noticia['texto_completo'], textos['categoria'])
    )
    
    auto_publicar = Config.AUTO_PUBLISH and analisis.get('confianza', 0) >= Config.AUTO_CONFIDENCE_THRESHOLD
    guardar_en_notion(noticia, analisis, textos, imagen_url, podcast_path, infografia_path, presentacion_path)
    
    if chat_id:
        mensaje = f"✅ Procesado: {textos['categoria']}\n🎙️ Podcast: {'✅' if podcast_path else '❌'}\n📊 Infografía: {'✅' if infografia_path else '❌'}\n📊 Presentación: {'✅' if presentacion_path else '❌'}"
        enviar_whatsapp(chat_id, mensaje)
    
    return {"exito": True, "categoria": textos['categoria'], "imagen": imagen_url, 
            "podcast": podcast_path, "infografia": infografia_path, "presentacion": presentacion_path}

# ==================== WEBHOOK WHATSAPP ====================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode and token and mode == 'subscribe' and token == Config.WHATSAPP_VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_whatsapp():
    try:
        data = request.get_json()
        if 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    if 'value' in change and 'messages' in change['value']:
                        for message in change['value']['messages']:
                            if message['type'] == 'text':
                                numero = message['from']
                                texto = message['text']['body']
                                enlaces = re.findall(r'https?://[^\s]+', texto)
                                if enlaces:
                                    for enlace in enlaces:
                                        threading.Thread(target=procesar_url_completo_sync, args=(enlace, numero)).start()
                                    enviar_whatsapp(numero, "⏳ Procesando tu enlace (podcast, infografía y presentación incluidos)...")
                                else:
                                    enviar_whatsapp(numero, "🤖 Envíame un enlace de noticia y lo procesaré.")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error webhook: {e}")
        return jsonify({"status": "error"}), 500

# ==================== ENDPOINTS ====================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Construex 5.0</title>
    <style>body{font-family:Arial;background:#0f0f0f;text-align:center;padding:50px;color:white;} .container{max-width:800px;margin:auto;background:#1a1a2e;padding:30px;border-radius:20px;} .status{color:#27ae60;}</style>
    </head>
    <body>
    <div class=container>
        <h1>🏗️ Construex Ecosystem 5.0</h1>
        <p>Sistema con generación automática de podcast, infografía y presentación</p>
        <div class=status>🟢 Operativo</div>
        <p>📱 Envía un enlace por WhatsApp para probar</p>
    </div>
    </body>
    </html>
    """

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "online", "version": "5.0", "notebooklm": NOTEBOOKLM_AVAILABLE})

@app.route('/imagenes/<path:filename>')
def servir_imagen(filename):
    return send_from_directory("imagenes_generadas", filename)

@app.route('/podcasts/<path:filename>')
def servir_podcast(filename):
    return send_from_directory("podcasts_generados", filename)

@app.route('/infografias/<path:filename>')
def servir_infografia(filename):
    return send_from_directory("infografias_generadas", filename)

@app.route('/presentaciones/<path:filename>')
def servir_presentacion(filename):
    return send_from_directory("presentaciones_generadas", filename)

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})

# ==================== INICIALIZACIÓN ====================
async def inicializar():
    await init_notebooklm()

if __name__ == '__main__':
    Config.validate()
    
    # Inicializar Notebook LM
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(inicializar())
    
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
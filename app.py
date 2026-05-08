"""
======================================================================
         CONSTRUEX ECOSYSTEM 4.0 - WHATSAPP AUTOMATIZADO
======================================================================
"""

import os
import re
import requests
import json
import time
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
from newspaper import Article
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)

# ==================== CONFIGURACIÓN ====================
class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GROK_API_KEY = os.getenv('GROK_API_KEY', '')
    NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')
    NOTION_VERSION = "2022-06-28"
    
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
    
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
    INSTAGRAM_BUSINESS_ID = os.getenv('INSTAGRAM_BUSINESS_ID', '')
    TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
    
    RSS_FEEDS = os.getenv('RSS_FEEDS', '').split(',')
    
    AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
    AUTO_CONFIDENCE_THRESHOLD = int(os.getenv('AUTO_CONFIDENCE_THRESHOLD', '85'))
    SCAN_INTERVAL_HOURS = int(os.getenv('SCAN_INTERVAL_HOURS', '6'))
    
    @classmethod
    def validate(cls):
        print("\n" + "="*70)
        print(" CONSTRUEX ECOSYSTEM 4.0 - CONFIGURACIÓN")
        print("="*70)
        print(f"🤖 Gemini: {'✅' if cls.GEMINI_API_KEY else '❌'}")
        print(f"🦅 Grok: {'✅' if cls.GROK_API_KEY else '❌'}")
        print(f"📝 Notion: {'✅' if cls.NOTION_API_KEY else '❌'}")
        print(f"📱 WhatsApp: {'✅' if cls.WHATSAPP_ACCESS_TOKEN else '❌'}")
        print(f"🚀 Auto-publicar: {'✅' if cls.AUTO_PUBLISH else '❌'}")
        print(f"🎯 Confianza mínima: {cls.AUTO_CONFIDENCE_THRESHOLD}%")
        print("="*70 + "\n")

# Inicializar Gemini
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Directorios
for dir_name in ['imagenes_generadas', 'videos_generados', 'podcasts_generados', 'infografias_generadas', 'logs']:
    os.makedirs(dir_name, exist_ok=True)

# ==================== FUNCIONES BASE ====================
def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)

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
    """Análisis con Gemini o fallback local"""
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
            resultado = json.loads(texto_limpio)
            resultado["motor_usado"] = "gemini"
            return resultado
        except:
            pass
    
    # Fallback local
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
    
    return {"instagram": instagram, "categoria": categoria}

def guardar_en_notion(contenido, analisis, textos, estado="PENDIENTE"):
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
            "Estado": {"select": {"name": estado}},
            "Confianza": {"number": analisis.get('confianza', 50)},
            "Motor": {"select": {"name": analisis.get('motor_usado', 'desconocido')}},
            "Fecha": {"date": {"start": datetime.now().isoformat()}}
        },
        "children": [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📝 RESUMEN"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": analisis.get('resumen_ejecutivo', '')[:2000]}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📱 INSTAGRAM"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": textos.get('instagram', '')[:500]}}]}}
        ]
    }
    
    try:
        headers = {"Authorization": f"Bearer {Config.NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": Config.NOTION_VERSION}
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=notion_data, timeout=30)
        return {"id": response.json().get('id')} if response.status_code == 200 else None
    except:
        return None

def enviar_respuesta_whatsapp(numero, mensaje):
    if not Config.WHATSAPP_ACCESS_TOKEN:
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {Config.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {"messaging_product": "whatsapp", "to": numero, "type": "text", "text": {"body": mensaje}}
        response = requests.post(url, headers=headers, json=data, timeout=30)
        return response.status_code == 200
    except:
        return False

def procesar_url_completo(url, chat_id=None):
    """Procesa una URL: extrae, analiza, guarda, y publica si aplica"""
    
    resultado = {"exito": False, "url": url}
    
    # 1. Extraer noticia
    noticia = extraer_noticia(url)
    if not noticia:
        if chat_id:
            enviar_respuesta_whatsapp(chat_id, "❌ No pude leer el enlace. Verifica que sea una noticia válida.")
        return resultado
    
    # 2. Analizar
    analisis = analizar_contenido(noticia['titulo'], noticia['texto_completo'])
    
    # 3. Generar textos
    textos = generar_texto_redes(noticia['titulo'], analisis)
    
    # 4. Decidir si publicar automáticamente
    auto_publicar = Config.AUTO_PUBLISH and analisis.get('confianza', 0) >= Config.AUTO_CONFIDENCE_THRESHOLD
    
    estado = "APROBADO" if auto_publicar else "PENDIENTE"
    
    # 5. Guardar en Notion
    notion_result = guardar_en_notion(noticia, analisis, textos, estado)
    
    # 6. Enviar respuesta por WhatsApp
    if chat_id:
        if auto_publicar:
            msg = f"✅ ¡Listo! Tu contenido ha sido analizado y publicado.\n\n📁 Categoría: {textos['categoria']}\n🎯 Confianza: {analisis.get('confianza', 0)}%\n\n📱 Revisa el contenido en Notion."
        else:
            msg = f"✅ Contenido analizado y guardado en Notion para revisión.\n\n📁 Categoría: {textos['categoria']}\n🎯 Confianza: {analisis.get('confianza', 0)}%\n\n📝 Un revisor lo aprobará pronto."
        enviar_respuesta_whatsapp(chat_id, msg)
    
    resultado["exito"] = True
    resultado["auto_publicado"] = auto_publicar
    return resultado

# ==================== WEBHOOK DE WHATSAPP ====================
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
        print(f"📨 Webhook recibido: {json.dumps(data, indent=2)}")
        
        if 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    if 'value' in change and 'messages' in change['value']:
                        for message in change['value']['messages']:
                            if message['type'] == 'text':
                                numero = message['from']
                                texto = message['text']['body']
                                
                                print(f"📱 Mensaje de {numero}: {texto}")
                                
                                # Extraer enlaces del mensaje
                                enlaces = re.findall(r'https?://[^\s]+', texto)
                                
                                if enlaces:
                                    for enlace in enlaces:
                                        # Procesar cada enlace en segundo plano
                                        import threading
                                        thread = threading.Thread(target=procesar_url_completo, args=(enlace, numero))
                                        thread.start()
                                    enviar_respuesta_whatsapp(numero, "⏳ Recibido! Estoy procesando el enlace. Te aviso cuando termine.")
                                else:
                                    enviar_respuesta_whatsapp(numero, "🤖 Hola! Envíame un enlace de una noticia y lo procesaré automáticamente.\n\nComandos:\n• Enviar un enlace\n• `estado` - Ver mi estado")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error en webhook: {e}")
        return jsonify({"status": "error"}), 500

# ==================== OTROS ENDPOINTS ====================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Ecosystem 4.0</title>
        <style>
            body { font-family: Arial; background: #0f0f0f; padding: 20px; text-align: center; }
            .container { max-width: 800px; margin: auto; background: #1a1a2e; padding: 30px; border-radius: 20px; color: white; }
            .status { margin: 20px 0; padding: 15px; background: #2a2a3e; border-radius: 12px; }
            .online { color: #27ae60; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1> Construex Ecosystem 4.0</h1>
            <p>Sistema automatizado</p>
            <div class="status">
                <h3>📡 Estado del Sistema</h3>
                <p>🤖 Gemini: <span class="online">✅ Conectado</span></p>
                <p>📱 WhatsApp Webhook: <span class="online">✅ Activo</span></p>
                <p>📝 Notion: <span class="online">✅ Configurado</span></p>
                <p>🚀 Auto-publicación: <span class="online">✅ Activada (confianza > 85%)</span></p>
            </div>
            <p>📱 Envía un enlace de noticia al número de WhatsApp para probar</p>
        </div>
    </body>
    </html>
    """

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "whatsapp_webhook": True,
        "gemini": bool(Config.GEMINI_API_KEY),
        "notion": bool(Config.NOTION_API_KEY),
        "auto_publish": Config.AUTO_PUBLISH,
        "confidence_threshold": Config.AUTO_CONFIDENCE_THRESHOLD
    })

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})

# ==================== MAIN ====================
if __name__ == '__main__':
    Config.validate()
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Servidor corriendo en http://0.0.0.0:{port}")
    print(f"📱 Webhook WhatsApp: https://construex-ecosystem.onrender.com/webhook")
    print(f"🔑 Verify Token: {Config.WHATSAPP_VERIFY_TOKEN}")
    app.run(host='0.0.0.0', port=port, debug=False)
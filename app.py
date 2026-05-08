"""
======================================================================
         CONSTRUEX ECOSYSTEM 6.0 - VERSIÓN WHATSAPP
======================================================================
Incluye: Política de Privacidad, Términos de Servicio, Eliminación de Datos
"""

import os
import re
import requests
import json
import time
import hashlib
import logging
import threading
import sqlite3
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
    NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')
    NOTION_VERSION = "2022-06-28"
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'construex_verify_2026')
    RSS_FEEDS = os.getenv('RSS_FEEDS', '').split(',')
    AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
    AUTO_CONFIDENCE_THRESHOLD = int(os.getenv('AUTO_CONFIDENCE_THRESHOLD', '85'))
    SCAN_INTERVAL_HOURS = int(os.getenv('SCAN_INTERVAL_HOURS', '6'))
    NANO_BANANA_API_KEY = os.getenv('NANO_BANANA_API_KEY', '')
    
    @classmethod
    def validate(cls):
        print("\n" + "="*60)
        print("🏗️ CONSTRUEX 6.0 - WHATSAPP")
        print("="*60)
        print(f"🤖 Gemini: {'✅' if cls.GEMINI_API_KEY else '❌'}")
        print(f"📝 Notion: {'✅' if cls.NOTION_API_KEY else '❌'}")
        print(f"📱 WhatsApp: {'✅' if cls.WHATSAPP_ACCESS_TOKEN else '❌'}")
        print(f"🎨 Nano Banana: {'✅' if cls.NANO_BANANA_API_KEY else '❌'}")
        print(f"🚀 Auto-publicar: {'✅' if cls.AUTO_PUBLISH else '❌'}")
        print("="*60 + "\n")

if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Directorios
for dir_name in ['imagenes_generadas', 'logs', 'leads']:
    os.makedirs(dir_name, exist_ok=True)

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "construex.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contenido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            url TEXT,
            titulo TEXT,
            categoria TEXT,
            viralidad INTEGER,
            resumen TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            categoria TEXT,
            oportunidad TEXT,
            fecha DATETIME,
            estado TEXT DEFAULT 'nuevo'
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

init_db()

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
    "confianza": 0-100,
    "intencion_compra": "alta|media|baja",
    "viralidad": 1-10
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
        "intencion_compra": "baja",
        "viralidad": 5
    }

def generar_imagen(titulo, categoria):
    """Genera imagen usando Nano Banana o Pollinations"""
    
    prompt = f"Imagen profesional para {categoria}: {titulo[:100]}. Moderno, corporativo, alta calidad 4K."
    
    # Intentar con Nano Banana Pro
    if Config.NANO_BANANA_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {Config.NANO_BANANA_API_KEY}", "Content-Type": "application/json"}
            payload = {"prompt": prompt, "width": 1080, "height": 1080, "model": "nano-banana-pro"}
            response = requests.post("https://api.nanobanana.ai/v1/generate", headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                image_url = response.json().get("url")
                if image_url:
                    img_response = requests.get(image_url)
                    timestamp = str(int(time.time()))
                    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
                    filename = f"nanobanana_{timestamp}_{nombre}.png"
                    filepath = os.path.join("imagenes_generadas", filename)
                    with open(filepath, 'wb') as f:
                        f.write(img_response.content)
                    return f"/imagenes/{filename}"
        except Exception as e:
            print(f"Nano Banana falló: {e}")
    
    # Fallback a Pollinations
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

def guardar_en_notion(contenido, analisis, textos, imagen_url):
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
            "Viralidad": {"number": analisis.get('viralidad', 5)},
            "Fecha": {"date": {"start": datetime.now().isoformat()}}
        }
    }
    
    if imagen_url:
        notion_data["children"] = [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "🖼️ IMAGEN GENERADA"}}]}},
            {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": imagen_url}}}
        ]
    
    try:
        headers = {"Authorization": f"Bearer {Config.NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": Config.NOTION_VERSION}
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=notion_data, timeout=30)
        return response.json().get('id') if response.status_code == 200 else None
    except:
        return None

def detectar_oportunidad_lead(contenido, analisis):
    intencion = analisis.get('intencion_compra', 'baja')
    categoria = analisis.get('categoria_principal', '')
    
    if intencion in ['alta', 'media']:
        lead = {
            "fuente": contenido.get('url', 'whatsapp'),
            "categoria": categoria,
            "confianza": analisis.get('confianza', 50),
            "fecha": datetime.now().isoformat()
        }
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leads (nombre, categoria, oportunidad, fecha)
            VALUES (?, ?, ?, ?)
        ''', (f"Lead de {categoria}", categoria, json.dumps(lead), datetime.now()))
        conn.commit()
        conn.close()
        
        return lead
    return None

def procesar_url_completo_sync(url, chat_id=None):
    noticia = extraer_noticia(url)
    if not noticia:
        if chat_id:
            enviar_whatsapp(chat_id, "❌ No pude leer el enlace.")
        return {"exito": False}
    
    analisis = analizar_contenido(noticia['titulo'], noticia['texto_completo'])
    textos = generar_texto_redes(noticia['titulo'], analisis)
    imagen_url = generar_imagen(noticia['titulo'], textos['categoria'])
    lead = detectar_oportunidad_lead(noticia, analisis)
    
    guardar_en_notion(noticia, analisis, textos, imagen_url)
    
    if chat_id:
        mensaje = f"✅ Procesado: {textos['categoria']}\n🖼️ Imagen: {'✅' if imagen_url else '❌'}"
        if lead:
            mensaje += f"\n💰 Oportunidad detectada!"
        enviar_whatsapp(chat_id, mensaje)
    
    return {"exito": True, "categoria": textos['categoria'], "imagen": imagen_url, "lead": lead}

# ==================== ENDPOINTS LEGALES ====================
@app.route('/privacy')
def privacy_policy():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Política de Privacidad - Construex</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; color: #333; }
            h1, h2 { color: #2c3e50; }
            h1 { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            .date { color: #7f8c8d; margin-bottom: 30px; font-size: 14px; }
            .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }
        </style>
    </head>
    <body>
        <h1>Política de Privacidad de Construex</h1>
        <div class="date">Última actualización: 8 de mayo de 2026</div>
        
        <h2>1. Información que recopilamos</h2>
        <p>Construex recopila los mensajes de WhatsApp que los usuarios envían a nuestro número de negocio (+593 98 393 8439), incluyendo enlaces, textos y archivos multimedia que contengan. No recopilamos información personal identificable más allá de lo necesario para operar el servicio.</p>
        
        <h2>2. Cómo usamos tu información</h2>
        <p>La información recopilada se utiliza exclusivamente para:</p>
        <ul>
            <li>Procesar y analizar el contenido de los enlaces compartidos por los usuarios</li>
            <li>Generar resúmenes, imágenes y contenido educativo basado en el análisis</li>
            <li>Mejorar la calidad y precisión de nuestro servicio automatizado</li>
            <li>Identificar tendencias y oportunidades en los sectores de construcción, emprendimiento, salud y educación</li>
        </ul>
        
        <h2>3. Compartición de datos con terceros</h2>
        <p>Para operar nuestro servicio, utilizamos las siguientes plataformas de terceros, cada una con sus propias políticas de privacidad:</p>
        <ul>
            <li><strong>Google Gemini</strong> - Para el análisis de contenido y generación de resúmenes</li>
            <li><strong>Notion</strong> - Para el almacenamiento organizado de contenido procesado</li>
            <li><strong>WhatsApp Cloud API</strong> - Para la recepción y envío de mensajes</li>
            <li><strong>Render</strong> - Para el alojamiento del servidor y la base de datos</li>
        </ul>
        <p>No vendemos, alquilamos ni compartimos tu información personal con terceros para fines de marketing.</p>
        
        <h2>4. Almacenamiento y seguridad de los datos</h2>
        <p>Tus datos se almacenan de forma segura en servidores de Render con cifrado en tránsito (TLS). Implementamos medidas de seguridad estándar de la industria para proteger tu información contra acceso no autorizado, alteración o destrucción.</p>
        
        <h2>5. Tus derechos</h2>
        <p>Tienes derecho a:</p>
        <ul>
            <li>Solicitar acceso a tus datos personales</li>
            <li>Solicitar la corrección de datos incorrectos</li>
            <li>Solicitar la eliminación de tus datos</li>
            <li>Oponerte al procesamiento de tus datos</li>
        </ul>
        
        <h2>6. Contacto</h2>
        <p>Para cualquier pregunta sobre esta política de privacidad o sobre tus datos personales, contáctanos en: <strong>david.fierro@construex.com.mx</strong></p>
        
        <div class="footer">
            <p>Construex - Innovación en construcción y educación</p>
        </div>
    </body>
    </html>
    """


@app.route('/terms')
def terms_of_service():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Términos de Servicio - Construex</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; color: #333; }
            h1, h2 { color: #2c3e50; }
            h1 { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            .date { color: #7f8c8d; margin-bottom: 30px; font-size: 14px; }
            .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }
        </style>
    </head>
    <body>
        <h1>Términos de Servicio de Construex</h1>
        <div class="date">Última actualización: 8 de mayo de 2026</div>
        
        <h2>1. Aceptación de los términos</h2>
        <p>Al interactuar con nuestro servicio de WhatsApp (+593 98 393 8439) o utilizar nuestra plataforma, aceptas quedar vinculado por estos Términos de Servicio en su totalidad.</p>
        
        <h2>2. Descripción del servicio</h2>
        <p>Construex ofrece un servicio automatizado que:</p>
        <ul>
            <li>Recibe enlaces de noticias y contenido enviado por WhatsApp</li>
            <li>Analiza el contenido utilizando inteligencia artificial (Gemini)</li>
            <li>Genera resúmenes, imágenes y contenido educativo</li>
            <li>Clasifica el contenido en categorías relevantes</li>
            <li>Almacena el contenido procesado para análisis y mejora continua</li>
        </ul>
        
        <h2>3. Uso adecuado y conducta prohibida</h2>
        <p>Al utilizar nuestro servicio, te comprometes a:</p>
        <ul>
            <li>No enviar contenido ilegal, ofensivo, difamatorio, obsceno o amenazante</li>
            <li>No utilizar el servicio para acosar, abusar o dañar a terceros</li>
            <li>No intentar descompilar, realizar ingeniería inversa o extraer el código fuente del sistema</li>
            <li>No sobrecargar intencionalmente nuestra infraestructura</li>
            <li>No utilizar el servicio para actividades fraudulentas o engañosas</li>
        </ul>
        
        <h2>4. Propiedad intelectual</h2>
        <p>Todo el contenido generado por nuestro sistema (resúmenes, imágenes, análisis) es propiedad de Construex. El contenido original de los enlaces enviados pertenece a sus respectivos autores y fuentes.</p>
        
        <h2>5. Limitación de responsabilidad</h2>
        <p>Construex no se hace responsable por:</p>
        <ul>
            <li>La precisión, integridad o actualidad del contenido generado automáticamente, ya que proviene de algoritmos de IA y fuentes externas</li>
            <li>Interrupciones del servicio debido a mantenimiento, fallos técnicos o eventos fuera de nuestro control</li>
            <li>El mal uso del servicio por parte de terceros</li>
            <li>Decisiones tomadas basadas en el contenido generado por nuestro sistema</li>
        </ul>
        
        <h2>6. Modificaciones del servicio</h2>
        <p>Nos reservamos el derecho de modificar, suspender o discontinuar cualquier aspecto del servicio en cualquier momento, con o sin previo aviso.</p>
        
        <h2>7. Ley aplicable</h2>
        <p>Estos términos se rigen por las leyes de la República del Ecuador.</p>
        
        <h2>8. Contacto</h2>
        <p>Para preguntas sobre estos términos: <strong>david.fierro@construex.com.mx</strong></p>
        
        <div class="footer">
            <p>Construex - Innovación en construcción y educación</p>
        </div>
    </body>
    </html>
    """


@app.route('/data-deletion')
def data_deletion():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Eliminación de Datos - Construex</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; color: #333; }
            h1, h2 { color: #2c3e50; }
            h1 { border-bottom: 2px solid #e74c3c; padding-bottom: 10px; }
            .date { color: #7f8c8d; margin-bottom: 30px; font-size: 14px; }
            .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }
        </style>
    </head>
    <body>
        <h1>Solicitud de Eliminación de Datos</h1>
        <div class="date">Última actualización: 8 de mayo de 2026</div>
        
        <h2>¿Cómo solicitar la eliminación de tus datos?</h2>
        <p>Si deseas que eliminemos toda la información personal que hayamos recopilado sobre ti, puedes hacerlo siguiendo uno de estos métodos:</p>
        
        <h3>📱 Opción 1: Enviar un mensaje de WhatsApp</h3>
        <p>Envía un mensaje al número <strong>+593 98 393 8439</strong> con el siguiente texto:</p>
        <pre style="background: #f0f0f0; padding: 15px; border-radius: 8px;">ELIMINAR MIS DATOS</pre>
        <p>Incluye tu nombre y número de teléfono en el mensaje para que podamos identificar tu información correctamente.</p>
        
        <h3>✉️ Opción 2: Enviar un correo electrónico</h3>
        <p>Envía un correo a <strong>david.fierro@construex.com.mx</strong> con:</p>
        <ul>
            <li>Asunto: "Eliminación de datos - [tu número de teléfono]"</li>
            <li>Cuerpo: Tu nombre completo y número de teléfono asociado</li>
        </ul>
        
        <h2>¿Qué datos eliminamos?</h2>
        <p>Al procesar tu solicitud, eliminaremos:</p>
        <ul>
            <li>✅ Historial de mensajes enviados a nuestro servicio</li>
            <li>✅ Contenido generado a partir de tus interacciones</li>
            <li>✅ Cualquier información personal asociada a tu número de teléfono</li>
            <li>✅ Registros de actividad vinculados a tu cuenta</li>
        </ul>
        
        <h2>Plazo de procesamiento</h2>
        <p>Procesaremos tu solicitud en un plazo máximo de <strong>30 días</strong> desde su recepción. Te confirmaremos por el mismo medio cuando la eliminación esté completa.</p>
        
        <h2>Excepciones</h2>
        <p>Podemos retener cierta información si es requerida por ley o para fines legítimos de seguridad, como prevenir fraudes.</p>
        
        <h2>Contacto para dudas</h2>
        <p>Si tienes preguntas sobre el proceso de eliminación de datos: <strong>david.fierro@construex.com.mx</strong></p>
        
        <div class="footer">
            <p>Construex - Comprometidos con tu privacidad</p>
        </div>
    </body>
    </html>
    """


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
                                    enviar_whatsapp(numero, "⏳ Procesando tu enlace...")
                                else:
                                    enviar_whatsapp(numero, "🤖 Envíame un enlace de noticia y lo procesaré.")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error webhook: {e}")
        return jsonify({"status": "error"}), 500


# ==================== ENDPOINTS PRINCIPALES ====================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex 6.0 - Sistema de WhatsApp</title>
        <style>
            body { font-family: Arial; background: #0f0f0f; text-align: center; padding: 50px; color: white; }
            .container { max-width: 800px; margin: auto; background: #1a1a2e; padding: 30px; border-radius: 20px; }
            .status { color: #27ae60; }
            .links { margin-top: 20px; }
            .links a { color: #3498db; text-decoration: none; margin: 0 10px; }
            .links a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem 6.0</h1>
            <p>Sistema automatizado de procesamiento de noticias vía WhatsApp</p>
            <div class="status">🟢 Sistema Operativo</div>
            
            <div class="links">
                <h3>Enlaces legales:</h3>
                <a href="/privacy" target="_blank">📋 Política de Privacidad</a>
                <a href="/terms" target="_blank">📜 Términos de Servicio</a>
                <a href="/data-deletion" target="_blank">🗑️ Eliminación de Datos</a>
            </div>
            
            <p>📱 Envía un enlace de noticia al número +593 98 393 8439 para probar</p>
        </div>
    </body>
    </html>
    """

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "version": "6.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "privacy": "/privacy",
            "terms": "/terms",
            "data_deletion": "/data-deletion",
            "webhook": "/webhook"
        }
    })

@app.route('/imagenes/<path:filename>')
def servir_imagen(filename):
    return send_from_directory("imagenes_generadas", filename)

@app.route('/leads', methods=['GET'])
def listar_leads():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY fecha DESC LIMIT 50")
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"leads": leads})

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Construex 6.0 funcionando correctamente"})


# ==================== MAIN ====================
if __name__ == '__main__':
    Config.validate()
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Servidor Construex 6.0 corriendo en puerto {port}")
    print(f"📋 Política de Privacidad: https://construex-ecosystem.onrender.com/privacy")
    print(f"📜 Términos de Servicio: https://construex-ecosystem.onrender.com/terms")
    print(f"🗑️ Eliminación de Datos: https://construex-ecosystem.onrender.com/data-deletion")
    print(f"📱 Webhook: /webhook")
    app.run(host='0.0.0.0', port=port, debug=False)
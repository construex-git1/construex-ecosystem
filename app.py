"""
======================================================================
         CONSTRUEX ECOSYSTEM 4.0 - VERSIÓN FINAL COMPLETA
======================================================================
"""

import os
import re
import requests
import json
import time
import csv
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
    # APIs Principales
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GROK_API_KEY = os.getenv('GROK_API_KEY', '')  # Opcional
    
    # APIs de Imagen/Video (opcionales)
    NANO_BANANA_API_KEY = os.getenv('NANO_BANANA_API_KEY', '')
    HIGGSFIELD_API_KEY = os.getenv('HIGGSFIELD_API_KEY', '')
    
    # Notion
    NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')
    NOTION_VERSION = "2022-06-28"
    
    # WhatsApp
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
    
    # Redes Sociales (opcionales)
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
    INSTAGRAM_BUSINESS_ID = os.getenv('INSTAGRAM_BUSINESS_ID', '')
    TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
    
    # NotebookLM (webhook)
    NOTEBOOKLM_WEBHOOK_URL = os.getenv('NOTEBOOKLM_WEBHOOK_URL', '')
    
    # Fuentes RSS
    RSS_FEEDS = os.getenv('RSS_FEEDS', '').split(',')
    
    # Configuración general
    AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
    AUTO_SYNC_NOTION = os.getenv('AUTO_SYNC_NOTION', 'true').lower() == 'true'
    SCAN_INTERVAL_HOURS = int(os.getenv('SCAN_INTERVAL_HOURS', '6'))
    
    @classmethod
    def validate(cls):
        print("\n" + "="*70)
        print("🏗️  CONSTRUEX ECOSYSTEM 4.0 - VERIFICACIÓN")
        print("="*70)
        print(f"🤖 Gemini AI: {'✅' if cls.GEMINI_API_KEY else '❌'}")
        print(f"🦅 Grok AI: {'✅' if cls.GROK_API_KEY else '⏳ Pendiente (opcional)'}")
        print(f"🎨 Nano Banana: {'✅' if cls.NANO_BANANA_API_KEY else '⏳ Pendiente (opcional)'}")
        print(f"🎬 Higgsfield: {'✅' if cls.HIGGSFIELD_API_KEY else '⏳ Pendiente (opcional)'}")
        print(f"📝 Notion: {'✅' if cls.NOTION_API_KEY else '❌'}")
        print(f"📱 WhatsApp: {'✅' if cls.WHATSAPP_ACCESS_TOKEN else '❌'}")
        print(f"📸 Instagram: {'✅' if cls.INSTAGRAM_ACCESS_TOKEN else '⏳ Pendiente'}")
        print(f"🐦 Twitter: {'✅' if cls.TWITTER_BEARER_TOKEN else '⏳ Pendiente'}")
        print(f"📡 RSS Feeds: {len([f for f in cls.RSS_FEEDS if f])} fuentes")
        print(f"🔄 Auto-publicar: {'✅' if cls.AUTO_PUBLISH else '❌'}")
        print(f"📋 Auto-Notion: {'✅' if cls.AUTO_SYNC_NOTION else '❌'}")
        print(f"⏰ Escaneo cada: {cls.SCAN_INTERVAL_HOURS} horas")
        print("="*70 + "\n")

# Inicializar Gemini (principal)
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Directorios
for dir_name in ['imagenes_generadas', 'videos_generados', 'podcasts_generados', 'infografias_generadas', 'logs']:
    os.makedirs(dir_name, exist_ok=True)

# ==================== FUNCIONES BASE ====================
def extraer_noticia(url):
    """Extrae el artículo completo usando newspaper3k"""
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
                "fecha_publicacion": datetime.now().isoformat(),
                "autor": ", ".join(article.authors) if article.authors else "Construex",
                "imagen_principal": article.top_image,
                "keywords": article.keywords[:15] if article.keywords else [],
                "dominio": urlparse(url).netloc,
                "url": url
            }
        return None
    except Exception as e:
        logging.error(f"Error extracción: {e}")
        return None

def detectar_categoria_local(titulo, texto):
    """Clasificación local de respaldo (no depende de IA)"""
    texto_lower = f"{titulo} {texto[:500]}".lower()
    if any(p in texto_lower for p in ["construc", "obra", "edificio", "cemento", "arquitect"]):
        return "Construccion"
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "startup"]):
        return "Emprendimiento"
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud"
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion", "universidad"]):
        return "Educacion"
    elif any(p in texto_lower for p in ["tecnologia", "innovacion", "software", "app"]):
        return "Tecnologia"
    return "Innovacion"

# ==================== ANÁLISIS CON GEMINI + GROK (HÍBRIDO) ====================
def analizar_con_grok(titulo, texto):
    """Análisis con Grok (opcional, solo si hay API key)"""
    if not Config.GROK_API_KEY:
        return None
    
    try:
        headers = {"Authorization": f"Bearer {Config.GROK_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "grok-1.5",
            "messages": [{"role": "user", "content": f"Analiza esta noticia y devuelve JSON con categoria_principal, subcategoria, nivel_importancia(1-5), resumen_ejecutivo:\nTítulo: {titulo}\nTexto: {texto[:2000]}"}],
            "temperature": 0.3
        }
        response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            content = content.replace('```json', '').replace('```', '').strip()
            return json.loads(content)
        return None
    except Exception as e:
        logging.error(f"Error Grok: {e}")
        return None

def analizar_completo_con_gemini(titulo, texto):
    """Análisis con Gemini (principal)"""
    if not gemini_model:
        return None
    
    prompt = f"""
Eres un analista de contenido para Construex. Analiza esta noticia y devuelve SOLO JSON:

Título: {titulo}
Contenido: {texto[:3000]}

{{
    "categoria_principal": "Construccion|Emprendimiento|Salud|Educacion|Innovacion|DesarrolloPersonal|Sostenibilidad|Tecnologia",
    "subcategoria": "string específica",
    "nivel_importancia": 1-5,
    "temas_relacionados": ["tema1", "tema2", "tema3", "tema4", "tema5"],
    "etiquetas_sugeridas": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
    "resumen_ejecutivo": "resumen de 2-3 líneas",
    "dato_impactante": "el dato más llamativo",
    "aplicacion_practica": "cómo aplicar esta información"
}}
"""
    try:
        response = gemini_model.generate_content(prompt)
        texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpio)
    except Exception as e:
        logging.error(f"Error Gemini: {e}")
        return None

def analizar_contenido(titulo, texto):
    """Analiza usando Gemini primero, luego Grok como respaldo, luego local"""
    
    # Intento 1: Gemini
    resultado = analizar_completo_con_gemini(titulo, texto)
    if resultado:
        resultado["motor_usado"] = "gemini"
        return resultado
    
    # Intento 2: Grok (si está disponible)
    if Config.GROK_API_KEY:
        resultado = analizar_con_grok(titulo, texto)
        if resultado:
            resultado["motor_usado"] = "grok"
            return resultado
    
    # Intento 3: Fallback local
    categoria_local = detectar_categoria_local(titulo, texto)
    return {
        "categoria_principal": categoria_local,
        "subcategoria": "General",
        "nivel_importancia": 3,
        "temas_relacionados": [categoria_local, "noticias", "actualidad"],
        "etiquetas_sugeridas": [categoria_local.lower(), "construex", "noticias", "informacion", "actualidad"],
        "resumen_ejecutivo": texto[:400],
        "dato_impactante": titulo[:150],
        "aplicacion_practica": "Revisa el artículo original para más detalles",
        "motor_usado": "fallback_local"
    }

# ==================== GENERACIÓN DE IMÁGENES (HÍBRIDO) ====================
def generar_imagen_con_nano_banana(prompt):
    """Genera imagen con Nano Banana (opcional)"""
    if not Config.NANO_BANANA_API_KEY:
        return None
    try:
        headers = {"Authorization": f"Bearer {Config.NANO_BANANA_API_KEY}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "width": 1080, "height": 1080}
        response = requests.post("https://api.nanobanana.ai/v1/generate", headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get('url')
        return None
    except Exception as e:
        logging.error(f"Error Nano Banana: {e}")
        return None

def generar_imagen_con_pollinations(prompt):
    """Genera imagen con Pollinations (gratis, siempre funciona)"""
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', prompt[:30]).replace(' ', '_')
            filename = f"img_{timestamp}_{nombre}.png"
            filepath = os.path.join("imagenes_generadas", filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/imagenes/{filename}"
        return None
    except Exception as e:
        logging.error(f"Error Pollinations: {e}")
        return None

def generar_imagen(titulo, categoria):
    """Genera imagen usando Nano Banana si está disponible, si no Pollinations"""
    prompt = f"{categoria}: {titulo[:80]}. Imagen profesional para redes sociales."
    
    # Intento 1: Nano Banana
    imagen = generar_imagen_con_nano_banana(prompt)
    if imagen:
        return imagen
    
    # Intento 2: Pollinations (fallback gratuito)
    return generar_imagen_con_pollinations(prompt)

# ==================== GENERACIÓN DE VIDEOS (HÍBRIDO) ====================
def generar_video_con_higgsfield(prompt):
    """Genera video con Higgsfield (opcional)"""
    if not Config.HIGGSFIELD_API_KEY:
        return None
    try:
        headers = {"Authorization": f"Bearer {Config.HIGGSFIELD_API_KEY}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "duration": 10, "aspect_ratio": "9:16"}
        response = requests.post("https://api.higgsfield.ai/v1/video/generate", headers=headers, json=payload, timeout=30)
        if response.status_code == 202:
            return {"status": "processing", "message": "Video en procesamiento"}
        return None
    except Exception as e:
        logging.error(f"Error Higgsfield: {e}")
        return None

# ==================== NOTION INTEGRATION ====================
def enviar_a_notion(contenido, analisis, textos, imagenes):
    """Guarda todo el contenido en Notion"""
    if not Config.NOTION_API_KEY or not Config.NOTION_DATABASE_ID:
        return {"exito": False, "error": "Notion no configurado"}
    
    content_id = hashlib.md5(f"{contenido['url']}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    
    notion_data = {
        "parent": {"database_id": Config.NOTION_DATABASE_ID},
        "properties": {
            "ID": {"title": [{"text": {"content": f"CON-{content_id}-{datetime.now().strftime('%Y%m%d')}"}}]},
            "Título": {"rich_text": [{"text": {"content": contenido['titulo'][:200]}}]},
            "URL": {"url": contenido['url']},
            "Categoría": {"select": {"name": analisis.get('categoria_principal', 'Otro')}},
            "Fecha": {"date": {"start": datetime.now().isoformat()}},
            "Importancia": {"number": analisis.get('nivel_importancia', 3)},
            "Estado": {"select": {"name": "Procesado"}},
            "Motor IA": {"select": {"name": analisis.get('motor_usado', 'desconocido')}}
        },
        "children": [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📝 Resumen"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": analisis.get('resumen_ejecutivo', contenido['resumen'])[:2000]}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📱 Contenido para Redes"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": textos.get('instagram', '')[:500]}}]}}
        ]
    }
    
    if imagenes:
        notion_data["children"].append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": imagenes[0]}}})
    
    try:
        headers = {"Authorization": f"Bearer {Config.NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": Config.NOTION_VERSION}
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=notion_data, timeout=30)
        return {"exito": response.status_code == 200, "id": response.json().get('id') if response.status_code == 200 else None}
    except Exception as e:
        logging.error(f"Error Notion: {e}")
        return {"exito": False, "error": str(e)}

# ==================== GENERACIÓN DE CONTENIDO PARA REDES ====================
def generar_contenido_redes(contenido, analisis):
    """Genera contenido optimizado para todas las plataformas"""
    categoria = analisis.get('categoria_principal', 'Innovacion')
    emojis = {"Construccion": "🏗️", "Emprendimiento": "🚀", "Salud": "💪", "Educacion": "🎓", "Innovacion": "💡", "Tecnologia": "⚡"}
    emoji = emojis.get(categoria, "📚")
    
    tags = analisis.get('etiquetas_sugeridas', [])[:5]
    
    instagram = f"""{emoji} {contenido['titulo'][:70]} {emoji}

📌 {analisis.get('resumen_ejecutivo', contenido['resumen'])[:350]}

💡 {analisis.get('dato_impactante', 'Descubre más en nuestro sitio')[:150]}

💾 GUARDA este post
👥 COMPARTE con alguien

#Construex #{categoria} """ + " ".join([f"#{tag}" for tag in tags[:3]])
    
    twitter = f"🧵 {contenido['titulo'][:250]}\n\n🔗 {contenido['url']}\n#Construex #{categoria}"
    
    whatsapp = f"""{emoji} *CONSTRUEX* {emoji}

*{contenido['titulo'][:60]}*

{analisis.get('resumen_ejecutivo', contenido['resumen'])[:300]}

🔗 {contenido['url']}"""
    
    linkedin = f"""🏗️ **{contenido['titulo'][:80]}**

{analisis.get('resumen_ejecutivo', contenido['resumen'])[:400]}

🔗 {contenido['url']}

#Construex #{categoria}"""
    
    return {"instagram": instagram, "twitter": twitter, "whatsapp": whatsapp, "linkedin": linkedin, "categoria": categoria}

# ==================== PUBLICACIÓN A REDES ====================
def publicar_instagram(imagen_path, caption):
    if not Config.INSTAGRAM_ACCESS_TOKEN:
        return {"exito": False, "error": "No configurado"}
    try:
        if imagen_path and Config.INSTAGRAM_BUSINESS_ID:
            media_url = f"https://graph.facebook.com/v18.0/{Config.INSTAGRAM_BUSINESS_ID}/media"
            response = requests.post(media_url, data={'image_url': imagen_path, 'caption': caption[:2200], 'access_token': Config.INSTAGRAM_ACCESS_TOKEN}, timeout=30)
            if response.status_code == 200:
                creation_id = response.json().get('id')
                publish_url = f"https://graph.facebook.com/v18.0/{Config.INSTAGRAM_BUSINESS_ID}/media_publish"
                publish_response = requests.post(publish_url, data={'creation_id': creation_id, 'access_token': Config.INSTAGRAM_ACCESS_TOKEN}, timeout=30)
                return {"exito": publish_response.status_code == 200}
        return {"exito": False}
    except Exception as e:
        return {"exito": False, "error": str(e)}

def publicar_twitter(texto):
    if not Config.TWITTER_BEARER_TOKEN:
        return {"exito": False, "error": "No configurado"}
    try:
        response = requests.post("https://api.twitter.com/2/tweets", headers={"Authorization": f"Bearer {Config.TWITTER_BEARER_TOKEN}", "Content-Type": "application/json"}, json={"text": texto[:280]}, timeout=30)
        return {"exito": response.status_code == 201}
    except Exception as e:
        return {"exito": False, "error": str(e)}

def enviar_whatsapp(numero, mensaje):
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

# ==================== NOTA SOBRE NOTEBOOKLM ====================
def generar_contenido_profundo(contenido, analisis):
    """Prepara contenido para NotebookLM (no tiene API pública)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = re.sub(r'[^\w\s-]', '', contenido['titulo'][:50]).replace(' ', '_')
    
    contenido_notebook = f"""# {contenido['titulo']}

## Metadatos
- **Fuente:** {contenido['url']}
- **Categoría:** {analisis.get('categoria_principal', 'General')}
- **Motor IA:** {analisis.get('motor_usado', 'desconocido')}

## Resumen
{analisis.get('resumen_ejecutivo', contenido['resumen'])}

## Contenido Completo
{contenido['texto_completo'][:5000]}

## Etiquetas
{', '.join(analisis.get('etiquetas_sugeridas', []))}
"""
    
    archivo_path = os.path.join("podcasts_generados", f"notebooklm_{timestamp}_{nombre_base}.md")
    with open(archivo_path, 'w', encoding='utf-8') as f:
        f.write(contenido_notebook)
    
    if Config.NOTEBOOKLM_WEBHOOK_URL:
        try:
            requests.post(Config.NOTEBOOKLM_WEBHOOK_URL, json={"title": contenido['titulo'], "content": contenido_notebook}, timeout=30)
        except:
            pass
    
    return archivo_path

# ==================== FLUJO PRINCIPAL ====================
def procesar_url_completo(url, auto_publicar=False):
    resultado = {"exito": False, "url": url, "timestamp": datetime.now().isoformat(), "pasos": []}
    
    noticia = extraer_noticia(url)
    if not noticia:
        resultado["error"] = "No se pudo extraer"
        return resultado
    resultado["pasos"].append({"paso": "extraccion", "exito": True})
    
    analisis = analizar_contenido(noticia['titulo'], noticia['texto_completo'])
    resultado["pasos"].append({"paso": "analisis", "exito": True, "motor": analisis.get('motor_usado', 'desconocido')})
    
    textos = generar_contenido_redes(noticia, analisis)
    resultado["pasos"].append({"paso": "textos", "exito": True})
    
    imagen = generar_imagen(noticia['titulo'], analisis.get('categoria_principal', 'Innovacion'))
    resultado["imagen_url"] = imagen
    resultado["pasos"].append({"paso": "imagen", "exito": bool(imagen)})
    
    generar_contenido_profundo(noticia, analisis)
    resultado["pasos"].append({"paso": "notebooklm", "exito": True})
    
    if Config.AUTO_SYNC_NOTION and Config.NOTION_API_KEY:
        notion_result = enviar_a_notion(noticia, analisis, textos, [imagen] if imagen else [])
        resultado["notion"] = notion_result
        resultado["pasos"].append({"paso": "notion", "exito": notion_result.get('exito', False)})
    
    publicaciones = {}
    if auto_publicar or Config.AUTO_PUBLISH:
        if imagen:
            publicaciones['instagram'] = publicar_instagram(imagen, textos['instagram'])
        publicaciones['twitter'] = publicar_twitter(textos['twitter'])

    with open('logs/contenido_procesado.csv', 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([datetime.now().isoformat(), url, noticia['titulo'], analisis.get('categoria_principal'), analisis.get('motor_usado'), len(analisis.get('temas_relacionados', []))])
    
    resultado["exito"] = True
    resultado["noticia"] = {"titulo": noticia['titulo'], "resumen": noticia['resumen'][:300], "url": url}
    resultado["textos"] = textos
    resultado["publicaciones"] = publicaciones
    return resultado

# ==================== ENDPOINTS ====================
@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html><head><title>Construex Ecosystem 4.0</title>
    <style>
        body { font-family: Arial; background: #0f0f0f; padding: 20px; }
        .container { max-width: 1000px; margin: auto; background: #1a1a2e; border-radius: 20px; padding: 30px; color: white; }
        input { width: 70%; padding: 12px; background: #2a2a3e; border: none; border-radius: 8px; color: white; margin: 10px 0; }
        button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 8px; cursor: pointer; }
        .resultado { margin-top: 20px; display: none; }
        textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 12px; border-radius: 8px; margin: 10px 0; }
        .copy-btn { background: #3498db; padding: 8px 20px; border: none; border-radius: 8px; color: white; cursor: pointer; }
    </style>
    </head>
    <body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem 4.0</h1>
        <p>Sistema completo con Gemini + Grok + Notion + WhatsApp</p>
        <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
        <button onclick="procesar()">🚀 Procesar</button>
        <div id="resultado" class="resultado"></div>
    </div>
    <script>
    async function procesar() {
        const url = document.getElementById('urlInput').value;
        if (!url) return alert('Ingresa URL');
        document.getElementById('resultado').style.display = 'block';
        document.getElementById('resultado').innerHTML = '<div>⏳ Procesando...</div>';
        const response = await fetch('/procesar_completo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, auto_publicar: false})
        });
        const data = await response.json();
        if (data.exito) {
            let html = `<h3>📰 ${data.noticia.titulo}</h3><p>📁 ${data.textos.categoria} | Motor: ${data.pasos.find(p=>p.paso==='analisis')?.motor || 'desconocido'}</p>`;
            html += `<textarea id="textoInstagram" rows="10" readonly>${data.textos.instagram}</textarea>`;
            html += `<button class="copy-btn" onclick="copiarTexto()">📋 Copiar Instagram</button>`;
            document.getElementById('resultado').innerHTML = html;
        } else {
            document.getElementById('resultado').innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
        }
    }
    function copiarTexto() { const t = document.getElementById('textoInstagram'); t.select(); document.execCommand('copy'); alert('✅ Copiado'); }
    </script>
    </body>
    </html>
    '''

@app.route('/procesar_completo', methods=['POST'])
def procesar_completo_endpoint():
    data = request.get_json()
    url = data.get('url')
    auto_publicar = data.get('auto_publicar', Config.AUTO_PUBLISH)
    if not url:
        return jsonify({"error": "URL requerida"}), 400
    return jsonify(procesar_url_completo(url, auto_publicar))

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "online", "version": "4.0", "gemini": bool(Config.GEMINI_API_KEY), "grok": bool(Config.GROK_API_KEY), "notion": bool(Config.NOTION_API_KEY)})

@app.route('/imagenes/<path:filename>')
def servir_imagen(filename):
    return send_from_directory("imagenes_generadas", filename)

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    if Config.WHATSAPP_VERIFY_TOKEN:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token and mode == 'subscribe' and token == Config.WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.get_json()
        if data and 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    if 'value' in change and 'messages' in change['value']:
                        for message in change['value']['messages']:
                            if message['type'] == 'text':
                                enviar_whatsapp(message['from'], "🤖 Recibido por Construex. Gracias!")
        return jsonify({"status": "ok"}), 200
    except:
        return jsonify({"status": "error"}), 500

# ==================== SCHEDULER ====================
def escanear_rss():
    urls = []
    for feed_url in Config.RSS_FEEDS:
        if feed_url:
            try:
                import feedparser
                for entry in feedparser.parse(feed_url).entries[:5]:
                    if entry.get('link'):
                        urls.append(entry['link'])
            except:
                pass
    return urls

def proceso_automatico():
    logging.info("🔄 Inicio proceso automático")
    for url in escanear_rss():
        procesar_url_completo(url, auto_publicar=Config.AUTO_PUBLISH)
        time.sleep(5)

scheduler = BackgroundScheduler()
scheduler.add_job(proceso_automatico, 'interval', hours=Config.SCAN_INTERVAL_HOURS)
scheduler.start()

# ==================== MAIN ====================
if __name__ == '__main__':
    Config.validate()
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Servidor corriendo en http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
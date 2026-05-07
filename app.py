"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN COMPLETA PROFESIONAL
======================================================================
"""

import os
import re
import requests
import json
import time
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
from newspaper import Article
import google.generativeai as genai
from datetime import datetime

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes_generadas")
INFOGRAFIAS_DIR = os.path.join(BASE_DIR, "infografias_generadas")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos_generados")
AUDIOS_DIR = os.path.join(BASE_DIR, "audios_generados")
PUBLICACIONES_FILE = os.path.join(BASE_DIR, "publicaciones.json")

for d in [IMAGENES_DIR, INFOGRAFIAS_DIR, VIDEOS_DIR, AUDIOS_DIR]:
    os.makedirs(d, exist_ok=True)


def guardar_publicacion(data):
    """Guarda la publicación en el historial"""
    publicaciones = []
    if os.path.exists(PUBLICACIONES_FILE):
        with open(PUBLICACIONES_FILE, 'r', encoding='utf-8') as f:
            publicaciones = json.load(f)
    
    nueva = {
        "id": int(time.time()),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "titulo": data.get("titulo", ""),
        "categoria": data.get("categoria", ""),
        "url_original": data.get("url", ""),
        "imagenes": data.get("imagenes", []),
        "infografia": data.get("infografia", ""),
        "video": data.get("video", ""),
        "audio": data.get("audio", ""),
        "texto_instagram": data.get("texto_instagram", ""),
        "texto_facebook": data.get("texto_facebook", ""),
        "enlaces_extraidos": data.get("enlaces", []),
        "publicado": False,
        "viralidad": data.get("viralidad", 0),
        "fecha_procesamiento": datetime.now().isoformat()
    }
    
    publicaciones.insert(0, nueva)
    publicaciones = publicaciones[:100]  # Mantener últimos 100
    
    with open(PUBLICACIONES_FILE, 'w', encoding='utf-8') as f:
        json.dump(publicaciones, f, ensure_ascii=False, indent=2)
    
    return nueva["id"]


def extraer_enlaces_del_texto(texto):
    """Extrae todos los enlaces del texto"""
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    enlaces = re.findall(patron_url, texto)
    return list(set(enlaces))  # Eliminar duplicados


def extraer_articulo_con_newspaper(url):
    try:
        article = Article(url, language='es')
        article.download()
        article.parse()
        
        if article.text and len(article.text) > 200:
            return {
                "exito": True,
                "titulo": article.title or "Sin título",
                "texto_completo": article.text,
                "texto_resumen": article.text[:3000],
                "autores": article.authors,
                "fecha_publicacion": str(article.publish_date) if article.publish_date else "",
                "imagen_principal": article.top_image,
                "dominio": urlparse(url).netloc,
                "url": url
            }
        return None
    except Exception as e:
        print(f"Error newspaper: {e}")
        return None


def extraer_contenido_fallback(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        articulo = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'article|content|post'))
        
        if articulo:
            texto = articulo.get_text()
        else:
            texto = soup.get_text()
        
        texto = ' '.join(texto.split())
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        return {
            "exito": True,
            "titulo": titulo,
            "texto_completo": texto[:8000],
            "texto_resumen": texto[:2000],
            "dominio": urlparse(url).netloc,
            "url": url
        }
    except Exception as e:
        return {"exito": False, "error": str(e)}


def extraer_contenido_inteligente(url):
    resultado = extraer_articulo_con_newspaper(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con newspaper3k")
        return resultado
    
    resultado = extraer_contenido_fallback(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con método manual")
        return resultado
    
    return {"exito": False, "error": "No se pudo extraer el contenido"}


def analizar_noticia_con_gemini(titulo, texto_completo, enlaces):
    prompt = f"""
    Analiza la siguiente noticia y extrae TODA la información importante.
    
    TÍTULO: {titulo}
    
    TEXTO COMPLETO:
    {texto_completo[:5000]}
    
    ENLACES ENCONTRADOS:
    {chr(10).join(enlaces[:5]) if enlaces else 'Ninguno'}
    
    Responde SOLO con JSON:
    
    {{
        "resumen": "Resumen completo de la noticia en 3-4 líneas",
        "fecha": "Fecha del evento principal",
        "lugar": "Lugar donde ocurre",
        "cifras": ["cifra 1", "cifra 2", "cifra 3"],
        "protagonistas": ["protagonista 1", "protagonista 2"],
        "contexto": "Contexto breve",
        "impacto": "Impacto o repercusión",
        "enlaces_relevantes": ["enlace1", "enlace2"],
        "puntos_infografia": [
            "Título del punto 1: descripción breve",
            "Título del punto 2: descripción breve",
            "Título del punto 3: descripción breve",
            "Título del punto 4: descripción breve"
        ]
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        elif "```" in texto:
            texto = texto.split("```")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error Gemini: {e}")
        return {
            "resumen": texto_completo[:500],
            "fecha": "",
            "lugar": "",
            "cifras": [],
            "protagonistas": [],
            "contexto": "",
            "impacto": "",
            "enlaces_relevantes": [],
            "puntos_infografia": []
        }


def generar_imagen(titulo, categoria, index=0):
    """Genera imagen profesional"""
    prompts = [
        f"Professional social media post image for {categoria} category. Topic: {titulo[:80]}. Modern, clean, professional, eye-catching. High quality, 4K.",
        f"Infographic style image about {titulo[:80]}. Professional, clean, with charts and data visualization. Modern design.",
        f"Educational content image about {titulo[:80]}. Professional, inspiring, suitable for Instagram."
    ]
    prompt = prompts[index % len(prompts)]
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"imagen_{timestamp}_{index}_{nombre}.png"
            filepath = os.path.join(IMAGENES_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/imagenes/{filename}"
        return None
    except Exception as e:
        print(f"Error imagen: {e}")
        return None


def generar_infografia_html(titulo, analisis, categoria):
    """Genera infografía HTML profesional"""
    
    puntos = analisis.get('puntos_infografia', [])
    if not puntos:
        puntos = [
            f"📌 {analisis.get('resumen', '')[:100]}",
            f"💰 {analisis.get('cifras', ['Dato relevante'])[0] if analisis.get('cifras') else 'Información clave'}",
            f"📍 {analisis.get('lugar', 'Ubicación relevante')}",
            f"📅 {analisis.get('fecha', 'Fecha importante')}"
        ]
    
    colores = {
        "Construccion": "#795548",
        "Emprendimiento": "#FF9800",
        "Construex University": "#2196F3",
        "Salud": "#4CAF50",
        "Automejora": "#9C27B0"
    }
    color = colores.get(categoria, "#667eea")
    
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"infografia_{timestamp}_{nombre}.html"
    filepath = os.path.join(INFOGRAFIAS_DIR, filename)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Construex - Infografía</title>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: linear-gradient(135deg, {color} 0%, #2c3e50 100%);
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 40px;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .infografia {{
            max-width: 1080px;
            width: 100%;
            background: rgba(255,255,255,0.95);
            border-radius: 30px;
            overflow: hidden;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
        }}
        .header {{
            background: {color};
            padding: 30px;
            text-align: center;
            color: white;
        }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .contenido {{ padding: 30px; }}
        .punto {{
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 15px;
            border-left: 5px solid {color};
        }}
        .punto-icono {{ font-size: 32px; min-width: 60px; text-align: center; }}
        .punto-texto {{ font-size: 16px; line-height: 1.5; color: #333; }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #eee;
        }}
        .categoria-badge {{
            display: inline-block;
            background: {color};
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    <div class="infografia">
        <div class="header">
            <div class="categoria-badge">{categoria.upper()}</div>
            <h1>{titulo[:80]}</h1>
        </div>
        <div class="contenido">
            {''.join([f'<div class="punto"><div class="punto-icono">{["📊","💰","📍","📅","🎯","💡"][i%6]}</div><div class="punto-texto">{p}</div></div>' for i, p in enumerate(puntos[:8])])}
        </div>
        <div class="footer">
            Construex Ecosystem | Infografía generada automáticamente<br>
            📌 Guarda • 👥 Comparte • 💬 Comenta
        </div>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return f"/infografias/{filename}"


def generar_video_simulado(titulo, categoria):
    """Genera un video simulado (placeholder)"""
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"video_{timestamp}_{nombre}.html"
    filepath = os.path.join(VIDEOS_DIR, filename)
    
    colores = {
        "Construccion": "#795548",
        "Emprendimiento": "#FF9800",
        "Construex University": "#2196F3",
        "Salud": "#4CAF50",
        "Automejora": "#9C27B0"
    }
    color = colores.get(categoria, "#667eea")
    
    html = f"""<!DOCTYPE html>
<html>
<head><title>Video - {titulo}</title>
<style>
    body {{ margin: 0; background: {color}; font-family: Arial; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    .video {{ width: 1080px; height: 1080px; background: linear-gradient(135deg, {color}, #2c3e50); display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; text-align: center; padding: 40px; }}
    h1 {{ font-size: 48px; margin-bottom: 20px; }}
    p {{ font-size: 24px; }}
    .btn {{ background: #FFD700; color: #333; padding: 15px 30px; border-radius: 50px; text-decoration: none; margin-top: 30px; display: inline-block; }}
</style>
</head>
<body>
    <div class="video">
        <h1>🎬 {titulo[:60]}</h1>
        <p>Video educativo sobre {categoria}</p>
        <a href="#" class="btn">📥 Descargar Video (Simulado)</a>
        <p style="margin-top: 30px; font-size: 14px;">💡 Para generar videos reales, necesitas API de generación de video</p>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return f"/videos/{filename}"


def generar_podcast(titulo, resumen, categoria):
    """Genera podcast simulado"""
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"podcast_{timestamp}_{nombre}.html"
    filepath = os.path.join(AUDIOS_DIR, filename)
    
    colores = {
        "Construccion": "#795548",
        "Emprendimiento": "#FF9800",
        "Construex University": "#2196F3",
        "Salud": "#4CAF50",
        "Automejora": "#9C27B0"
    }
    color = colores.get(categoria, "#667eea")
    
    html = f"""<!DOCTYPE html>
<html>
<head><title>Podcast - {titulo}</title>
<style>
    body {{ margin: 0; background: {color}; font-family: Arial; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    .podcast {{ width: 1080px; height: 1080px; background: linear-gradient(135deg, {color}, #2c3e50); display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; text-align: center; padding: 40px; }}
    .transcripcion {{ background: rgba(0,0,0,0.5); border-radius: 20px; padding: 20px; margin-top: 20px; font-size: 14px; text-align: left; }}
</style>
</head>
<body>
    <div class="podcast">
        <h1>🎙️ PODCAST: {titulo[:60]}</h1>
        <p>Duración: 3-5 minutos</p>
        <div class="transcripcion">
            <strong>📝 Transcripción:</strong><br>
            {resumen[:500]}...
        </div>
        <p style="margin-top: 30px;">▶️ Escucha el podcast completo en nuestra plataforma</p>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return f"/audios/{filename}"


def clasificar_categoria(titulo, texto):
    texto_lower = f"{titulo} {texto[:500]}".lower()
    if any(p in texto_lower for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal"]):
        return "Construccion"
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "inversion", "empleo"]):
        return "Emprendimiento"
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University"
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud"
    return "Automejora"


def generar_texto_redes(titulo, analisis, categoria, enlaces):
    emojis = {"Construccion": "🏗️", "Emprendimiento": "🚀", "Construex University": "🎓", "Salud": "💪", "Automejora": "🌟"}
    emoji = emojis.get(categoria, "📚")
    
    resumen = analisis.get('resumen', titulo)
    lugar = analisis.get('lugar', '')
    fecha = analisis.get('fecha', '')
    cifras = analisis.get('cifras', [])
    contexto = analisis.get('contexto', '')
    impacto = analisis.get('impacto', '')
    
    # Instagram
    instagram = f"""{emoji} {titulo[:70]} {emoji}

📌 {resumen}

{chr(10).join([f'💰 {c}' for c in cifras[:3]]) if cifras else ''}

{f'📍 {lugar}' if lugar else ''}{f'   📅 {fecha}' if fecha else ''}

🎯 {contexto[:200] if contexto else ''}

✨ {impacto[:150] if impacto else ''}

📚 MÁS INFORMACIÓN:
{chr(10).join([f'🔗 {e[:60]}...' for e in enlaces[:2]]) if enlaces else ''}

💾 GUARDA este post
👥 COMPARTE con alguien

#{categoria.replace(' ', '')} #Construex #Noticias"""
    
    # Facebook
    facebook = f"""{titulo}

{resumen}

{f'📍 {lugar}' if lugar else ''} {f'📅 {fecha}' if fecha else ''}

{chr(10).join([f'✅ {c}' for c in cifras[:3]]) if cifras else ''}

{contexto[:300] if contexto else ''}

{impacto[:200] if impacto else ''}

{chr(10).join([f'🔗 {e}' for e in enlaces[:2]]) if enlaces else ''}

#{categoria.replace(' ', '')} #Construex"""
    
    return instagram, facebook

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Pro - Generador Completo</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; text-align: center; }
            input { width: 60%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-left: 10px; }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; margin-bottom: 20px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; }
            .card-body { padding: 20px; }
            textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; resize: vertical; margin-bottom: 10px; }
            .copy-btn { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; background: #9C27B0; margin-right: 10px; }
            .preview-img { max-width: 200px; border-radius: 12px; margin: 10px; }
            .galeria { display: flex; flex-wrap: wrap; gap: 10px; }
            .tab { overflow: hidden; border-bottom: 1px solid #3a3a4e; margin-bottom: 20px; }
            .tab button { background: inherit; border: none; color: white; padding: 10px 20px; cursor: pointer; margin: 0; }
            .tab button:hover { background: #2a2a3e; }
            .tab button.active { background: #3498db; }
            .tabcontent { display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Pro</h1>
                <p>Genera infografías, imágenes, videos y contenido para redes sociales</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
                <button onclick="procesar()">🚀 Generar TODO</button>
                <div class="loading" id="loading">⏳ Generando contenido...</div>
            </div>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultado').style.display = 'none';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                
                if (data.exito) {
                    mostrarResultado(data);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch(e) {
                alert('Error: ' + e.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function mostrarResultado(data) {
            let html = `
                <div class="card">
                    <div class="card-header">📊 CONTENIDO GENERADO</div>
                    <div class="card-body">
                        <span class="categoria-badge">📁 ${data.categoria}</span>
                        <h3>${data.titulo}</h3>
                        
                        <div class="tab">
                            <button class="tablinks" onclick="openTab(event, 'Imagenes')" id="defaultOpen">🖼️ Imágenes (${data.imagenes.length})</button>
                            <button class="tablinks" onclick="openTab(event, 'Infografia')">📊 Infografía</button>
                            <button class="tablinks" onclick="openTab(event, 'Video')">🎬 Video</button>
                            <button class="tablinks" onclick="openTab(event, 'Podcast')">🎙️ Podcast</button>
                            <button class="tablinks" onclick="openTab(event, 'Textos')">📱 Textos</button>
                        </div>
                        
                        <div id="Imagenes" class="tabcontent">
                            <div class="galeria">
                                ${data.imagenes.map(img => `<img src="${img}" class="preview-img"><br><a href="${img}" download>📥 Descargar</a>`).join('')}
                            </div>
                        </div>
                        
                        <div id="Infografia" class="tabcontent">
                            <iframe src="${data.infografia}" style="width:100%; height:600px; border:none; border-radius:12px;"></iframe>
                            <a href="${data.infografia}" download style="display:inline-block; margin-top:10px;">📥 Descargar Infografía</a>
                        </div>
                        
                        <div id="Video" class="tabcontent">
                            <iframe src="${data.video}" style="width:100%; height:600px; border:none; border-radius:12px;"></iframe>
                            <a href="${data.video}" download style="display:inline-block; margin-top:10px;">📥 Descargar Video</a>
                        </div>
                        
                        <div id="Podcast" class="tabcontent">
                            <iframe src="${data.audio}" style="width:100%; height:600px; border:none; border-radius:12px;"></iframe>
                            <a href="${data.audio}" download style="display:inline-block; margin-top:10px;">📥 Descargar Podcast</a>
                        </div>
                        
                        <div id="Textos" class="tabcontent">
                            <strong>📱 Instagram:</strong>
                            <textarea rows="8" readonly>${data.texto_instagram}</textarea>
                            <button class="copy-btn" onclick="copiarTexto(this)">📋 Copiar</button>
                            
                            <strong style="margin-top:15px; display:block;">📘 Facebook:</strong>
                            <textarea rows="6" readonly>${data.texto_facebook}</textarea>
                            <button class="copy-btn" onclick="copiarTexto(this)">📋 Copiar</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('resultado').innerHTML = html;
            document.getElementById('resultado').style.display = 'block';
            document.getElementById('defaultOpen').click();
        }
        
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }
        
        function copiarTexto(btn) {
            const textarea = btn.previousElementSibling;
            textarea.select();
            document.execCommand('copy');
            alert('✅ Texto copiado');
        }
        </script>
    </body>
    </html>
    """


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "No hay URL"}), 400
    
    # 1. Extraer contenido
    contenido = extraer_contenido_inteligente(url)
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo extraer')}), 400
    
    # 2. Extraer enlaces del texto
    enlaces_extraidos = extraer_enlaces_del_texto(contenido['texto_completo'])
    
    # 3. Clasificar categoría
    categoria = clasificar_categoria(contenido['titulo'], contenido['texto_resumen'])
    
    # 4. Analizar con Gemini
    analisis = analizar_noticia_con_gemini(contenido['titulo'], contenido['texto_resumen'], enlaces_extraidos)
    
    # 5. Generar imágenes (3 imágenes)
    imagenes = []
    for i in range(3):
        img = generar_imagen(contenido['titulo'], categoria, i)
        if img:
            imagenes.append(img)
    
    # 6. Generar infografía
    infografia = generar_infografia_html(contenido['titulo'], analisis, categoria)
    
    # 7. Generar video simulado
    video = generar_video_simulado(contenido['titulo'], categoria)
    
    # 8. Generar podcast simulado
    podcast = generar_podcast(contenido['titulo'], analisis.get('resumen', ''), categoria)
    
    # 9. Generar textos para redes
    texto_instagram, texto_facebook = generar_texto_redes(
        contenido['titulo'], analisis, categoria, enlaces_extraidos[:3]
    )
    
    # 10. Guardar publicación
    guardar_publicacion({
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "url": url,
        "imagenes": imagenes,
        "infografia": infografia,
        "video": video,
        "audio": podcast,
        "texto_instagram": texto_instagram,
        "texto_facebook": texto_facebook,
        "enlaces": enlaces_extraidos[:5],
        "viralidad": 8
    })
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "titulo": contenido['titulo'],
        "imagenes": imagenes,
        "infografia": infografia,
        "video": video,
        "audio": podcast,
        "texto_instagram": texto_instagram,
        "texto_facebook": texto_facebook
    })


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/infografias/<path:filename>')
def descargar_infografia(filename):
    return send_from_directory(INFOGRAFIAS_DIR, filename, as_attachment=True)


@app.route('/videos/<path:filename>')
def descargar_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=True)


@app.route('/audios/<path:filename>')
def descargar_audio(filename):
    return send_from_directory(AUDIOS_DIR, filename, as_attachment=True)


@app.route('/historial', methods=['GET'])
def historial():
    if os.path.exists(PUBLICACIONES_FILE):
        with open(PUBLICACIONES_FILE, 'r', encoding='utf-8') as f:
            return jsonify({"publicaciones": json.load(f)})
    return jsonify({"publicaciones": []})


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
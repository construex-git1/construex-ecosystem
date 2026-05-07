"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN COMPLETA
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

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)


def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)


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
                "dominio": urlparse(url).netloc
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
            "dominio": urlparse(url).netloc
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


def analizar_noticia_con_gemini(titulo, texto_completo):
    prompt = f"""
    Analiza la siguiente noticia y extrae TODA la información importante.
    
    TÍTULO: {titulo}
    
    TEXTO COMPLETO:
    {texto_completo[:5000]}
    
    Responde SOLO con JSON en este formato EXACTO. Si no encuentras un campo, déjalo como cadena vacía:
    
    {{
        "resumen": "Resumen completo de la noticia en 3-4 líneas explicando qué pasó, cuándo, dónde y cifras importantes",
        "fecha": "Fecha del evento principal (ej: mayo 2026, 1 de mayo, etc.)",
        "lugar": "Lugar donde ocurre (ciudad, país, provincia)",
        "cifras": ["cifra 1", "cifra 2", "cifra 3"],
        "protagonistas": ["protagonista 1", "protagonista 2"],
        "contexto": "Contexto breve de por qué es importante esta noticia",
        "impacto": "Impacto o repercusión de esta noticia"
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
            "impacto": ""
        }


def generar_imagen(titulo, categoria):
    prompt = f"Professional social media post image for {categoria} category. Topic: {titulo[:80]}. Modern, clean, professional, eye-catching. High quality, 4K, vibrant colors."
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    try:
        print(f"   🖼️ Generando imagen...")
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"imagen_{timestamp}_{nombre}.png"
            filepath = os.path.join(IMAGENES_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/imagenes/{filename}"
        return None
    except Exception as e:
        print(f"Error imagen: {e}")
        return None


def clasificar_categoria(titulo, texto):
    texto_lower = f"{titulo} {texto[:500]}".lower()
    
    if any(p in texto_lower for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal", "construcción"]):
        return "Construccion"
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "inversion", "empleo"]):
        return "Emprendimiento"
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University"
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud"
    return "Automejora"


def generar_texto_redes(titulo, analisis, categoria):
    emojis = {
        "Construccion": "🏗️",
        "Emprendimiento": "🚀",
        "Construex University": "🎓",
        "Salud": "💪",
        "Automejora": "🌟"
    }
    emoji = emojis.get(categoria, "📚")
    
    resumen = analisis.get('resumen', titulo)
    lugar = analisis.get('lugar', '')
    fecha = analisis.get('fecha', '')
    cifras = analisis.get('cifras', [])
    contexto = analisis.get('contexto', '')
    impacto = analisis.get('impacto', '')
    
    # Construir texto de Instagram
    instagram_lines = []
    instagram_lines.append(f"{emoji} {titulo[:70]} {emoji}")
    instagram_lines.append("")
    instagram_lines.append(f"📌 {resumen}")
    instagram_lines.append("")
    
    if cifras:
        instagram_lines.append("💰 DATOS CLAVE:")
        for c in cifras[:3]:
            instagram_lines.append(f"   • {c}")
        instagram_lines.append("")
    
    if lugar or fecha:
        info_line = ""
        if lugar:
            info_line += f"📍 {lugar}"
        if fecha:
            info_line += f"   📅 {fecha}"
        if info_line:
            instagram_lines.append(info_line)
            instagram_lines.append("")
    
    if contexto:
        instagram_lines.append(f"🎯 {contexto}")
        instagram_lines.append("")
    
    if impacto:
        instagram_lines.append(f"✨ {impacto}")
        instagram_lines.append("")
    
    instagram_lines.append("💾 GUARDA este post")
    instagram_lines.append("👥 COMPARTE con alguien")
    instagram_lines.append("")
    instagram_lines.append(f"#{categoria.replace(' ', '')} #Construex #Noticias")
    
    texto_instagram = "\n".join(instagram_lines)
    
    # Texto para Facebook (más simple)
    facebook_lines = []
    facebook_lines.append(titulo)
    facebook_lines.append("")
    facebook_lines.append(resumen)
    facebook_lines.append("")
    
    if cifras:
        facebook_lines.append("Datos clave:")
        for c in cifras[:3]:
            facebook_lines.append(f"• {c}")
        facebook_lines.append("")
    
    if lugar or fecha:
        info = ""
        if lugar:
            info += f"📍 {lugar}"
        if fecha:
            info += f" | 📅 {fecha}"
        facebook_lines.append(info)
        facebook_lines.append("")
    
    facebook_lines.append(f"#{categoria.replace(' ', '')} #Construex")
    
    texto_facebook = "\n".join(facebook_lines)
    
    return texto_instagram, texto_facebook


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Contenido</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; text-align: center; }
            input { width: 70%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-left: 10px; }
            button:hover { transform: scale(1.02); }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; margin-bottom: 20px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; }
            .card-body { padding: 20px; }
            textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; resize: vertical; margin-bottom: 10px; }
            .copy-btn { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; background: #9C27B0; margin-right: 10px; }
            .info-box { background: #2a2a3e; padding: 15px; border-radius: 12px; margin-top: 15px; color: #ddd; line-height: 1.5; }
            .preview-img { max-width: 100%; border-radius: 12px; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Ecosystem</h1>
                <p>Extrae noticias, genera resúmenes e imágenes para redes sociales</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
                <button onclick="procesar()">🚀 Generar Contenido</button>
                <div class="loading" id="loading">⏳ Procesando...</div>
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
                    <div class="card-header">📋 ANÁLISIS DE LA NOTICIA</div>
                    <div class="card-body">
                        <span class="categoria-badge">📁 ${data.categoria}</span>
                        <h3 style="color: white; margin: 15px 0;">${data.titulo}</h3>
                        ${data.imagen_url ? `<img src="${data.imagen_url}" class="preview-img"><br>` : ''}
                        <div class="info-box"><strong>📝 RESUMEN</strong><br>${data.analisis.resumen || 'No disponible'}</div>
                        ${data.analisis.fecha ? `<div class="info-box"><strong>📅 FECHA</strong><br>${data.analisis.fecha}</div>` : ''}
                        ${data.analisis.lugar ? `<div class="info-box"><strong>📍 LUGAR</strong><br>${data.analisis.lugar}</div>` : ''}
                        ${data.analisis.cifras?.length ? `<div class="info-box"><strong>💰 CIFRAS CLAVE</strong><br>${data.analisis.cifras.join('<br>')}</div>` : ''}
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📱 TEXTO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="12" readonly style="width:100%;">${data.texto_instagram}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📘 TEXTO PARA FACEBOOK</div>
                    <div class="card-body">
                        <textarea id="textoFacebook" rows="8" readonly style="width:100%;">${data.texto_facebook}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoFacebook')">📋 Copiar</button>
                    </div>
                </div>
            `;
            
            document.getElementById('resultado').innerHTML = html;
            document.getElementById('resultado').style.display = 'block';
        }
        
        function copiarTexto(id) {
            const textarea = document.getElementById(id);
            textarea.select();
            document.execCommand('copy');
            alert('✅ Copiado al portapapeles');
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
    
    contenido = extraer_contenido_inteligente(url)
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo extraer')}), 400
    
    categoria = clasificar_categoria(contenido['titulo'], contenido['texto_resumen'])
    
    analisis = analizar_noticia_con_gemini(contenido['titulo'], contenido['texto_resumen'])
    
    imagen_url = generar_imagen(contenido['titulo'], categoria)
    
    texto_instagram, texto_facebook = generar_texto_redes(
        contenido['titulo'], analisis, categoria
    )
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "titulo": contenido['titulo'],
        "analisis": analisis,
        "imagen_url": imagen_url,
        "texto_instagram": texto_instagram,
        "texto_facebook": texto_facebook
    })


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
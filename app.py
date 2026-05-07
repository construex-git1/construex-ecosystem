"""
======================================================================
         CONSTRUEX ECOSYSTEM - EXTRACCIÓN PRECISA + IMÁGENES
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
    """
    Extrae SOLO el artículo principal usando newspaper3k
    Ignora menús, publicidad, secciones laterales
    """
    try:
        article = Article(url, language='es')
        article.download()
        article.parse()
        
        if article.text and len(article.text) > 200:
            return {
                "exito": True,
                "titulo": article.title or "Sin título",
                "texto_completo": article.text,
                "texto_resumen": article.text[:2000],
                "autores": article.authors,
                "fecha_publicacion": str(article.publish_date) if article.publish_date else "",
                "imagen_principal": article.top_image,
                "dominio": urlparse(url).netloc
            }
        else:
            return None
    except Exception as e:
        print(f"Error con newspaper: {e}")
        return None


def extraer_contenido_fallback(url):
    """Extracción manual de respaldo"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Eliminar elementos no deseados
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            element.decompose()
        
        # Intentar encontrar el artículo
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
    """Orquesta la extracción, priorizando newspaper3k"""
    
    # 1. Intentar con newspaper3k (mejor para noticias)
    resultado = extraer_articulo_con_newspaper(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con newspaper3k")
        return resultado
    
    # 2. Fallback manual
    resultado = extraer_contenido_fallback(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con método manual")
        return resultado
    
    return {"exito": False, "error": "No se pudo extraer el contenido"}


def analizar_noticia_con_gemini(titulo, texto_completo):
    """Analiza la noticia y extrae información clave"""
    
    prompt = f"""
    Analiza la siguiente noticia y extrae la información más importante.
    
    TÍTULO: {titulo}
    
    TEXTO DE LA NOTICIA:
    {texto_completo[:6000]}
    
    Responde SOLO con JSON en este formato:
    
    {{
        "resumen": "Resumen de la noticia en 2-3 líneas, explicando QUÉ pasó",
        "datos_clave": {{
            "fecha": "Fecha del evento si aparece",
            "lugar": "Lugar donde ocurre",
            "cifras": ["cifra importante 1", "cifra importante 2"],
            "protagonistas": ["persona o empresa 1", "persona o empresa 2"]
        }},
        "contexto": "Contexto breve de por qué es importante",
        "impacto": "Impacto potencial"
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error Gemini: {e}")
        return {
            "resumen": texto_completo[:300],
            "datos_clave": {"fecha": "", "lugar": "", "cifras": [], "protagonistas": []},
            "contexto": "",
            "impacto": ""
        }


def generar_imagen(titulo, categoria):
    """Genera imagen profesional con Pollinations"""
    
    prompt = f"Professional social media post image for {categoria} category. Topic: {titulo[:80]}. Style: modern, clean, professional, eye-catching, suitable for Instagram. High quality, 4K, vibrant colors."
    
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
            
            print(f"   ✅ Imagen guardada: {filepath}")
            return f"/imagenes/{filename}"
        else:
            print(f"   ❌ Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def clasificar_categoria(titulo, texto):
    texto_lower = f"{titulo} {texto[:500]}".lower()
    
    if any(p in texto_lower for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal", "construcción"]):
        return "Construccion", 9
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "inversion", "empleo", "trabajo"]):
        return "Emprendimiento", 8
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion", "certificacion", "estudio"]):
        return "Construex University", 7
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar", "dieta", "ejercicio"]):
        return "Salud", 7
    return "Automejora", 6


def generar_texto_redes(titulo, analisis, categoria):
    """Genera texto optimizado para redes sociales"""
    
    emojis = {
        "Construccion": "🏗️",
        "Emprendimiento": "🚀",
        "Construex University": "🎓",
        "Salud": "💪",
        "Automejora": "🌟"
    }
    emoji = emojis.get(categoria, "📚")
    
    datos = analisis.get('datos_clave', {})
    lugar = datos.get('lugar', '')
    fecha = datos.get('fecha', '')
    cifras = datos.get('cifras', [])
    resumen = analisis.get('resumen', titulo)
    impacto = analisis.get('impacto', '')
    
    texto_instagram = f"""{emoji} {titulo[:70]} {emoji}

📌 {resumen}

{chr(10).join([f'💰 {c}' for c in cifras[:2]]) if cifras else ''}

📍 {lugar}
📅 {fecha}

✨ {impacto[:150] if impacto else ''}

💾 GUARDA este post
👥 COMPARTE con alguien

#{categoria.replace(' ', '')} #Construex #Noticias
"""
    
    texto_facebook = f"""{titulo}

{resumen}

{f'📍 {lugar}' if lugar else ''}
{f'📅 {fecha}' if fecha else ''}

{impacto[:200] if impacto else ''}

#{categoria.replace(' ', '')} #Construex
"""
    
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
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; min-height: 100vh; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; }
            .header h1 { font-size: 36px; margin-bottom: 10px; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; text-align: center; }
            input { width: 70%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-left: 10px; }
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
                        <span class="categoria-badge" style="background:#e67e22;">🔥 Viralidad: ${data.viralidad}/10</span>
                        <h3 style="color: white; margin: 15px 0;">${data.titulo}</h3>
                        
                        ${data.imagen_url ? `<img src="${data.imagen_url}" class="preview-img" alt="Imagen generada"><br>` : ''}
                        
                        <div class="info-box">
                            <strong>📝 RESUMEN</strong><br>
                            ${data.analisis.resumen || 'No disponible'}
                        </div>
                        
                        ${data.analisis.datos_clave?.fecha ? `<div class="info-box"><strong>📅 FECHA:</strong><br>${data.analisis.datos_clave.fecha}</div>` : ''}
                        ${data.analisis.datos_clave?.lugar ? `<div class="info-box"><strong>📍 LUGAR:</strong><br>${data.analisis.datos_clave.lugar}</div>` : ''}
                        ${data.analisis.datos_clave?.cifras?.length ? `<div class="info-box"><strong>💰 CIFRAS CLAVE:</strong><br>${data.analisis.datos_clave.cifras.join('<br>')}</div>` : ''}
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
    
    # 1. Extraer contenido preciso del artículo
    contenido = extraer_contenido_inteligente(url)
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo extraer')}), 400
    
    # 2. Clasificar categoría
    categoria, viralidad = clasificar_categoria(contenido['titulo'], contenido['texto_resumen'])
    
    # 3. Analizar con Gemini
    analisis = analizar_noticia_con_gemini(contenido['titulo'], contenido['texto_resumen'])
    
    # 4. Generar imagen
    imagen_url = generar_imagen(contenido['titulo'], categoria)
    
    # 5. Generar textos para redes
    texto_instagram, texto_facebook = generar_texto_redes(
        contenido['titulo'], analisis, categoria
    )
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
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
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
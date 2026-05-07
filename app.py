"""
======================================================================
         CONSTRUEX ECOSYSTEM - EXTRACCIÓN AUTOMÁTICA PROFESIONAL
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
import io
import PyPDF2
from readability import Readability
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


def extraer_contenido_con_gemini(url):
    """
    Usa la función nativa de Gemini para leer URLs
    Ventajas: supera Cloudflare, extrae contenido principal automáticamente
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        # Usar URL Context de Gemini [citation:5][citation:10]
        prompt = f"""
        Analiza el contenido de esta URL y extrae:
        1. Título principal
        2. Texto completo del artículo (sin HTML, sin código)
        3. Resumen ejecutivo (2-3 líneas)
        4. Puntos clave (3-5 puntos)
        5. Fecha de publicación si está disponible
        6. Autor si está disponible
        
        URL: {url}
        
        Devuelve SOLO JSON en este formato:
        {{
            "titulo": "...",
            "texto_completo": "...",
            "resumen": "...",
            "puntos_clave": ["punto1", "punto2", "punto3"],
            "fecha_publicacion": "...",
            "autor": "...",
            "exito": true
        }}
        """
        
        response = gemini_model.generate_content(prompt)
        texto = response.text
        
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        
        resultado = json.loads(texto.strip())
        return resultado
        
    except Exception as e:
        print(f"Error con Gemini URL Context: {e}")
        return None


def extraer_contenido_con_readability(url):
    """
    Extrae contenido usando readability (versátil, no requiere Gemini)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        
        # Usar readability para extraer contenido principal [citation:4][citation:9]
        doc = Readability(response.text, url=url)
        article, _ = doc.parse()
        
        if article and article.text_content and len(article.text_content) > 200:
            # Extraer metadatos básicos
            soup = BeautifulSoup(response.text, 'html.parser')
            titulo = article.title or soup.find('title').text.strip() if soup.find('title') else "Sin título"
            
            # Extraer fecha
            fecha = ""
            for tag in soup.find_all(['time', 'meta']):
                if tag.get('datetime'):
                    fecha = tag.get('datetime')
                    break
                elif tag.get('content') and 'date' in str(tag.get('property', '')):
                    fecha = tag.get('content')
                    break
            
            # Extraer autor
            autor = ""
            for tag in soup.find_all(['meta', 'span', 'div', 'a']):
                if 'author' in str(tag.get('class', [])).lower() or tag.get('rel') == ['author']:
                    autor = tag.text.strip()
                    break
            
            return {
                "exito": True,
                "titulo": titulo,
                "texto_completo": article.text_content[:5000],
                "resumen": article.excerpt or article.text_content[:300],
                "puntos_clave": [],
                "fecha_publicacion": fecha,
                "autor": autor
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error con readability: {e}")
        return None


def extraer_contenido_pdf(url):
    """Extrae texto de un PDF desde URL sin descargarlo"""
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        texto_completo = ""
        for page in pdf_reader.pages[:20]:  # Máximo 20 páginas
            texto_completo += page.extract_text()
        
        if texto_completo:
            # Intentar extraer título del PDF
            titulo = texto_completo.split('\n')[0][:100] if texto_completo else "Documento PDF"
            
            return {
                "exito": True,
                "titulo": titulo,
                "texto_completo": texto_completo[:5000],
                "resumen": texto_completo[:300],
                "puntos_clave": [],
                "fecha_publicacion": "",
                "autor": "",
                "es_pdf": True
            }
    except Exception as e:
        print(f"Error leyendo PDF: {e}")
    
    return None


def extraer_contenido_manual(url):
    """
    Extracción manual avanzada como último recurso
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Eliminar elementos no deseados
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            element.decompose()
        
        # Extraer título
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        # Extraer texto completo
        texto_completo = soup.get_text()
        texto_completo = ' '.join(texto_completo.split())
        
        # Extraer metadatos
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        descripcion = meta_desc.get('content', '')[:500] if meta_desc else ""
        
        return {
            "exito": True,
            "titulo": titulo,
            "texto_completo": texto_completo[:5000],
            "resumen": descripcion or texto_completo[:300],
            "puntos_clave": [],
            "fecha_publicacion": "",
            "autor": ""
        }
        
    except Exception as e:
        return {"exito": False, "error": str(e)}


def extraer_contenido_inteligente(url):
    """
    Orquesta múltiples métodos de extracción en orden de prioridad
    """
    # 1. Si es PDF, usar método específico
    if url.lower().endswith('.pdf'):
        resultado = extraer_contenido_pdf(url)
        if resultado and resultado.get('exito'):
            return resultado
    
    # 2. Intentar con Gemini URL Context (más potente) [citation:5]
    if GEMINI_API_KEY:
        resultado = extraer_contenido_con_gemini(url)
        if resultado and resultado.get('exito') and len(resultado.get('texto_completo', '')) > 200:
            print("   ✅ Extraído con Gemini URL Context")
            return resultado
    
    # 3. Intentar con readability
    resultado = extraer_contenido_con_readability(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con readability")
        return resultado
    
    # 4. Fallback manual
    resultado = extraer_contenido_manual(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Extraído con método manual")
        return resultado
    
    return {"exito": False, "error": "No se pudo extraer el contenido"}


def clasificar_categoria(titulo, texto_completo):
    texto = f"{titulo} {texto_completo[:500]}".lower()
    
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal", "arquitect"]):
        return "Construccion", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion", "startup"]):
        return "Emprendimiento", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion", "estudio"]):
        return "Construex University", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta", "ejercicio", "hospital"]):
        return "Salud", 6
    return "Automejora", 5


def generar_textos_redes(titulo, texto_completo, categoria, viralidad):
    """Genera textos optimizados para redes sociales"""
    
    emojis = {
        "Construccion": "🏗️",
        "Emprendimiento": "🚀",
        "Construex University": "🎓",
        "Salud": "💪",
        "Automejora": "🌟"
    }
    emoji = emojis.get(categoria, "📚")
    
    # Generar resumen automático
    resumen = texto_completo[:350] if texto_completo else ""
    
    # Generar puntos clave desde el texto
    frases = [s.strip() for s in re.split(r'[.!?]+', texto_completo) if len(s.strip()) > 30][:4]
    puntos_clave = frases if len(frases) >= 3 else [texto_completo[:100], texto_completo[100:200], texto_completo[200:300]]
    
    texto_instagram = f"""{emoji} {titulo[:80]} {emoji}

📌 {resumen}

✨ {puntos_clave[0] if puntos_clave else ''}
💡 {puntos_clave[1] if len(puntos_clave) > 1 else ''}
🔑 {puntos_clave[2] if len(puntos_clave) > 2 else ''}

💾 GUARDA este post para después
👥 COMPARTE con alguien que le interese

#{categoria.replace(' ', '')} #Construex #Educacion #Aprende #Informacion
"""
    
    texto_facebook = f"""{titulo}

{resumen}

📢 ¿Qué opinas sobre este tema?

Déjanos tu comentario 👇

#{categoria.replace(' ', '')} #Construex
"""
    
    return {
        "resumen": resumen,
        "puntos_clave": puntos_clave[:3],
        "texto_instagram": texto_instagram,
        "texto_facebook": texto_facebook
    }


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Extractor de Contenido</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; min-height: 100vh; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; }
            .header h1 { font-size: 36px; margin-bottom: 10px; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; text-align: center; }
            input { width: 70%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            select { padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; margin-left: 10px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-left: 10px; }
            button:hover { transform: scale(1.02); }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; margin-bottom: 20px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; }
            .card-body { padding: 20px; }
            textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; resize: vertical; }
            .copy-btn { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; background: #9C27B0; }
            .info-extra { background: #2a2a3e; padding: 15px; border-radius: 12px; margin-top: 15px; color: #ddd; font-size: 13px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Ecosystem</h1>
                <p>Extrae contenido automáticamente desde cualquier enlace o PDF</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo o https://ejemplo.com/documento.pdf">
                <button onclick="generarContenido()">🚀 Extraer Contenido</button>
                <div class="loading" id="loading">⏳ Extrayendo contenido del enlace...</div>
            </div>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
        async function generarContenido() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultado').style.display = 'none';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url })
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
                    <div class="card-header">📋 INFORMACIÓN EXTRAÍDA</div>
                    <div class="card-body">
                        <span class="categoria-badge">📁 ${data.categoria}</span>
                        <span class="categoria-badge" style="background:#e67e22;">🔥 Viralidad: ${data.viralidad}/10</span>
                        <h3 style="color: white; margin: 15px 0;">${data.titulo}</h3>
                        <div class="info-extra">
                            <strong>📝 Resumen del artículo:</strong><br>
                            ${data.resumen}
                        </div>
                        <div class="info-extra" style="margin-top: 10px;">
                            <strong>🔑 Puntos clave:</strong><br>
                            • ${data.puntos_clave[0] || 'No disponible'}<br>
                            • ${data.puntos_clave[1] || 'No disponible'}<br>
                            • ${data.puntos_clave[2] || 'No disponible'}
                        </div>
                        <div class="info-extra" style="margin-top: 10px;">
                            <strong>📄 Texto extraído (primeros 500 caracteres):</strong><br>
                            ${data.texto_completo ? data.texto_completo.substring(0, 500) + '...' : 'No disponible'}
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📱 TEXTO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="14" readonly style="width:100%;">${data.texto_instagram}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar para Instagram</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📘 TEXTO PARA FACEBOOK</div>
                    <div class="card-body">
                        <textarea id="textoFacebook" rows="8" readonly style="width:100%;">${data.texto_facebook}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoFacebook')">📋 Copiar para Facebook</button>
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
            alert('✅ Texto copiado al portapapeles');
        }
        </script>
    </body>
    </html>
    """


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    
    # Extraer contenido usando múltiples métodos
    contenido = extraer_contenido_inteligente(enlaces[0])
    
    if not contenido or not contenido.get('exito'):
        error_msg = contenido.get('error', 'No se pudo extraer el contenido') if contenido else 'Error desconocido'
        return jsonify({"error": error_msg}), 400
    
    # Clasificar categoría usando el texto completo
    categoria, viralidad = clasificar_categoria(
        contenido.get('titulo', ''), 
        contenido.get('texto_completo', '')
    )
    
    # Generar textos para redes
    textos = generar_textos_redes(
        contenido.get('titulo', ''),
        contenido.get('texto_completo', ''),
        categoria,
        viralidad
    )
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido.get('titulo', 'Sin título'),
        "resumen": textos['resumen'],
        "puntos_clave": textos['puntos_clave'],
        "texto_instagram": textos['texto_instagram'],
        "texto_facebook": textos['texto_facebook'],
        "texto_completo": contenido.get('texto_completo', '')
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
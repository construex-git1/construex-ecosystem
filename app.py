"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN CORREGIDA
======================================================================
"""

import os
import re
import requests
import json
import time
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')  # Cambiado a flash (más rápido y estable)

IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)


def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)


def leer_contenido_completo_url(url):
    """Extrae TODO el texto de la URL sin límites de tamaño"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'es-ES,es;q=0.9'
        }
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Eliminar elementos no deseados
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "form"]):
            element.decompose()
        
        # Buscar contenido principal
        contenido_principal = None
        for selector in ['article', 'main', '.post-content', '.article-content', '.entry-content', '#content', '.content']:
            elemento = soup.select_one(selector)
            if elemento:
                contenido_principal = elemento
                break
        
        if contenido_principal:
            texto = contenido_principal.get_text()
        else:
            texto = soup.get_text()
        
        # Limpiar texto
        texto = ' '.join(texto.split())
        
        # Extraer título
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        # Extraer fecha
        fecha = ""
        selectores_fecha = ['time', '[datetime]', '.date', '.published', '.post-date']
        for selector in selectores_fecha:
            elemento = soup.select_one(selector)
            if elemento:
                fecha = elemento.text.strip()
                if fecha:
                    break
        
        return {
            "exito": True,
            "titulo": titulo,
            "texto_completo": texto[:10000],
            "fecha_publicacion": fecha,
            "url": url,
            "dominio": urlparse(url).netloc
        }
        
    except Exception as e:
        return {"exito": False, "error": str(e)}


def analizar_noticia_con_gemini(titulo, texto_completo, url):
    """Usa Gemini para analizar la noticia"""
    
    prompt = f"""
    Analiza la siguiente noticia y extrae la información más importante.
    
    TÍTULO: {titulo}
    
    TEXTO DE LA NOTICIA:
    {texto_completo[:8000]}
    
    Responde SOLO con JSON en este formato. Si no encuentras algo, déjalo vacío:
    
    {{
        "resumen": "Resumen corto de la noticia (2-3 líneas)",
        "fecha": "Fecha del evento si aparece",
        "lugar": "Lugar si aparece",
        "cifras": ["cifra1", "cifra2"],
        "protagonistas": ["persona1", "persona2"],
        "contexto": "Contexto breve",
        "impacto": "Impacto potencial"
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        
        # Limpiar JSON
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        elif "```" in texto:
            texto = texto.split("```")[1].split("```")[0]
        
        return json.loads(texto.strip())
        
    except Exception as e:
        print(f"Error Gemini: {e}")
        return {
            "resumen": texto_completo[:300],
            "fecha": "",
            "lugar": "",
            "cifras": [],
            "protagonistas": [],
            "contexto": "",
            "impacto": ""
        }


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


def generar_texto_redes(titulo, analisis, categoria, viralidad):
    """Genera texto para redes sociales"""
    
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
    impacto = analisis.get('impacto', '')
    
    texto_instagram = f"""{emoji} {titulo[:70]} {emoji}

📌 {resumen}

{chr(10).join([f'💰 {c}' for c in cifras[:2]]) if cifras else ''}

📍 {lugar}
📅 {fecha}

✨ {impacto[:150] if impacto else ''}

💾 GUARDA este post
👥 COMPARTE con alguien

#{categoria.replace(' ', '')} #Construex #Noticias #Informacion
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
        <title>Construex - Analizador de Noticias</title>
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
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; background: #9C27B0; margin-right: 10px; }
            .info-box { background: #2a2a3e; padding: 15px; border-radius: 12px; margin-top: 15px; color: #ddd; font-size: 14px; line-height: 1.5; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Ecosystem</h1>
                <p>Analiza noticias y genera contenido para redes sociales</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
                <button onclick="analizarNoticia()">🚀 Analizar Noticia</button>
                <div class="loading" id="loading">⏳ Leyendo y analizando la noticia...</div>
            </div>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
        async function analizarNoticia() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultado').style.display = 'none';
            
            try {
                const response = await fetch('/analizar', {
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
                        
                        <div class="info-box">
                            <strong>📝 RESUMEN</strong><br>
                            ${data.analisis.resumen || 'No disponible'}
                        </div>
                        
                        ${data.analisis.fecha ? `<div class="info-box"><strong>📅 FECHA:</strong><br>${data.analisis.fecha}</div>` : ''}
                        ${data.analisis.lugar ? `<div class="info-box"><strong>📍 LUGAR:</strong><br>${data.analisis.lugar}</div>` : ''}
                        ${data.analisis.cifras && data.analisis.cifras.length ? `<div class="info-box"><strong>💰 CIFRAS CLAVE:</strong><br>${data.analisis.cifras.join('<br>')}</div>` : ''}
                        ${data.analisis.contexto ? `<div class="info-box"><strong>🎯 CONTEXTO:</strong><br>${data.analisis.contexto}</div>` : ''}
                        ${data.analisis.impacto ? `<div class="info-box"><strong>⚡ IMPACTO:</strong><br>${data.analisis.impacto}</div>` : ''}
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📱 CONTENIDO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="12" readonly style="width:100%;">${data.texto_instagram}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar para Instagram</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📘 CONTENIDO PARA FACEBOOK</div>
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
            alert('✅ Copiado al portapapeles');
        }
        </script>
    </body>
    </html>
    """


@app.route('/analizar', methods=['POST'])
def analizar():
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "No hay URL"}), 400
    
    # 1. Extraer contenido completo
    contenido = leer_contenido_completo_url(url)
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    # 2. Clasificar categoría
    categoria, viralidad = clasificar_categoria(contenido['titulo'], contenido['texto_completo'])
    
    # 3. Analizar con Gemini
    analisis = analizar_noticia_con_gemini(contenido['titulo'], contenido['texto_completo'], url)
    
    # 4. Generar textos para redes
    texto_instagram, texto_facebook = generar_texto_redes(
        contenido['titulo'], analisis, categoria, viralidad
    )
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "analisis": analisis,
        "texto_instagram": texto_instagram,
        "texto_facebook": texto_facebook
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
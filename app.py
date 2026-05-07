"""
======================================================================
         CONSTRUEX ECOSYSTEM - LECTURA Y COMPRENSIÓN COMPLETA
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
    gemini_model = genai.GenerativeModel('gemini-1.5-pro')  # Modelo con 1M de contexto

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
        
        # Buscar contenido principal por selectores comunes
        contenido_principal = None
        
        # Intentar encontrar el artículo
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
        
        # Extraer metadatos
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        # Extraer fecha
        fecha = ""
        selectores_fecha = ['time', '[datetime]', '.date', '.published', '.post-date', 'meta[property="article:published_time"]']
        for selector in selectores_fecha:
            elemento = soup.select_one(selector)
            if elemento:
                if selector.startswith('meta'):
                    fecha = elemento.get('content', '')
                else:
                    fecha = elemento.text.strip()
                if fecha:
                    break
        
        return {
            "exito": True,
            "titulo": titulo,
            "texto_completo": texto[:15000],  # 15k caracteres es suficiente para noticias
            "fecha_publicacion": fecha,
            "url": url,
            "dominio": urlparse(url).netloc
        }
        
    except Exception as e:
        return {"exito": False, "error": str(e)}


def analizar_noticia_con_gemini(titulo, texto_completo, url):
    """Usa Gemini para analizar la noticia como un periodista humano"""
    
    prompt = f"""
    Eres un periodista experto y analista de tendencias. Analiza la siguiente noticia y extrae información clave como lo haría un humano que lee el artículo completo.
    
    TÍTULO: {titulo}
    URL: {url}
    
    TEXTO COMPLETO DE LA NOTICIA:
    {texto_completo[:12000]}
    
    Por favor, responde con un JSON EXACTAMENTE con esta estructura:
    
    {{
        "resumen_ejecutivo": "Resumen de 3-4 líneas explicando DE QUÉ TRATA la noticia (qué pasó, cuándo, dónde, quiénes están involucrados)",
        "datos_clave": {{
            "fecha": "Fecha clave del evento si aparece en la noticia",
            "lugar": "Lugar donde ocurre el evento",
            "protagonistas": ["persona1", "persona2"],
            "cifras": ["cifra1", "cifra2"],
            "plazos": ["fecha límite o plazo importante"]
        }},
        "contexto": "Explicación del contexto: por qué es importante esta noticia ahora",
        "impacto": "Impacto potencial en el sector o la sociedad",
        "puntos_clave_para_viralizar": [
            "dato sorprendente 1",
            "dato sorprendente 2", 
            "frase impactante 3",
            "conclusión relevante 4"
        ],
        "sugerencia_angulo_viral": "Un ángulo específico para hacer viral esta noticia (ej: 'Las 3 cosas que no sabías sobre...', 'El dato que cambiará tu forma de ver...')",
        "hashtags_sugeridos": ["#Hashtag1", "#Hashtag2", "#Hashtag3", "#Hashtag4", "#Hashtag5"]
    }}
    
    IMPORTANTE: No inventes información. Si algo no aparece en el texto, déjalo vacío.
    Los puntos clave para viralizar deben ser DATOS REALES y SORPRENDENTES de la noticia.
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error en análisis Gemini: {e}")
        return None


def generar_texto_viral(analisis, categoria, viralidad):
    """Genera texto optimizado para redes basado en el análisis real de la noticia"""
    
    emojis = {
        "Construccion": "🏗️",
        "Emprendimiento": "🚀",
        "Construex University": "🎓",
        "Salud": "💪",
        "Automejora": "🌟"
    }
    emoji = emojis.get(categoria, "📚")
    
    # Extraer datos clave del análisis
    puntos = analisis.get('puntos_clave_para_viralizar', [])
    datos = analisis.get('datos_clave', {})
    contexto = analisis.get('contexto', '')
    impacto = analisis.get('impacto', '')
    angulo = analisis.get('sugerencia_angulo_viral', '')
    
    # Construir texto para Instagram
    instagram_text = f"""{emoji} {angulo or analisis.get('resumen_ejecutivo', '')[:60]} {emoji}

🔥 {analisis.get('resumen_ejecutivo', '')}

📊 DATOS CLAVE:
{chr(10).join([f'• {p}' for p in puntos[:3]]) if puntos else ''}

📍 {datos.get('lugar', '')}
📅 {datos.get('fecha', '')}
💰 {datos.get('cifras', [''])[0] if datos.get('cifras') else ''}

{contexto[:200] if contexto else ''}

✨ {impacto[:150] if impacto else ''}

💾 GUARDA este post
👥 COMPARTE con alguien

{' '.join(analisis.get('hashtags_sugeridos', [f'#{categoria}', '#Construex', '#Noticias', '#Informacion'])[:10])}
"""
    
    # Texto para Facebook (más formal)
    facebook_text = f"""{angulo or analisis.get('resumen_ejecutivo', '')}

{analisis.get('resumen_ejecutivo', '')}

📌 PUNTOS CLAVE:
{chr(10).join([f'✅ {p}' for p in puntos[:4]]) if puntos else ''}

{contexto[:300] if contexto else ''}

{impacto[:200] if impacto else ''}

{' '.join(analisis.get('hashtags_sugeridos', [f'#{categoria}', '#Construex'])[:5])}
"""
    
    return {
        "instagram": instagram_text,
        "facebook": facebook_text
    }


def clasificar_categoria(titulo, texto):
    texto_lower = f"{titulo} {texto[:500]}".lower()
    
    if any(p in texto_lower for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal", "arquitect", "construcción"]):
        return "Construccion", 9
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "inversion", "startup", "empleo", "trabajo"]):
        return "Emprendimiento", 8
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion", "certificacion", "estudio", "universidad"]):
        return "Construex University", 7
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar", "dieta", "ejercicio", "hospital"]):
        return "Salud", 7
    return "Automejora", 6


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
            input { width: 80%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-left: 10px; }
            button:hover { transform: scale(1.02); }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; margin-bottom: 20px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; font-size: 18px; }
            .card-body { padding: 20px; }
            textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; resize: vertical; margin-bottom: 10px; }
            .copy-btn { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; background: #9C27B0; margin-right: 10px; }
            .info-box { background: #2a2a3e; padding: 15px; border-radius: 12px; margin-top: 15px; color: #ddd; font-size: 14px; line-height: 1.5; }
            .datos-destacados { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
            .dato-chip { background: #2a2a3e; padding: 8px 15px; border-radius: 20px; font-size: 13px; border-left: 3px solid #FFD700; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Ecosystem</h1>
                <p>Analiza noticias y genera contenido viral para redes sociales</p>
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
                            <strong>📝 RESUMEN EJECUTIVO</strong><br>
                            ${data.analisis.resumen_ejecutivo || 'No disponible'}
                        </div>
                        
                        <div class="datos-destacados">
                            ${data.analisis.datos_clave?.fecha ? `<div class="dato-chip">📅 ${data.analisis.datos_clave.fecha}</div>` : ''}
                            ${data.analisis.datos_clave?.lugar ? `<div class="dato-chip">📍 ${data.analisis.datos_clave.lugar}</div>` : ''}
                            ${(data.analisis.datos_clave?.cifras || []).map(c => `<div class="dato-chip">💰 ${c}</div>`).join('')}
                        </div>
                        
                        <div class="info-box">
                            <strong>🎯 CONTEXTO</strong><br>
                            ${data.analisis.contexto || 'No disponible'}
                        </div>
                        
                        <div class="info-box">
                            <strong>⚡ IMPACTO POTENCIAL</strong><br>
                            ${data.analisis.impacto || 'No disponible'}
                        </div>
                        
                        <div class="info-box">
                            <strong>🔥 PUNTOS CLAVE PARA VIRALIZAR</strong><br>
                            ${(data.analisis.puntos_clave_para_viralizar || []).map((p, i) => `${i+1}️⃣ ${p}<br>`).join('')}
                        </div>
                        
                        <div class="info-box">
                            <strong>💡 SUGERENCIA DE ÁNGULO VIRAL</strong><br>
                            ${data.analisis.sugerencia_angulo_viral || 'No disponible'}
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📱 CONTENIDO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="16" readonly style="width:100%;">${data.texto_instagram}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar para Instagram</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📘 CONTENIDO PARA FACEBOOK</div>
                    <div class="card-body">
                        <textarea id="textoFacebook" rows="10" readonly style="width:100%;">${data.texto_facebook}</textarea>
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
    
    # 3. Analizar con Gemini (como periodista)
    analisis = analizar_noticia_con_gemini(contenido['titulo'], contenido['texto_completo'], url)
    
    if not analisis:
        return jsonify({"error": "No se pudo analizar la noticia"}), 500
    
    # 4. Generar textos virales
    textos = generar_texto_viral(analisis, categoria, viralidad)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "analisis": analisis,
        "texto_instagram": textos['instagram'],
        "texto_facebook": textos['facebook']
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
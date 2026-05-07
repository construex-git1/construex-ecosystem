"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN INFOGRAFÍA PROFESIONAL
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


def leer_contenido_url(url):
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        # Extraer más contenido para mejor análisis
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        descripcion = meta_desc.get('content', '')[:1500] if meta_desc else ""
        
        # Extraer texto principal del artículo
        articulo = soup.find('article') or soup.find('main') or soup.find('body')
        if articulo:
            for script in articulo(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            texto_completo = articulo.get_text()
            texto_completo = ' '.join(texto_completo.split())[:2000]
        else:
            texto_completo = descripcion
        
        return {
            "exito": True, 
            "titulo": titulo, 
            "descripcion": descripcion, 
            "texto_completo": texto_completo,
            "dominio": urlparse(url).netloc
        }
    except Exception as e:
        return {"exito": False, "error": str(e)}


def generar_infografia_con_gemini(titulo, texto_completo, categoria):
    """Genera una infografía completa usando Gemini"""
    
    prompt = f"""
    Eres un experto en crear infografías educativas. Basado en el siguiente artículo, crea una infografía detallada.
    
    TÍTULO: {titulo}
    CATEGORÍA: {categoria}
    CONTENIDO COMPLETO: {texto_completo[:2000]}
    
    Genera EXACTAMENTE este formato JSON para crear una infografía profesional:
    
    {{
        "titulo_principal": "Título llamativo de la infografía (máx 60 caracteres)",
        "introduccion": "Frase de impacto que resuma el tema (1-2 líneas)",
        
        "datos_clave": [
            {{"icono": "📊", "titulo": "Dato 1", "valor": "valor numérico o porcentaje", "descripcion": "explicación breve"}},
            {{"icono": "📈", "titulo": "Dato 2", "valor": "valor", "descripcion": "explicación"}},
            {{"icono": "🎯", "titulo": "Dato 3", "valor": "valor", "descripcion": "explicación"}}
        ],
        
        "puntos_clave": [
            "Punto clave 1 con contexto y detalle (máx 120 caracteres)",
            "Punto clave 2 con contexto y detalle (máx 120 caracteres)",
            "Punto clave 3 con contexto y detalle (máx 120 caracteres)",
            "Punto clave 4 con contexto y detalle (máx 120 caracteres)"
        ],
        
        "tendencia": "Análisis de la tendencia principal del artículo (1-2 líneas)",
        "aplicacion_practica": "Cómo aplicar este conocimiento en el sector (1-2 líneas)",
        "fuente": "{fuente}",
        "fecha": "{fecha_actual}"
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
        return generar_infografia_fallback(titulo, texto_completo, categoria)


def generar_infografia_fallback(titulo, texto, categoria):
    """Infografía de respaldo"""
    palabras = texto.split()[:50]
    resumen = ' '.join(palabras)
    
    return {
        "titulo_principal": titulo[:55],
        "introduccion": resumen[:150],
        "datos_clave": [
            {"icono": "📊", "titulo": "Impacto", "valor": "Significativo", "descripcion": "El tema tiene gran relevancia"},
            {"icono": "📈", "titulo": "Tendencia", "valor": "En crecimiento", "descripcion": "Cada vez más relevante"},
            {"icono": "🎯", "titulo": "Clave", "valor": "Prioritario", "descripcion": "Aspecto fundamental"}
        ],
        "puntos_clave": [
            f"✅ {resumen[:100]}",
            f"📌 Aspecto relevante del artículo",
            f"💡 Información importante a considerar",
            f"🔑 Conclusión principal del contenido"
        ],
        "tendencia": "Este tema está ganando relevancia en el sector",
        "aplicacion_practica": f"Aplica este conocimiento en {categoria} para mejores resultados",
        "fuente": "Análisis Construex",
        "fecha": time.strftime("%d/%m/%Y")
    }


def generar_html_infografia(infografia, categoria):
    """Genera HTML profesional de la infografía"""
    
    colores = {
        "Construccion": {"principal": "#795548", "secundario": "#5D4037", "texto": "#FFFFFF"},
        "Emprendimiento": {"principal": "#FF9800", "secundario": "#E65100", "texto": "#FFFFFF"},
        "Construex University": {"principal": "#2196F3", "secundario": "#0D47A1", "texto": "#FFFFFF"},
        "Salud": {"principal": "#4CAF50", "secundario": "#1B5E20", "texto": "#FFFFFF"},
        "Automejora": {"principal": "#9C27B0", "secundario": "#4A148C", "texto": "#FFFFFF"}
    }
    color = colores.get(categoria, {"principal": "#667eea", "secundario": "#764ba2", "texto": "#FFFFFF"})
    
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', infografia['titulo_principal'][:30]).replace(' ', '_')
    filename = f"infografia_{timestamp}_{nombre}.html"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    # Generar HTML de la infografía
    datos_html = ""
    for dato in infografia.get('datos_clave', []):
        datos_html += f"""
        <div style="text-align: center; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 12px;">
            <div style="font-size: 36px;">{dato.get('icono', '📊')}</div>
            <div style="font-size: 24px; font-weight: bold;">{dato.get('titulo', '')}</div>
            <div style="font-size: 32px; color: #FFD700; margin: 10px 0;">{dato.get('valor', '')}</div>
            <div style="font-size: 14px; opacity: 0.9;">{dato.get('descripcion', '')}</div>
        </div>
        """
    
    puntos_html = ""
    for i, punto in enumerate(infografia.get('puntos_clave', []), 1):
        puntos_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 10px;">
            <div style="font-size: 28px; min-width: 50px;">{i}️⃣</div>
            <div style="font-size: 16px; line-height: 1.4;">{punto}</div>
        </div>
        """
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Construex - {infografia['titulo_principal']}</title>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: linear-gradient(135deg, {color['principal']} 0%, {color['secundario']} 100%);
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
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 30px;
            overflow: hidden;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .header {{
            background: rgba(0,0,0,0.3);
            padding: 30px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .logo {{
            font-size: 14px;
            letter-spacing: 2px;
            margin-bottom: 10px;
            opacity: 0.7;
        }}
        .titulo {{
            font-size: 36px;
            font-weight: bold;
            color: white;
            margin-bottom: 15px;
        }}
        .introduccion {{
            font-size: 18px;
            color: rgba(255,255,255,0.9);
            max-width: 80%;
            margin: 0 auto;
        }}
        .contenido {{
            padding: 40px;
        }}
        .datos-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        .seccion {{
            margin-bottom: 40px;
        }}
        .seccion-titulo {{
            font-size: 24px;
            font-weight: bold;
            color: #FFD700;
            margin-bottom: 20px;
            border-left: 4px solid #FFD700;
            padding-left: 15px;
        }}
        .footer {{
            background: rgba(0,0,0,0.3);
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: rgba(255,255,255,0.6);
        }}
        .categoria-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 15px;
        }}
        @media (max-width: 768px) {{
            .datos-grid {{ grid-template-columns: 1fr; }}
            .titulo {{ font-size: 28px; }}
            .contenido {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="infografia">
        <div class="header">
            <div class="logo">🏗️ CONSTRUEX ECOSYSTEM</div>
            <div class="categoria-badge">📁 {categoria.upper()}</div>
            <div class="titulo">{infografia['titulo_principal']}</div>
            <div class="introduccion">{infografia['introduccion']}</div>
        </div>
        
        <div class="contenido">
            <div class="datos-grid">
                {datos_html}
            </div>
            
            <div class="seccion">
                <div class="seccion-titulo">📌 PUNTOS CLAVE</div>
                {puntos_html}
            </div>
            
            <div class="seccion">
                <div class="seccion-titulo">📈 TENDENCIA</div>
                <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px;">
                    {infografia.get('tendencia', '')}
                </div>
            </div>
            
            <div class="seccion">
                <div class="seccion-titulo">💡 APLICACIÓN PRÁCTICA</div>
                <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px;">
                    {infografia.get('aplicacion_practica', '')}
                </div>
            </div>
        </div>
        
        <div class="footer">
            Fuente: {infografia.get('fuente', 'Construex')} | {infografia.get('fecha', '')}<br>
            📌 Guarda esta infografía • 👥 Compártela • 💬 Déjanos tu opinión
        </div>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return f"/imagenes/{filename}"


def generar_imagen_leonardo_web(titulo, categoria):
    """Genera URL para imagen de calidad profesional (para que el usuario genere en Leonardo.ai web)"""
    
    prompts_por_categoria = {
        "Construccion": f"Professional architectural photography, modern building construction site, {titulo[:80]}, high resolution, 4K, cinematic lighting, realistic, architectural digest style",
        "Emprendimiento": f"Professional corporate photography, modern office or startup scene, {titulo[:80]}, high resolution, 4K, cinematic lighting, professional, business magazine style",
        "Construex University": f"Professional educational photography, modern classroom or learning environment, {titulo[:80]}, high resolution, 4K, clean, academic style",
        "Salud": f"Professional healthcare photography, modern medical or wellness scene, {titulo[:80]}, high resolution, 4K, clean, fresh, professional",
        "Automejora": f"Professional motivational photography, personal development scene, {titulo[:80]}, high resolution, 4K, inspiring, clean"
    }
    
    prompt = prompts_por_categoria.get(categoria, f"Professional photography of {categoria}, {titulo[:80]}, high resolution, 4K")
    
    # Enlace a Leonardo.ai con el prompt pre-cargado
    leonardo_url = f"https://app.leonardo.ai/image-generation?prompt={requests.utils.quote(prompt)}"
    
    return leonardo_url


def clasificar_categoria(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal"]):
        return "Construccion"
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento"
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University"
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud"
    return "Automejora"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Infografías</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; min-height: 100vh; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; }
            .header h1 { font-size: 36px; margin-bottom: 10px; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; text-align: center; }
            input { width: 70%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-left: 10px; }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; margin-bottom: 20px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; }
            .card-body { padding: 20px; }
            iframe { width: 100%; min-height: 600px; border: none; border-radius: 12px; }
            .btn-copiar { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; }
            .leonardo-btn { background: #27ae60; display: inline-block; padding: 12px 24px; border-radius: 12px; color: white; text-decoration: none; margin-top: 15px; }
            .info-box { background: #2a2a3e; padding: 15px; border-radius: 12px; margin-top: 15px; color: #ddd; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Infografías</h1>
                <p>Generador profesional de infografías a partir de cualquier enlace</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo" style="width: 60%;">
                <button onclick="generarInfografia()">🚀 Generar Infografía</button>
                <div class="loading" id="loading">⏳ Analizando artículo y generando infografía profesional...</div>
            </div>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
        async function generarInfografia() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultado').style.display = 'none';
            
            try {
                const response = await fetch('/generar', {
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
                    <div class="card-header">📊 INFOGRAFÍA GENERADA</div>
                    <div class="card-body">
                        <iframe src="${data.infografia_url}"></iframe>
                        <div style="margin-top: 15px;">
                            <button class="btn-copiar" onclick="window.open('${data.infografia_url}', '_blank')">📤 Abrir Infografía</button>
                            <button class="btn-copiar" onclick="window.location.href='${data.infografia_url}'">💾 Descargar HTML</button>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">🎨 GENERAR IMAGEN PROFESIONAL (Leonardo.ai)</div>
                    <div class="card-body">
                        <p style="color: #ddd; margin-bottom: 15px;">Para una imagen de calidad profesional, haz clic en el enlace y genera la imagen con esta IA:</p>
                        <a href="${data.leonardo_url}" target="_blank" class="leonardo-btn">🎨 Abrir Leonardo.ai con el prompt listo</a>
                        <div class="info-box">
                            💡 <strong>Instrucciones:</strong>
                            <br>1. Al abrir Leonardo.ai, el prompt ya está precargado
                            <br>2. Haz clic en "Generate" para crear tu imagen profesional
                            <br>3. Descarga la imagen y úsala junto con la infografía
                            <br>4. Leonardo.ai tiene créditos gratis diarios
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📱 TEXTO LISTO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="10" readonly style="width:100%; background:#2a2a3e; color:white; border:none; padding:12px; border-radius:8px;">${data.texto_instagram}</textarea>
                        <button class="btn-copiar" onclick="copiarTexto('textoInstagram')">📋 Copiar para Instagram</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">📘 TEXTO PARA FACEBOOK</div>
                    <div class="card-body">
                        <textarea id="textoFacebook" rows="8" readonly style="width:100%; background:#2a2a3e; color:white; border:none; padding:12px; border-radius:8px;">${data.texto_facebook}</textarea>
                        <button class="btn-copiar" onclick="copiarTexto('textoFacebook')">📋 Copiar para Facebook</button>
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


@app.route('/generar', methods=['POST'])
def generar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    
    contenido = leer_contenido_url(enlaces[0])
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    categoria = clasificar_categoria(contenido['titulo'], contenido['descripcion'])
    
    # Generar infografía con Gemini
    infografia = generar_infografia_con_gemini(
        contenido['titulo'], 
        contenido.get('texto_completo', contenido['descripcion']), 
        categoria
    )
    
    # Generar HTML de la infografía
    infografia_url = generar_html_infografia(infografia, categoria)
    
    # Generar texto para redes sociales
    texto_instagram = f"""🔥 {infografia.get('titulo_principal', '')} 🔥

📌 {infografia.get('introduccion', '')}

📊 DATOS CLAVE:
{chr(10).join([f"{d.get('icono', '•')} {d.get('titulo', '')}: {d.get('valor', '')}" for d in infografia.get('datos_clave', [])])}

✨ {infografia.get('tendencia', '')}

💡 {infografia.get('aplicacion_practica', '')}

💾 GUARDA esta infografía
👥 COMPARTE con alguien

#{categoria} #Construex #Infografia #Educacion #Aprende
"""
    
    texto_facebook = f"""{infografia.get('titulo_principal', '')}

{infografia.get('introduccion', '')}

Datos clave:
{chr(10).join([f"• {d.get('titulo', '')}: {d.get('valor', '')}" for d in infografia.get('datos_clave', [])])}

{infografia.get('tendencia', '')}

{infografia.get('aplicacion_practica', '')}

Fuente: {infografia.get('fuente', 'Construex')}
#{categoria} #Construex
"""
    
    # Generar enlace para Leonardo.ai
    leonardo_url = generar_imagen_leonardo_web(contenido['titulo'], categoria)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "infografia_url": infografia_url,
        "leonardo_url": leonardo_url,
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
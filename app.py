"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN DEFINITIVA
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

load_dotenv()
app = Flask(__name__)

# Directorios
IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)


def extraer_noticia_completa(url):
    """Extrae el artículo completo usando newspaper3k"""
    try:
        article = Article(url, language='es')
        article.download()
        article.parse()
        
        if article.text and len(article.text) > 100:
            # Extraer metadatos adicionales
            soup = BeautifulSoup(article.html, 'html.parser')
            
            # Buscar fecha
            fecha = ""
            for tag in soup.find_all(['time', 'meta']):
                if tag.get('datetime'):
                    fecha = tag.get('datetime')
                    break
                elif tag.get('content') and 'date' in str(tag.get('property', '')):
                    fecha = tag.get('content')
                    break
            
            return {
                "exito": True,
                "titulo": article.title,
                "texto_completo": article.text[:5000],
                "fecha_publicacion": fecha or "",
                "autor": ", ".join(article.authors) if article.authors else "",
                "imagen_principal": article.top_image,
                "dominio": urlparse(url).netloc
            }
        return None
    except Exception as e:
        print(f"Error con newspaper: {e}")
        return None


def extraer_noticia_fallback(url):
    """Método manual de respaldo"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Eliminar elementos no deseados
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Buscar el artículo
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
            "texto_completo": texto[:5000],
            "fecha_publicacion": "",
            "autor": "",
            "dominio": urlparse(url).netloc
        }
    except Exception as e:
        return {"exito": False, "error": str(e)}


def extraer_noticia(url):
    """Orquesta la extracción"""
    resultado = extraer_noticia_completa(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Artículo extraído con newspaper3k")
        return resultado
    
    resultado = extraer_noticia_fallback(url)
    if resultado and resultado.get('exito'):
        print("   ✅ Artículo extraído con método manual")
        return resultado
    
    return {"exito": False, "error": "No se pudo extraer el artículo"}


def analizar_noticia(texto_completo, titulo):
    """Extrae información clave del texto"""
    # Extraer cifras (números)
    cifras = re.findall(r'\b\d+(?:\.\d+)?\s*(?:millones|millon|mil|dólares|euros|empleos|trabajadores|personas|años|días|meses)\b', texto_completo)
    cifras = list(set(cifras))[:5]
    
    # Buscar lugar (ciudades)
    lugares_encontrados = []
    ciudades = ["Portoviejo", "Manabí", "Quito", "Guayaquil", "Manta", "Cuenca", "Ambato", "Loja"]
    for ciudad in ciudades:
        if ciudad.lower() in texto_completo.lower():
            lugares_encontrados.append(ciudad)
    
    # Buscar fechas
    fechas = re.findall(r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b', texto_completo)
    fechas += re.findall(r'\b\w+\s+de\s+\d{4}\b', texto_completo)
    
    # Generar resumen (primeras 3-4 oraciones)
    oraciones = re.split(r'[.!?]+', texto_completo)
    resumen = '. '.join([o.strip() for o in oraciones[:4] if len(o.strip()) > 30]) + '.'
    
    # Generar puntos clave (oraciones importantes)
    puntos = []
    for o in oraciones:
        if len(o.strip()) > 50 and any(p in o.lower() for p in ["construir", "empleo", "inversión", "centro comercial", "proyecto", "millones"]):
            puntos.append(o.strip())
    puntos = puntos[:4]
    
    if len(puntos) < 3:
        puntos = [resumen[:150], resumen[150:300], resumen[300:450]] if len(resumen) > 450 else [resumen[:150], resumen[150:300]]
    
    return {
        "resumen": resumen[:500],
        "cifras": cifras,
        "lugar": lugares_encontrados[0] if lugares_encontrados else "",
        "fecha": fechas[0] if fechas else "",
        "puntos_clave": puntos
    }


def generar_imagen(titulo, categoria, index=0):
    """Genera imagen profesional para Instagram"""
    prompts = [
        f"Professional social media post for {categoria}: {titulo[:100]}. Modern, clean, professional, high quality, 4K.",
        f"Educational infographic style image about {titulo[:100]}. Professional design, corporate colors.",
        f"Inspiring social media visual for {categoria} category. High quality, modern, professional."
    ]
    prompt = prompts[index % 3]
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"img_{timestamp}_{index}_{nombre}.png"
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
    if any(p in texto_lower for p in ["construc", "centro comercial", "mall", "obra", "edificio"]):
        return "Construccion", 9
    elif any(p in texto_lower for p in ["negocio", "emprend", "empresa", "ventas", "empleo"]):
        return "Emprendimiento", 8
    elif any(p in texto_lower for p in ["curso", "aprender", "educacion"]):
        return "Construex University", 7
    elif any(p in texto_lower for p in ["salud", "medico", "bienestar"]):
        return "Salud", 7
    return "Automejora", 6


def generar_texto_instagram(titulo, analisis, categoria):
    emojis = {"Construccion": "🏗️", "Emprendimiento": "🚀", "Construex University": "🎓", "Salud": "💪", "Automejora": "🌟"}
    emoji = emojis.get(categoria, "📚")
    
    texto = f"""{emoji} {titulo[:70]} {emoji}

📌 {analisis['resumen']}

"""
    if analisis['cifras']:
        texto += f"💰 DATOS CLAVE:\n"
        for c in analisis['cifras'][:3]:
            texto += f"   • {c}\n"
        texto += "\n"
    
    if analisis['lugar'] or analisis['fecha']:
        texto += f"📍 {analisis['lugar']}" if analisis['lugar'] else ""
        texto += f"   📅 {analisis['fecha']}" if analisis['fecha'] else ""
        texto += "\n\n"
    
    for i, p in enumerate(analisis['puntos_clave'][:3]):
        texto += f"{['✨', '💡', '🔑'][i]} {p[:150]}\n\n"
    
    texto += """💾 GUARDA este post
👥 COMPARTE con alguien

#{} #Construex #Noticias""".format(categoria.replace(' ', ''))
    
    return texto


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Contenido</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial; background: #0f0f0f; padding: 20px; }
            .container { max-width: 1000px; margin: auto; }
            .header { background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 20px; padding: 30px; margin-bottom: 20px; color: white; text-align: center; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 20px; text-align: center; }
            input { width: 60%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; cursor: pointer; margin-left: 10px; }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; background: #1a1a2e; border-radius: 20px; padding: 20px; margin-top: 20px; }
            .card { background: #2a2a3e; border-radius: 16px; padding: 20px; margin-bottom: 20px; }
            .galeria { display: flex; gap: 15px; flex-wrap: wrap; margin-top: 15px; }
            .imagen-item { background: #1a1a2e; border-radius: 12px; padding: 10px; text-align: center; }
            .imagen-item img { width: 200px; border-radius: 12px; }
            textarea { width: 100%; background: #1a1a2e; color: white; border: none; padding: 15px; border-radius: 12px; font-family: monospace; margin: 10px 0; }
            .copy-btn { background: #3498db; padding: 8px 20px; border: none; border-radius: 8px; color: white; cursor: pointer; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; background: #9C27B0; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Ecosystem</h1>
                <p>Genera contenido profesional desde cualquier noticia</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
                <button onclick="procesar()">🚀 Generar Contenido</button>
                <div class="loading" id="loading">⏳ Leyendo la noticia y generando contenido...</div>
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
                    <span class="categoria-badge">📁 ${data.categoria}</span>
                    <span class="categoria-badge" style="background:#e67e22;">🔥 Viralidad: ${data.viralidad}/10</span>
                    <h3 style="color:white; margin:15px 0;">${data.titulo}</h3>
                    
                    <div class="galeria">
                        ${data.imagenes.map(img => `
                            <div class="imagen-item">
                                <img src="${img}">
                                <br><a href="${img}" download style="color:#3498db;">📥 Descargar</a>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div class="card">
                    <strong>📱 TEXTO PARA INSTAGRAM</strong>
                    <textarea id="textoInstagram" rows="12" readonly>${data.texto_instagram}</textarea>
                    <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar para Instagram</button>
                </div>
            `;
            
            document.getElementById('resultado').innerHTML = html;
            document.getElementById('resultado').style.display = 'block';
        }
        
        function copiarTexto(id) {
            const textarea = document.getElementById(id);
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
    
    # 1. Extraer noticia completa
    noticia = extraer_noticia(url)
    if not noticia['exito']:
        return jsonify({"error": noticia.get('error', 'No se pudo extraer')}), 400
    
    # 2. Analizar contenido
    analisis = analizar_noticia(noticia['texto_completo'], noticia['titulo'])
    
    # 3. Clasificar categoría
    categoria, viralidad = clasificar_categoria(noticia['titulo'], noticia['texto_completo'])
    
    # 4. Generar imágenes (3 imágenes)
    imagenes = []
    for i in range(3):
        img = generar_imagen(noticia['titulo'], categoria, i)
        if img:
            imagenes.append(img)
    
    # 5. Generar texto para Instagram
    texto_instagram = generar_texto_instagram(noticia['titulo'], analisis, categoria)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": noticia['titulo'],
        "texto_instagram": texto_instagram,
        "imagenes": imagenes
    })


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
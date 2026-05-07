import os
import re
import requests
import time
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

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
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        descripcion = meta_desc.get('content', '')[:500] if meta_desc else ""
        
        if not descripcion:
            for script in soup(["script", "style"]):
                script.decompose()
            texto = soup.get_text()
            descripcion = ' '.join(texto.split())[:500]
        
        return {"exito": True, "titulo": titulo, "descripcion": descripcion, "dominio": urlparse(url).netloc}
    except Exception as e:
        return {"exito": False, "error": str(e)}


def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "edificio", "canal"]):
        return "Construccion", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud", 6
    return "Automejora", 5


def generar_html_instagram(titulo, resumen, categoria, enlace):
    """Genera un HTML que simula una imagen de Instagram (funciona sin Pillow)"""
    
    colores = {
        "Construccion": "#795548",
        "Emprendimiento": "#FF9800", 
        "Construex University": "#2196F3",
        "Salud": "#4CAF50",
        "Automejora": "#9C27B0"
    }
    color = colores.get(categoria, "#3498db")
    
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"instagram_{timestamp}_{nombre}.html"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Construex - {categoria}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: {color};
            font-family: 'Segoe UI', Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .card {{
            width: 500px;
            background: white;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            margin: 20px;
        }}
        .header {{
            background: {color};
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 14px;
            letter-spacing: 2px;
        }}
        .content {{
            padding: 30px;
        }}
        .categoria {{
            background: {color};
            color: white;
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 15px;
        }}
        .titulo {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            line-height: 1.3;
        }}
        .resumen {{
            color: #555;
            line-height: 1.6;
            margin-bottom: 25px;
        }}
        .cta {{
            background: {color};
            color: white;
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .hashtags {{
            color: #999;
            font-size: 12px;
            text-align: center;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 15px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>🏗️ CONSTRUEX ECOSYSTEM</h1>
        </div>
        <div class="content">
            <div class="categoria">📁 {categoria.upper()}</div>
            <div class="titulo">{titulo[:80]}</div>
            <div class="resumen">{resumen[:400]}...</div>
            <div class="cta">
                ✨ Aprende más en Construex ✨
            </div>
            <div class="hashtags">
                #{categoria.replace(' ', '')} #Construex #Educacion #Aprendizaje
            </div>
        </div>
        <div class="footer">
            👉 Comparte este contenido | Fuente: {enlace[:50]}...
        </div>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return f"/imagenes/{filename}"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Ecosystem</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; }
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            .preview { margin-top: 15px; text-align: center; }
            iframe { width: 100%; height: 600px; border: none; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Genera contenido listo para Instagram desde cualquier enlace</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <br>
            <button onclick="procesar()">🚀 Generar Contenido</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div>⏳ Procesando...</div>';
                
                try {
                    const response = await fetch('/procesar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mensaje: url })
                    });
                    const data = await response.json();
                    
                    if (data.exito) {
                        let html = `<div style="background:#d4edda; padding:10px; border-radius:5px; margin-bottom:15px;">`;
                        html += `<strong>📁 Categoría:</strong> ${data.categoria}<br>`;
                        html += `<strong>🔥 Viralidad:</strong> ${data.viralidad}/10<br>`;
                        html += `<strong>📝 Título:</strong> ${data.titulo}</div>`;
                        
                        if (data.html_url) {
                            html += `<div class="preview">`;
                            html += `<strong>🖼️ Contenido listo para Instagram:</strong><br>`;
                            html += `<iframe src="${data.html_url}"></iframe>`;
                            html += `<br><a href="${data.html_url}" target="_blank" style="display: inline-block; margin-top: 10px; background: #3498db; color: white; padding: 8px 16px; border-radius: 5px; text-decoration: none;">📥 Ver/Guardar</a>`;
                            html += `<p style="font-size:12px; color:#666; margin-top:10px;">💡 Toma una captura de pantalla para publicar en Instagram</p>`;
                            html += `</div>`;
                        }
                        
                        resultadoDiv.innerHTML = html;
                        document.getElementById('urlInput').value = '';
                    } else {
                        resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
                    }
                } catch(e) {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</code> ${e.message}</div>`;
                }
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
    
    contenido = leer_contenido_url(enlaces[0])
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    categoria, viralidad = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    html_url = generar_html_instagram(contenido['titulo'], contenido['descripcion'], categoria, enlaces[0])
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "html_url": html_url
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
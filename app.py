"""
======================================================================
         CONSTRUEX ECOSYSTEM - PNG REAL PARA INSTAGRAM
======================================================================
"""

import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)


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
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "edificio"]):
        return "Construccion", 8, "#795548"
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas"]):
        return "Emprendimiento", 7, "#FF9800"
    elif any(p in texto for p in ["curso", "aprender", "educacion"]):
        return "Construex University", 6, "#2196F3"
    elif any(p in texto for p in ["salud", "medico", "bienestar"]):
        return "Salud", 6, "#4CAF50"
    return "Automejora", 5, "#9C27B0"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Imágenes para Instagram</title>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
            .container { max-width: 550px; width: 100%; }
            .card { background: white; border-radius: 20px; padding: 25px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
            h1 { color: #2c3e50; font-size: 24px; margin-bottom: 5px; }
            .sub { color: #7f8c8d; font-size: 14px; margin-bottom: 20px; }
            input { width: 100%; padding: 14px; border: 2px solid #e0e0e0; border-radius: 12px; font-size: 14px; margin-bottom: 15px; }
            button { width: 100%; background: #27ae60; color: white; padding: 14px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s; }
            button:hover { transform: scale(1.02); background: #219a52; }
            .loading { text-align: center; padding: 20px; color: #666; display: none; }
            .preview { margin-top: 20px; display: none; }
            .preview h3 { margin-bottom: 15px; color: #2c3e50; }
            .capture-area { background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .info-box { background: #e8f4f8; padding: 12px; border-radius: 10px; margin-top: 15px; font-size: 13px; color: #555; }
            .download-btn { background: #3498db; margin-top: 15px; }
            .download-btn:hover { background: #2980b9; }
            .categoria-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-bottom: 10px; }
            .error { color: red; text-align: center; padding: 15px; display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>🏗️ Construex Ecosystem</h1>
                <div class="sub">Genera imágenes listas para Instagram</div>
                
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
                <button id="generateBtn">🚀 Generar Imagen para Instagram</button>
                
                <div class="loading" id="loading">⏳ Analizando contenido y generando imagen...</div>
                <div class="error" id="error"></div>
            </div>
            
            <div class="preview" id="preview">
                <div class="capture-area" id="captureArea">
                    <div id="poster" style="width: 1080px; height: 1080px; position: relative; font-family: 'Segoe UI', Arial, sans-serif;">
                        <!-- El contenido se llena con JS -->
                    </div>
                </div>
                <div class="info-box">
                    💡 La imagen es de 1080x1080, tamaño perfecto para Instagram.
                    <br>📱 Haz clic en "Descargar PNG" para guardarla en tu dispositivo.
                </div>
                <button class="download-btn" id="downloadBtn">📥 Descargar Imagen PNG</button>
            </div>
        </div>

        <script>
        const colores = {
            "Construccion": "#795548",
            "Emprendimiento": "#FF9800",
            "Construex University": "#2196F3",
            "Salud": "#4CAF50",
            "Automejora": "#9C27B0"
        };
        
        const categoriasIconos = {
            "Construccion": "🏗️",
            "Emprendimiento": "🚀",
            "Construex University": "🎓",
            "Salud": "💪",
            "Automejora": "🌟"
        };
        
        document.getElementById('generateBtn').addEventListener('click', procesar);
        document.getElementById('downloadBtn').addEventListener('click', descargarImagen);
        
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { mostrarError('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('preview').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url })
                });
                const data = await response.json();
                
                if (data.exito) {
                    generarPoster(data);
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('preview').style.display = 'block';
                    document.getElementById('generateBtn').disabled = false;
                } else {
                    mostrarError(data.error);
                }
            } catch(e) {
                mostrarError('Error de conexión: ' + e.message);
            }
        }
        
        function generarPoster(data) {
            const color = colores[data.categoria] || "#3498db";
            const icono = categoriasIconos[data.categoria] || "📚";
            
            // Limitar texto para que no se desborde
            let titulo = data.titulo.length > 80 ? data.titulo.substring(0, 77) + '...' : data.titulo;
            let resumen = data.resumen.length > 300 ? data.resumen.substring(0, 297) + '...' : data.resumen;
            
            const html = `
                <div style="width: 1080px; height: 1080px; background: linear-gradient(135deg, ${color} 0%, #2c3e50 100%); display: flex; flex-direction: column; justify-content: space-between; padding: 50px; position: relative;">
                    <!-- Patrón decorativo -->
                    <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; opacity: 0.05;">
                        <svg width="100%" height="100%">
                            <defs><pattern id="dots" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse"><circle cx="20" cy="20" r="3" fill="white"/></pattern></defs>
                            <rect width="100%" height="100%" fill="url(#dots)"/>
                        </svg>
                    </div>
                    
                    <!-- Marco decorativo -->
                    <div style="position: absolute; top: 25px; left: 25px; right: 25px; bottom: 25px; border: 2px solid rgba(255,255,255,0.2); border-radius: 20px; pointer-events: none;"></div>
                    
                    <!-- Logo -->
                    <div style="text-align: center; margin-bottom: 20px;">
                        <div style="background: rgba(255,255,255,0.15); display: inline-block; padding: 10px 25px; border-radius: 50px;">
                            <span style="color: white; font-size: 28px; font-weight: bold;">🏗️ CONSTRUEX</span>
                        </div>
                    </div>
                    
                    <!-- Categoría -->
                    <div style="text-align: center; margin-bottom: 15px;">
                        <span style="background: rgba(255,255,255,0.2); padding: 8px 20px; border-radius: 30px; color: #FFD700; font-size: 20px; font-weight: bold;">
                            ${icono} ${data.categoria.toUpperCase()} ${icono}
                        </span>
                    </div>
                    
                    <!-- Línea decorativa -->
                    <div style="width: 80px; height: 3px; background: #FFD700; margin: 0 auto 25px auto; border-radius: 2px;"></div>
                    
                    <!-- Título -->
                    <div style="text-align: center; margin-bottom: 25px;">
                        <div style="color: white; font-size: 42px; font-weight: bold; line-height: 1.3; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                            ${titulo}
                        </div>
                    </div>
                    
                    <!-- Línea decorativa -->
                    <div style="width: 120px; height: 2px; background: rgba(255,255,255,0.3); margin: 0 auto 25px auto;"></div>
                    
                    <!-- Resumen -->
                    <div style="background: rgba(0,0,0,0.3); border-radius: 20px; padding: 25px; margin-bottom: 25px;">
                        <div style="color: rgba(255,255,255,0.95); font-size: 24px; line-height: 1.5; text-align: center;">
                            "${resumen.substring(0, 250)}"
                        </div>
                    </div>
                    
                    <!-- Call to Action y Hashtags -->
                    <div style="text-align: center;">
                        <div style="background: #FFD700; color: #2c3e50; padding: 12px 25px; border-radius: 50px; display: inline-block; font-weight: bold; font-size: 22px; margin-bottom: 15px;">
                            ✨ APRENDE MÁS EN CONSTRUEX ✨
                        </div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 18px; letter-spacing: 1px;">
                            #${data.categoria.replace(' ', '')} #Construex #Educacion #Aprendizaje
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="text-align: center; margin-top: 20px;">
                        <div style="color: rgba(255,255,255,0.4); font-size: 14px;">
                            construex.com | Contenido generado por IA
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('poster').innerHTML = html;
        }
        
        async function descargarImagen() {
            const element = document.getElementById('poster');
            const loadingDiv = document.getElementById('loading');
            loadingDiv.style.display = 'block';
            loadingDiv.innerHTML = '⏳ Generando imagen PNG...';
            
            try {
                const canvas = await html2canvas(element, {
                    scale: 2,
                    backgroundColor: null,
                    logging: false,
                    useCORS: true
                });
                
                const link = document.createElement('a');
                link.download = `construex_instagram_${Date.now()}.png`;
                link.href = canvas.toDataURL('image/png');
                link.click();
                
                loadingDiv.style.display = 'none';
            } catch(e) {
                loadingDiv.style.display = 'none';
                mostrarError('Error al generar la imagen: ' + e.message);
            }
        }
        
        function mostrarError(msg) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
            document.getElementById('error').innerHTML = '❌ ' + msg;
            document.getElementById('generateBtn').disabled = false;
            setTimeout(() => {
                document.getElementById('error').style.display = 'none';
            }, 5000);
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
    
    categoria, viralidad, _ = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "resumen": contenido['descripcion'][:300]
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
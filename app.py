"""
======================================================================
                    CONSTRUEX ECOSYSTEM - VERSION CON LOGS
======================================================================
"""

import os
import sys
import traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================
# CONFIGURACION BASICA
# ============================================

print("🚀 Iniciando aplicación...")

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

print(f"📌 GEMINI_API_KEY configurada: {'✅ Sí' if GEMINI_API_KEY else '❌ No'}")

# ============================================
# FUNCIONES SIMPLIFICADAS
# ============================================

def extraer_enlaces(texto):
    """Extrae URLs del texto"""
    import re
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)

def procesar_mensaje_simple(mensaje):
    """Versión simple que no usa Gemini"""
    enlaces = extraer_enlaces(mensaje)
    
    if not enlaces:
        return {"error": "No se encontraron enlaces", "mensaje": mensaje}
    
    return {
        "exito": True,
        "enlaces_encontrados": enlaces,
        "cantidad": len(enlaces),
        "primer_enlace": enlaces[0] if enlaces else None
    }

# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    print("📍 GET / - Página principal")
    return jsonify({
        "servicio": "Construex Ecosystem",
        "estado": "activo",
        "version": "4.0.0 (con logs)",
        "gemini_configurada": bool(GEMINI_API_KEY)
    })

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    print("📍 GET /webhook - Verificación")
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    print(f"   mode={mode}, token={token}, challenge={challenge}")
    
    if mode and token and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def receive_whatsapp():
    print("📍 POST /webhook - Mensaje recibido")
    return jsonify({"status": "ok"}), 200

@app.route('/procesar', methods=['POST'])
def procesar():
    print("\n" + "="*50)
    print("🔵 PROCESAR - Iniciando procesamiento")
    print("="*50)
    
    try:
        # 1. Obtener datos
        print("📥 Paso 1: Leyendo JSON...")
        data = request.get_json()
        print(f"   Datos recibidos: {data}")
        
        if not data:
            print("❌ Error: No hay datos JSON")
            return jsonify({"error": "No hay datos JSON"}), 400
        
        # 2. Extraer mensaje
        print("📝 Paso 2: Extrayendo mensaje...")
        mensaje = data.get('mensaje', '')
        print(f"   Mensaje: {mensaje[:100]}...")
        
        if not mensaje:
            print("❌ Error: No hay mensaje")
            return jsonify({"error": "No hay mensaje"}), 400
        
        # 3. Extraer enlaces
        print("🔗 Paso 3: Extrayendo enlaces...")
        enlaces = extraer_enlaces(mensaje)
        print(f"   Enlaces encontrados: {len(enlaces)}")
        
        if not enlaces:
            print("❌ Error: No se encontraron enlaces")
            return jsonify({"error": "No se encontraron enlaces"}), 400
        
        # 4. Procesar (versión simple)
        print("⚙️ Paso 4: Procesando...")
        resultado = {
            "exito": True,
            "url": enlaces[0],
            "enlaces": enlaces,
            "mensaje_original": mensaje[:200],
            "timestamp": "2024-01-01"
        }
        
        print("✅ Paso 5: Resultado generado")
        print(f"   Resultado: {resultado}")
        print("="*50 + "\n")
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/test', methods=['GET'])
def test():
    print("📍 GET /test - Probando conexión")
    return jsonify({
        "status": "ok",
        "message": "Servidor funcionando correctamente",
        "gemini_key": bool(GEMINI_API_KEY)
    })

@app.route('/status', methods=['GET'])
def status():
    print("📍 GET /status - Estado del sistema")
    return jsonify({
        "status": "running",
        "gemini_configured": bool(GEMINI_API_KEY),
        "endpoints": ["/", "/webhook", "/procesar", "/test", "/status"]
    })

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSION CON LOGS
======================================================================

Endpoints disponibles:
   GET  /          - Información general
   GET  /test      - Prueba de conexión
   GET  /status    - Estado del sistema
   POST /procesar  - Procesar enlaces
   GET  /webhook   - Verificación de WhatsApp
   POST /webhook   - Recepción de WhatsApp

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor iniciando en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
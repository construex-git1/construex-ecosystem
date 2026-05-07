import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Construex activo"})

@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    return jsonify({
        "status": "ok",
        "recibido": mensaje,
        "longitud": len(mensaje)
    })

@app.route('/webhook', methods=['GET'])
def webhook():
    return jsonify({"status": "webhook activo"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
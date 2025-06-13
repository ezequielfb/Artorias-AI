from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
import traceback
# import asyncio # <-- REMOVIDO
from flask_cors import CORS 

# Importa o seu bot Artorias AI.
from artoriasbot import Artoriasbot

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app) 

# --- Inicialização do Artoriasbot ---
try:
    BOT = Artoriasbot()
    print("Artoriasbot inicializado com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO: Falha ao inicializar o Artoriasbot: {e}")
    traceback.print_exc()
    exit(1) 


@app.route("/api/messages", methods=["POST"]) 
def messages():
    """
    Endpoint HTTP para receber mensagens do usuário.
    Espera um JSON com um campo 'text' (ou 'message'/'content', podemos padronizar).
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type deve ser application/json"}), 415

    try:
        data = request.get_json()
        user_message = data.get("text") 
        
        if not user_message:
            return jsonify({"error": "Campo 'text' (ou 'message') não encontrado na requisição"}), 400

        print(f"Flask: Mensagem recebida do usuário: '{user_message}'")

        # --- CHAMADA SÍNCRONA PARA O BOT ---
        bot_response_text = BOT.process_message(user_message, user_id="test_user_123") 
        # --- FIM DA CHAMADA SÍNCRONA ---
            
        print(f"Flask: Resposta do bot: '{bot_response_text}'")
        return jsonify({"response": bot_response_text}), 200

    except Exception as e:
        print(f"ERRO: Falha ao processar a requisição HTTP: {e}")
        traceback.print_exc()
        return jsonify({"error": "Erro interno do servidor ao lidar com a requisição."}), 500

if __name__ == '__main__':
    print("Iniciando servidor Flask para Artorias AI (desenvolvimento)...")
    app.run(host="0.0.0.0", port=3979, debug=True)
from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
import traceback
import asyncio
from flask_cors import CORS # <-- ADICIONADO: Importa a extensão Flask-CORS

# Importa o seu bot Artorias AI.
from artoriasbot import Artoriasbot

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app) # <-- ADICIONADO: Inicializa CORS para a sua aplicação Flask

# --- Inicialização do Artoriasbot ---
try:
    BOT = Artoriasbot()
    print("Artoriasbot inicializado com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO: Falha ao inicializar o Artoriasbot: {e}")
    traceback.print_exc()
    exit(1) # Sai do programa


@app.route("/api/messages", methods=["POST", "OPTIONS"]) # <-- ATUALIZADO: Adiciona 'OPTIONS' aqui
def messages():
    """
    Endpoint HTTP para receber mensagens do usuário.
    Espera um JSON com um campo 'text' (ou 'message'/'content', podemos padronizar).
    """
    # A requisição OPTIONS é um "preflight" do CORS.
    # Se o navegador fez um OPTIONS, apenas retorne OK com os cabeçalhos CORS (Flask-CORS cuida disso).
    if request.method == 'OPTIONS':
        return '', 200 # Responde OK para o OPTIONS e Flask-CORS adiciona os cabeçalhos necessários


    if not request.is_json:
        return jsonify({"error": "Content-Type deve ser application/json"}), 415

    try:
        data = request.get_json()
        user_message = data.get("text") # Ou 'message', ou 'content'
        
        if not user_message:
            return jsonify({"error": "Campo 'text' (ou 'message') não encontrado na requisição"}), 400

        print(f"Flask: Mensagem recebida do usuário: '{user_message}'")

        # --- Como lidar com asyncio em Flask ---
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            bot_response_text = loop.run_until_complete(BOT.process_message(user_message, user_id="test_user_123"))
            
        except Exception as e:
            print(f"ERRO: Falha ao processar a requisição no loop assíncrono: {e}")
            traceback.print_exc()
            return jsonify({"error": "Erro interno do servidor ao processar a mensagem."}), 500

        print(f"Flask: Resposta do bot: '{bot_response_text}'")
        return jsonify({"response": bot_response_text}), 200

    except Exception as e:
        print(f"ERRO: Falha ao processar a requisição HTTP: {e}")
        traceback.print_exc()
        return jsonify({"error": "Erro interno do servidor ao lidar com a requisição."}), 500

if __name__ == '__main__':
    print("Iniciando servidor Flask para Artorias AI (desenvolvimento)...")
    app.run(host="0.0.0.0", port=3979, debug=True)
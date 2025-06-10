from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from artoriasbot import Artoriasbot # <-- CORRIGIDO: Importa Artoriasbot
from config import DefaultConfig
import asyncio
import traceback
import os 
from dotenv import load_dotenv # <-- Adicionado para carregar variáveis de ambiente de .env

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv() 

app = Flask(__name__)

CONFIG = DefaultConfig()

SETTINGS = BotFrameworkAdapterSettings(
    os.environ.get("MicrosoftAppId", ""),
    os.environ.get("MicrosoftAppPassword", "")
)

class CustomBotFrameworkAdapter(BotFrameworkAdapter):
    def __init__(self, settings: BotFrameworkAdapterSettings):
        super().__init__(settings)
        self._prod_service_url = "https://" + (os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "")
        if not os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
             print("AVISO: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não encontrada. Pode afetar respostas em produção.")
        print(f"ADAPTER: _prod_service_url inicializado como: {self._prod_service_url}")

    async def get_service_url(self, turn_context: TurnContext) -> str:
        service_url = turn_context.activity.service_url

        if self._prod_service_url and ("localhost" in service_url or not service_url):
            print(f"ADAPTER: serviceUrl '{service_url}' da atividade substituído por '{self._prod_service_url}'")
            return self._prod_service_url
        
        print(f"ADAPTER: Usando serviceUrl da atividade: '{service_url}'")
        return service_url

ADAPTER = CustomBotFrameworkAdapter(SETTINGS)


MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Removida a inicialização do cliente CLU
BOT = Artoriasbot( # <-- CORRIGIDO: Instancia Artoriasbot
    CONVERSATION_STATE,
    USER_STATE
)

@app.route("/api/messages", methods=["POST"])
def messages():
    if "application/json" not in request.headers.get("Content-Type", ""):
        return jsonify({"error": "Tipo de conteúdo não suportado"}), 415

    try:
        body = request.json
    except Exception as e:
        print(f"Erro ao parsear JSON: {e}")
        traceback.print_exc()
        return jsonify({"error": "Bad Request - JSON Inválido"}), 400

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # --- MODIFICAÇÃO PRINCIPAL AQUI: Como lidar com asyncio em Flask ---
    try:
        # Pega o loop de eventos corrente. Se não houver um, cria um novo para a Thread atual.
        # Isso é mais robusto para uso em ambientes como o Gunicorn ou o servidor de desenvolvimento do Flask.
        loop = asyncio.get_event_loop()
        
        # Cria uma "tarefa" assíncrona para processar a atividade do bot.
        # NÃO usamos asyncio.run() aqui diretamente, pois o Flask já está rodando em um loop/thread.
        loop.run_until_complete(ADAPTER.process_activity(activity, auth_header, BOT.on_turn))

    except RuntimeError as e:
        # Se um loop já estiver rodando e não pudermos usar run_until_complete,
        # tentamos agendar a tarefa no loop existente.
        print(f"RuntimeError ou Loop já rodando: {e}. Tentando agendar a tarefa no loop existente...")
        traceback.print_exc()
        try:
            current_loop = asyncio.get_running_loop() # Tenta pegar o loop que está rodando
            current_loop.create_task(ADAPTER.process_activity(activity, auth_header, BOT.on_turn))
            print("Tarefa assíncrona agendada com sucesso no loop existente.")
        except RuntimeError:
            print("ERRO CRÍTICO: Não foi possível obter ou agendar a tarefa assíncrona. Nenhum loop de eventos rodando ou erro no agendamento.")
            return jsonify({"error": "Erro interno no servidor: Falha ao agendar processamento do bot."}), 500
    except Exception as e:
        print(f"Erro inesperado durante o processamento da atividade: {e}")
        traceback.print_exc()
        return jsonify({"error": "Erro interno no servidor durante processamento do bot."}), 500

    return jsonify({"status": "Solicitação recebida, processamento iniciado."}), 201

if __name__ == '__main__':
    print("Iniciando servidor de desenvolvimento Flask (apenas para testes locais)...")
    app.run(host="0.0.0.0", port=3979, debug=True)
from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from artoriasbot import Artoriasbot # <-- ATUALIZADO: Importa Artoriasbot
from config import DefaultConfig
import asyncio
import traceback
import os 
from dotenv import load_dotenv # <-- Adicionado para carregar variáveis de ambiente de .env

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv() 

app = Flask(__name__)

CONFIG = DefaultConfig()

# As credenciais do bot framework APP_ID e APP_PASSWORD podem vir de variáveis de ambiente também
# SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
SETTINGS = BotFrameworkAdapterSettings(
    os.environ.get("MicrosoftAppId", ""), # Vazio para testes locais no Emulator
    os.environ.get("MicrosoftAppPassword", "") # Vazio para testes locais no Emulator
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

# --- REMOVIDA A INICIALIZAÇÃO DO CLIENTE CLU ---
# CLU_CLIENT não é mais necessário, pois usaremos Gemini

BOT = Artoriasbot( # <-- ATUALIZADO: Instancia Artoriasbot
    CONVERSATION_STATE,
    USER_STATE
    # Parâmetros CLU removidos
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

    async def _process_activity_async():
        try:
            await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        except Exception as e:
            print(f"Erro ao processar atividade assíncrona: {e}")
            traceback.print_exc()

    try:
        asyncio.run(_process_activity_async())
    except RuntimeError as e:
        print(f"RuntimeError ao executar asyncio.run(): {e}. Tentando outra abordagem...")
        traceback.print_exc()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_process_activity_async())
            print("Tarefa agendada com sucesso.")
        except RuntimeError:
            print("Não foi possível agendar a tarefa assíncrona: nenhum loop de eventos rodando.")
            return jsonify({"error": "Erro interno no servidor ao agendar processamento do bot."}), 500

    return jsonify({"status": "Solicitação recebida, processamento iniciado."}), 201

if __name__ == '__main__':
    print("Iniciando servidor de desenvolvimento Flask (apenas para testes locais)...")
    app.run(host="0.0.0.0", port=3979, debug=True)
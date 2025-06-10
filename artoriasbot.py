# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
# As importações abaixo foram removidas pois não são usadas na nova arquitetura:
# from datetime import datetime
# from typing import Any, Dict
# from botbuilder.core import ActivityHandler, TurnContext, MessageFactory, UserState, ConversationState
# from botbuilder.schema import ChannelAccount, ActivityTypes
# from config import DefaultConfig

# Importações essenciais para o Gemini
import google.generativeai as genai
import os # Para acessar variáveis de ambiente

class Artoriasbot: # Não herda mais de ActivityHandler
    def __init__(self):
        self.conversation_states = {} # Dicionário para simular estado por ID de usuário/conversa

        # Configuração da API do Gemini
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        # Usando o modelo 'gemini-2.0-flash' conforme o log do curl
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        print("Artoriasbot: Modelo Gemini inicializado com sucesso.")


    async def process_message(self, user_message: str, user_id: str = "default_user") -> str:
        """
        Processa uma mensagem de texto do usuário e retorna uma resposta.
        Esta é a nova função principal do seu bot.
        """
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        
        try:
            # Contexto do sistema para o Gemini (pode ser parte do history, ou passado via um prompt de sistema)
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec. Sua função principal é:\n"
                f"1. Responder perguntas gerais sobre a empresa e seus serviços (preços, implementação, etc.).\n"
                f"2. Qualificar leads para o time de SDR, coletando nome, função, empresa, desafios e tamanho da empresa.\n"
                f"3. Encaminhar para o suporte técnico se o usuário tiver um problema.\n"
                f"4. Mantenha as respostas concisas e no máximo 3 frases.\n"
                f"5. Se precisar de uma informação do usuário, faça a pergunta diretamente.\n"
                f"6. Se for um SDR, peça nome e função primeiro.\n"
                f"7. Se for suporte, peça a descrição do problema.\n"
                f"---"
            )

            # Inicializa (ou continua) a sessão de chat com o Gemini.
            # O 'history' deve ser no formato que a API do Gemini espera (roles e parts).
            chat_session = self.gemini_model.start_chat(history=current_flow_state["history"])
            
            # Envia a mensagem do usuário, combinando com a instrução do sistema no prompt.
            # A API send_message adiciona a mensagem do usuário e a resposta do modelo ao histórico da sessão.
            gemini_response = chat_session.send_message(system_instruction + "\n" + user_message) # <-- Removido o 'await'

            if gemini_response and gemini_response.candidates:
                response_text = gemini_response.candidates[0].content.parts[0].text
                # Atualiza nosso histórico local com o histórico da sessão do Gemini
                current_flow_state["history"] = [
                    {"role": entry.role, "parts": [part.text for part in entry.parts if hasattr(part, 'text')]}
                    for entry in chat_session.history
                ]
            else:
                response_text = "Não consegui gerar uma resposta inteligente no momento. Por favor, tente novamente."

            # Atualiza o estado da conversa local (em memória)
            self.conversation_states[user_id] = current_flow_state

        except Exception as e:
            print(f"ERRO: Falha ao chamar a API do Gemini: {e}")
            traceback.print_exc(file=sys.stdout)
            response_text = "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente mais tarde."

        return response_text
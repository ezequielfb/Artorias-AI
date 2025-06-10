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
            # Contexto do sistema para o Gemini: Define o papel do bot e suas responsabilidades.
            # INSTRUÇÕES ATUALIZADAS PARA SAÍDA ESTRUTURADA E FLUXOS
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec, uma empresa de soluções de TI.\n"
                f"Suas responsabilidades são:\n"
                f"1.  **Atendimento Geral (FAQ):** Responda perguntas sobre preços, implementação, Microsoft Teams, gestão de documentação e contratos. Se for uma pergunta de FAQ, forneça a resposta diretamente.\n"
                f"2.  **Qualificação SDR:** Se o usuário demonstrar interesse em vendas, orçamentos, propostas, ou falar com um especialista/consultor de vendas, inicie o processo de qualificação de SDR. Colete as seguintes informações sequencialmente:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades.\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    Após coletar todas as informações, informe que um SDR entrará em contato.\n"
                f"3.  **Suporte Técnico:** Se o usuário tiver um problema técnico ou precisar de ajuda, inicie o processo de suporte. Colete:\n"
                f"    a. Descrição detalhada do problema.\n"
                f"    b. Informações de contato (nome, e-mail, empresa) se for necessária escalada (peça após a descrição do problema).\n"
                f"    Após coletar o problema e as informações de contato, informe que o ticket será encaminhado para a equipe de suporte.\n"
                f"4.  **Comportamento:**\n"
                f"    - Mantenha um tom profissional e útil.\n"
                f"    - Seja conciso. Limite suas respostas a 3 frases, a menos que uma explicação mais completa seja solicitada ou necessária para o fluxo.\n"
                f"    - Guie o usuário suavemente pelos fluxos de SDR ou Suporte, pedindo uma informação por vez.\n"
                f"    - Se não entender, peça para o usuário reformular.\n"
                f"    - Se o usuário se despedir ou agradecer, responda de forma cordial e encerre o tópico.\n"
                f"---"
            )

            # O histórico de chat deve ser passado para o Gemini para manter o contexto.
            # O sistema instruction pode ser a primeira entrada do histórico para o Gemini.
            if not current_flow_state["history"]:
                gemini_history = [
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]}
                ]
            else:
                gemini_history = current_flow_state["history"]
            
            # Inicia a sessão de chat com o histórico construído
            chat_session = self.gemini_model.start_chat(history=gemini_history)
            
            # Envia a nova mensagem do usuário para a sessão de chat.
            gemini_response = chat_session.send_message(user_message)

            if gemini_response and gemini_response.candidates:
                response_content = gemini_response.candidates[0].content.parts[0].text
                response_text = response_content # Por enquanto, a resposta é apenas o texto
                
                # Vamos tentar fazer o Gemini retornar um JSON no início da resposta.
                # Esta é uma técnica de prompt, e o Gemini não GARANTE que seguirá,
                # mas é um passo para entender como extrair dados estruturados.
                # Exemplo: { "action": "sdr_qualify", "next_step": "ask_name", "response": "Claro! Para começarmos, qual seu nome e função?" }
                # Mas para a primeira iteração, vamos apenas focar na resposta em texto.
                # A lógica de parsing JSON será um próximo passo.

                # Atualiza nosso histórico local com o histórico da sessão do Gemini.
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
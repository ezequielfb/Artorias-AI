# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from typing import Any, Dict

from botbuilder.core import (
    ActivityHandler, TurnContext, MessageFactory, UserState,
    ConversationState
)
from botbuilder.schema import ChannelAccount, ActivityTypes # Removidas Attachment, ActionTypes, CardAction

# Importações para o Gemini
import google.generativeai as genai
import os # Para acessar variáveis de ambiente

# Importações de configuração (se ainda precisar de CONFIG aqui)
from config import DefaultConfig

class Artoriasbot(ActivityHandler): # Renomeado para Artoriasbot
    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        if conversation_state is None:
            raise TypeError(
                "[ArtoriasBot]: Missing parameter. conversation_state is required"
            )
        if user_state is None:
            raise TypeError("[ArtoriasBot]: Missing parameter. user_state is required")

        self.conversation_state = conversation_state
        self.user_state = user_state
        self.conversation_flow_accessor = self.conversation_state.create_property("ConversationFlow")
        self.user_profile_accessor = self.user_state.create_property("UserProfile")

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        self.gemini_model = genai.GenerativeModel('gemini-pro')
        print("Artoriasbot: Modelo Gemini inicializado com sucesso.")


    async def on_turn(self, turn_context: TurnContext):
        print(f"ON_TURN: Activity Type: {turn_context.activity.type}, User ID: {turn_context.activity.from_property.id}")

        await super().on_turn(turn_context)

        await self.conversation_state.save_changes(turn_context, False)
        await self.user_state.save_changes(turn_context, False)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        print("ON_MEMBERS_ADDED_ACTIVITY: Novo membro adicionado.")
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_text = ("Saudações, sou Artorias AI! Seu guardião inteligente para assistência e qualificação de leads. "
                                "Como posso servi-lo hoje? Posso responder perguntas, conectar você com um especialista ou ajudar com automações.")
                await turn_context.send_activity(MessageFactory.text(welcome_text))
                
                await self.conversation_flow_accessor.set(turn_context, {"state": "initial"})
                await self.user_profile_accessor.set(turn_context, {})

    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text
        print(f"ON_MESSAGE_ACTIVITY: Mensagem do usuário: '{user_message}'")

        current_flow_state = await self.conversation_flow_accessor.get(turn_context, {"state": "initial"})
        user_profile = await self.user_profile_accessor.get(turn_context, {})

        response_text = "Desculpe, ainda estou aprendendo. Por favor, reformule sua pergunta."
        
        try:
            prompt = f"""
            Você é Artorias AI, um assistente inteligente para a Tralhotec. Sua função principal é:
            1. Responder perguntas gerais sobre a empresa e seus serviços (preços, implementação, etc.).
            2. Qualificar leads para o time de SDR (Sales Development Representative), coletando informações como nome, função, empresa, desafios e tamanho da empresa.
            3. Encaminhar para o suporte técnico se o usuário tiver um problema.

            Considere o histórico da conversa (se houver, adicione aqui o histórico real da conversa) e o estado atual do fluxo: {current_flow_state.get('state', 'initial')}.

            Mensagem do usuário: "{user_message}"

            Com base na mensagem do usuário e no contexto, por favor, responda de forma concisa e útil. Se for uma pergunta de qualificação de SDR ou suporte, faça a próxima pergunta necessária ou informe o próximo passo.
            """

            gemini_response = self.gemini_model.generate_content(prompt)
            
            if gemini_response and gemini_response.candidates:
                response_text = gemini_response.candidates[0].content.parts[0].text
            else:
                response_text = "Não consegui gerar uma resposta inteligente no momento. Por favor, tente novamente."

        except Exception as e:
            print(f"ERRO: Falha ao chamar a API do Gemini: {e}")
            traceback.print_exc(file=sys.stdout)
            response_text = "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente mais tarde."

        await turn_context.send_activity(MessageFactory.text(response_text))
        print(f"ON_MESSAGE_ACTIVITY: Bot respondeu: '{response_text}'")
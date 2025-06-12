import sys
import traceback
import google.generativeai as genai
import os
import json
# import asyncpg # <-- REMOVIDO: Não usaremos mais o driver assíncrono para BD

class Artoriasbot:
    def __init__(self):
        # O histórico de conversas será mantido APENAS em memória.
        self.conversation_states = {} 
        # self.db_pool = None # Removido, pois não há BD

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        # Ajustando parâmetros do modelo para comportamento mais "orgânico" e menos restritivo.
        # Aumentando max_output_tokens e removendo temperature para usar o padrão (mais criativo).
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"max_output_tokens": 500}) 
        print("Artoriasbot: Modelo Gemini inicializado com sucesso (orgânico).")

    # Métodos de BD removidos ou adaptados para não fazer nada
    # def _init_db_pool(self): pass
    # def _load_conversation_history(self, user_id: str) -> list: return [] # Retorna vazio, não carrega do BD
    # def _save_conversation_entry(self, user_id: str, role: str, content: str): pass # Não salva no BD
    # def _save_extracted_data(self, user_id: str, data: dict, action_type: str): pass # Não salva no BD

    async def process_message(self, user_message: str, user_id: str = "default_user") -> str:
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        # Histórico em memória apenas
        # Se o usuário é novo ou o histórico é vazio, inicializa.
        # Senão, pega o histórico da memória.
        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} 

        try:
            # INSTRUÇÕES DO SISTEMA (PROMPT) - Versão "Orgânica" 
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec, uma empresa de soluções de TI.\n"
                f"Suas responsabilidades são:\n"
                f"1.  **Atendimento Geral (FAQ):** Responda perguntas sobre preços, implementação, Microsoft Teams, gestão de documentação e contratos. Se for uma pergunta de FAQ, forneça a resposta diretamente.\n"
                f"2.  **Qualificação SDR:** Se o usuário demonstrar interesse em vendas, orçamentos, propostas, ou falar com um especialista/consultor de vendas, inicie o processo de qualificação de SDR. Colete as seguintes informações sequencialmente:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades.\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    e. E-mail de contato e/ou número de WhatsApp (último passo da qualificação SDR).\n"
                f"    Ao final do fluxo SDR (todas as informações serem coletadas), forneça a resposta de texto final para o usuário e, em uma nova linha, **então adicione o bloco JSON**.\n"
                f"    ```json\n"
                f"    {{\"action\": \"sdr_completed\", \"lead_info\": {{\"nome\": \"[Nome]\", \"funcao\": \"[Funcao]\", \"empresa\": \"[Empresa]\", \"desafios\": \"[Desafios]\", \"tamanho\": \"[Tamanho]\", \"email\": \"[Email]\", \"whatsapp\": \"[WhatsApp]\"}}}}\n"
                f"    ```\n"
                f"    Substitua os placeholders `[Nome]`, `[Funcao]`, etc., pelos dados coletados.\n"
                f"3.  **Suporte Técnico:** Se o usuário tiver um problema técnico ou precisar de ajuda, inicie o processo de suporte. Colete:\n"
                f"    a. Descrição detalhada do problema.\n"
                f"    b. Informações de contato (nome, e-mail, empresa) se for necessária escalada (peça após a descrição do problema).\n"
                f"    Ao final do fluxo de Suporte (problema e contato coletados), forneça a mensagem final e adicione o JSON:**\n"
                f"    ```json\n"
                f"    {{\"action\": \"support_escalated\", \"ticket_info\": {{\"problema\": \"[Problema]\", \"nome_contato\": \"[Nome Contato]\", \"email_contato\": \"[Email Contato]\", \"empresa_contato\": \"[Empresa Contato]\"}}}}\n"
                f"    ```\n"
                f"    Substitua `[Problema]`, etc., pelos dados.\n"
                f"4.  **Comportamento:**\n"
                f"    - Mantenha um tom profissional e útil.\n"
                f"    - Seja conciso. Limite suas respostas a 3 frases, a menos que uma explicação mais completa seja solicitada ou necessária para o fluxo.\n"
                f"    - Guie o usuário suavemente pelos fluxos de SDR ou Suporte, pedindo uma informação por vez.\n"
                f"    - Se não entender, peça para o usuário reformular.\n"
                f"    - Se o usuário se despedir ou agradecer, responda de forma cordial e encerre o tópico.\n"
                f"---"
            )

            # Prepara o histórico para o Gemini.
            # O system_instruction é adicionado como a primeira entrada no histórico apenas no primeiro turno.
            if not current_flow_state["history"]: 
                gemini_chat_history = [
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]}
                ]
            else:
                gemini_chat_history = current_flow_state["history"]
            
            chat_session = self.gemini_model.start_chat(history=gemini_chat_history)
            gemini_response = chat_session.send_message(user_message) # Síncrono: não precisa de 'await'

            if gemini_response and gemini_response.candidates:
                response_content = gemini_response.candidates[0].content.parts[0].text
                
                # print(f"DEBUG: Conteúdo bruto do Gemini: '{response_content}'") # REMOVIDO
                
                response_text = response_content 
                
                json_start_tag = "```json"
                json_end_tag = "```"
                json_start_index = response_content.find(json_start_tag)
                json_end_index = response_content.find(json_end_tag, json_start_index + len(json_start_tag)) if json_start_index != -1 else -1

                # print(f"DEBUG: json_start_index: {json_start_index}, json_end_index: {json_end_index}") # REMOVIDO

                if json_start_index != -1 and json_end_index != -1:
                    json_str = response_content[json_start_index + len(json_start_tag):json_end_index].strip()
                    # print(f"DEBUG: String JSON extraída: '{json_str}'") # REMOVIDO
                    try:
                        extracted_data = json.loads(json_str)
                        print(f"Artoriasbot: JSON extraído: {extracted_data}")
                        
                        # --- CÓDIGO DE SALVAMENTO DE DADOS REMOVIDO/DESATIVADO ---
                        # action_type = extracted_data.get("action", "unknown")
                        # if action_type in ["sdr_completed", "support_escalated"]:
                        #    pass # Não salva mais no BD
                        # --- FIM DO CÓDIGO DE SALVAMENTO DE DADOS REMOVIDO ---
                        
                        response_text = response_content[:json_start_index].strip()
                        
                        # print(f"DEBUG: Resposta textual após remover JSON: '{response_text}'") # REMOVIDO

                        if not response_text:
                            # print(f"DEBUG: response_text está vazio. Tentando resposta padrão.") # REMOVIDO
                            action = extracted_data.get("action", "")
                            # print(f"DEBUG: Ação extraída do JSON: '{action}')") # REMOVIDO

                            if "sdr_completed" in action:
                                response_text = "Perfeito! Agradeço as informações. Um dos nossos SDRs entrará em contato em breve para agendar uma conversa com um consultor de vendas."
                            elif "support_escalated" in action:
                                response_text = "Obrigado! Sua solicitação de suporte foi encaminhada para nossa equipe. Eles entrarão em contato em breve."
                            else:
                                response_text = "Concluído! Agradeço as informações." 

                        # print(f"DEBUG: Resposta textual final: '{response_text}'") # REMOVIDO

                    except json.JSONDecodeError as e:
                        print(f"Artoriasbot: ERRO ao parsear JSON: {e}")
                        extracted_data = {} 
                
                # --- CÓDIGO DE SALVAMENTO DE HISTÓRICO REMOVIDO ---
                # current_flow_state["history"] será atualizado apenas em memória.
                # Não salva mais no BD.
                # await self._save_conversation_entry(user_id, "user", user_message)
                # await self._save_conversation_entry(user_id, "model", response_text)
                
                # Apenas atualiza o histórico em memória para a próxima rodada
                current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})

            else:
                response_text = "Não consegui gerar uma resposta inteligente no momento. Por favor, tente novamente."

            self.conversation_states[user_id] = current_flow_state

            return response_text

        except Exception as e:
            print(f"ERRO: Falha ao chamar a API do Gemini: {e}")
            traceback.print_exc(file=sys.stdout)
            response_text = "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente mais tarde."

        return response_text
import sys
import traceback
import google.generativeai as genai
import os
import json
# import asyncpg # BD temporariamente desativado.
# requests # Removido, pois não é mais necessário para a funcionalidade atual.

class Artoriasbot:
    def __init__(self):
        self.conversation_states = {} # Histórico em memória

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        # Versão orgânica: sem temperature e sem max_output_tokens
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash') 
        print("Artoriasbot: Modelo Gemini inicializado com sucesso (orgânico, sem restrições de temperatura/tokens).")

    # Métodos de BD temporariamente desativados/removidos.
    # def _init_db_pool(self): pass
    # async def _load_conversation_history(self, user_id: str) -> list: return []
    # async def _save_conversation_entry(self, user_id: str, role: str, content: str): pass
    # async def _save_extracted_data(self, user_id: str, data: dict, action_type: str): pass

    async def process_message(self, user_message: str, user_id: str = "default_user") -> str: # AGORA ASÍNCRONO (async def)
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} 

        try:
            # PROMPT ORGÂNICO E INTELIGENTE: Processar tudo que o usuário der e pedir só o que falta
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec, uma empresa de soluções de TI.\n"
                f"Sua missão é guiar o usuário pelos fluxos de SDR ou Suporte Técnico. Você deve ser capaz de: \n"
                f"1.  **Entender toda a informação fornecida em um único turno.** Se o usuário der múltiplas informações de uma vez (ex: nome, empresa e problema), processe todas elas.\n"
                f"2.  **Identificar qual a próxima informação *FALTANTE*** na sequência do fluxo e pedir APENAS por ela.\n"
                f"3.  **Gerar o JSON estruturado** ao final do fluxo, quando todas as informações forem coletadas.\n"
                f"4.  **Manter um tom profissional e útil**, sendo conciso, mas completo na resposta.\n"
                f"\n"
                f"--- REGRAS DE FLUXO E COLETA DE DADOS ---\n"
                f"1.  **QUALIFICAÇÃO SDR (SEQUÊNCIA PRIORITÁRIA):**\n"
                f"    Informações a coletar sequencialmente para SDR:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades.\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    e. E-mail de contato e/ou número de WhatsApp.\n"
                f"    Ao final do fluxo SDR (todas as infos coletadas), inclua o JSON: \n"
                f"    ```json\n"
                f"    {{\"action\": \"sdr_completed\", \"lead_info\": {{\"nome\": \"[Nome]\", \"funcao\": \"[Funcao]\", \"empresa\": \"[Empresa]\", \"desafios\": \"[Desafios]\", \"tamanho\": \"[Tamanho]\", \"email\": \"[Email]\", \"whatsapp\": \"[WhatsApp]\"}}}}\n"
                f"    ```\n"
                f"2.  **SUPORTE TÉCNICO (SEQUÊNCIA PRIORITÁRIA):**\n"
                f"    Informações a coletar sequencialmente para Suporte:\n"
                f"    a. Descrição detalhada do problema.\n"
                f"    b. Informações de contato (nome, e-mail, empresa).\n"
                f"    Ao final do fluxo de Suporte (todas as infos coletadas), inclua o JSON:\n"
                f"    ```json\n"
                f"    {{\"action\": \"support_escalated\", \"ticket_info\": {{\"problema\": \"[Problema]\", \"nome_contato\": \"[Nome Contato]\", \"email_contato\": \"[Email Contato]\", \"empresa_contato\": \"[Empresa Contato]\"}}}}\n"
                f"    ```\n"
                f"\n"
                f"--- COMPORTAMENTO GERAL ---\n"
                f"1.  **Sempre tente encaixar o usuário em um dos fluxos (SDR ou Suporte).** Se a intenção for clara, comece pelo passo 1 do fluxo. Se o usuário fornecer informações para ambos os fluxos, priorize o SDR.\n"
                f"2.  **Se o usuário fornecer todas as informações necessárias para um fluxo em um único turno, responda a mensagem final e inclua o JSON na mesma resposta.**\n"
                f"3.  **Se o usuário desviar ou perguntar algo não relacionado no meio de um fluxo, gentilmente o redirecione ao fluxo, pedindo a próxima informação necessária.**\n"
                f"4.  Se o usuário se despedir ou agradecer, responda cordialmente.\n"
                f"5.  Se não entender, peça para reformular.\n"
                f"---"
            )

            # Prepara o histórico para o Gemini.
            if not current_flow_state["history"]: 
                gemini_chat_history = [
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]}
                ]
            else:
                gemini_chat_history = current_flow_state["history"]
            
            chat_session = self.gemini_model.start_chat(history=gemini_chat_history)
            gemini_response = await chat_session.send_message(user_message) # <-- 'await' está presente e necessário aqui

            if gemini_response and gemini_response.candidates:
                response_content = gemini_response.candidates[0].content.parts[0].text
                
                response_text = response_content 
                
                json_start_tag = "```json"
                json_end_tag = "```"
                json_start_index = response_content.find(json_start_tag)
                json_end_index = response_content.find(json_end_tag, json_start_index + len(json_start_tag)) if json_start_index != -1 else -1

                if json_start_index != -1 and json_end_index != -1:
                    json_str = response_content[json_start_index + len(json_start_tag):json_end_index].strip()
                    try:
                        extracted_data = json.loads(json_str)
                        print(f"Artoriasbot: JSON extraído: {extracted_data}")
                        
                        # Código de salvamento de dados temporariamente desativado
                        # action_type = extracted_data.get("action", "unknown")
                        # if action_type in ["sdr_completed", "support_escalated"]:
                        #    pass 
                        
                        response_text = response_content[:json_start_index].strip()
                        
                        if not response_text:
                            action = extracted_data.get("action", "")
                            if "sdr_completed" in action:
                                response_text = "Perfeito! Agradeço as informações. Um dos nossos SDRs entrará em contato em breve para agendar uma conversa com um consultor de vendas."
                            elif "support_escalated" in action:
                                response_text = "Obrigado! Sua solicitação de suporte foi encaminhada para nossa equipe. Eles entrarão em contato em breve."
                            else:
                                response_text = "Concluído! Agradeço as informações." 

                    except json.JSONDecodeError as e:
                        print(f"Artoriasbot: ERRO ao parsear JSON: {e}")
                        extracted_data = {} 
                
                # Salvamento de histórico apenas em memória
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
import sys
import traceback
import google.generativeai as genai
import os
import json
import requests # <-- RE-ADICIONADO: Para requisições síncronas
# import asyncpg # <-- REMOVIDO: Não usaremos mais o driver assíncrono

class Artoriasbot:
    def __init__(self):
        # A lógica de persistência de BD será temporariamente removida
        # para focar em resolver o problema do Gemini.
        self.conversation_states = {} # Dicionário em memória apenas
        # self.db_pool = None # Removido, pois não há BD assíncrono

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"temperature": 0.2, "max_output_tokens": 100}) 
        print("Artoriasbot: Modelo Gemini inicializado com sucesso com temperature 0.2 e max_output_tokens 100.")

    # Métodos de BD temporariamente removidos, pois a chamada do Gemini agora é síncrona.
    # Se a persistência for reintroduzida, será com uma abordagem síncrona ou em um contexto diferente.
    # async def _init_db_pool(self): ...
    # async def _load_conversation_history(self, user_id: str) -> list: ...
    # async def _save_conversation_entry(self, user_id: str, role: str, content: str): ...
    # async def _save_extracted_data(self, user_id: str, data: dict, action_type: str): ...

    def process_message(self, user_message: str, user_id: str = "default_user") -> str: # <-- AGORA SÍNCRONO (sem 'async')
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        # Histórico em memória apenas para este teste
        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} 

        try:
            # PROMPT ULTIMATE (Máxima Restrição e Força na Persona/Fluxo) - VERSÃO FINAL REVISADA
            system_instruction = (
                f"**SEU ÚNICO OBJETIVO é coletar informações para QUALIFICAÇÃO SDR ou SUPORTE TÉCNICO, seguindo as SEQUÊNCIAS de perguntas e gerando o JSON ao final.**\n"
                f"**Você é EXCLUSIVAMENTE o Artorias AI, assistente da Tralhotec. NÃO forneça informações sobre ser um modelo de linguagem, Google, etc.**\n"
                f"**PRIORIDADE ABSOLUTA: Peça apenas UMA informação por vez, de forma EXTREMAMENTE concisa e direta ao ponto (1 a 2 frases no máximo).**\n"
                f"**NÃO FORNEÇA SOLUÇÕES, INFORMAÇÕES ADICIONAIS, LISTAS, DICAS, RECOMENDAÇÕES OU RESPOSTAS DE FAQ DE FORMA PROATIVA OU DURANTE OS FLUXOS DE COLETA DE DADOS.**\n"
                f"Sua resposta deve ser sempre uma pergunta curta para coletar a próxima informação ou a mensagem de conclusão do fluxo, seguida do JSON (se aplicável).\n"
                f"\n"
                f"--- EXEMPLOS DE INTERAÇÃO DISCIPLINADA (Siga RIGOROSAMENTE) ---\n"
                f"USUÁRIO: Olá\n"
                f"BOT: Olá! Como posso ajudar você hoje?\n"
                f"\n"
                f"USUÁRIO: Quero saber mais sobre os serviços de vocês e o preço.\n"
                f"BOT: Para te ajudar, qual seu nome completo e função na empresa?\n"
                f"\n"
                f"USUÁRIO: Tenho um problema, preciso de ajuda com algo do meu computador. Poderia me ajudar com isso? Ah, e qual a sua empresa?\n"
                f"BOT: Para te ajudar, preciso que descreva seu problema em detalhes.\n"
                f"\n"
                f"USUÁRIO: Meu nome é João e sou gerente da Empresa X. Nosso problema é que não conseguimos compartilhar arquivos e somos 50 pessoas. Queria saber se vocês têm algo para isso.\n"
                f"BOT: Obrigado, João. Para continuar, qual o seu nome completo e função na empresa?\n" 
                f"\n"
                f"USUÁRIO: Qual a sua função, Artorias?\n"
                f"BOT: Sou Artorias AI. Para que tipo de ajuda você veio: qualificação SDR ou suporte técnico?\n" 
                f"\n"
                f"USUÁRIO: Quem é você?\n"
                f"BOT: Meu nome é Artorias AI, assistente da Tralhotec. Para que tipo de ajuda você veio: qualificação SDR ou suporte técnico?\n" 
                f"\n"
                f"USUÁRIO: Como você pode me ajudar?\n"
                f"BOT: Posso te ajudar com qualificação de leads ou suporte técnico. Qual sua necessidade?\n" 
                f"\n"
                f"USUÁRIO: Quero contratar o serviço de vocês.\n"
                f"BOT: Certo. Para te ajudar, qual seu nome completo e função na empresa?\n"
                f"\n"
                f"USUÁRIO: Por favor, me diga os números primos de 1 a 100.\n"
                f"BOT: Posso te ajudar com qualificação de leads ou suporte técnico. Qual sua necessidade?\n" 
                f"--- FIM DOS EXEMPLOS ---\n"
                f"\n"
                f"--- REGRAS DETALHADAS (SEMPRE APLICAR) ---\n"
                f"1.  **QUALIFICAÇÃO SDR (SEQUÊNCIA RÍGIDA):**\n"
                f"    Se o usuário demonstrar interesse em vendas, orçamentos, propostas ou falar com especialista, inicie o processo de qualificação de SDR. Colete as seguintes informações **EXATAMENTE nesta ordem**:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades (peça a descrição, NUNCA dê soluções ou liste opções).\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    e. E-mail de contato e/ou número de WhatsApp.\n"
                f"    **Ao concluir o fluxo SDR (todas as informações coletadas), forneça a mensagem final e adicione o JSON:**\n"
                f"    ```json\n"
                f"    {{\"action\": \"sdr_completed\", \"lead_info\": {{\"nome\": \"[Nome]\", \"funcao\": \"[Funcao]\", \"empresa\": \"[Empresa]\", \"desafios\": \"[Desafios]\", \"tamanho\": \"[Tamanho]\", \"email\": \"[Email]\", \"whatsapp\": \"[WhatsApp]\"}}}}\n"
                f"    ```\n"
                f"    Substitua `[Nome]`, etc. pelos dados.\n"
                f"2.  **SUPORTE TÉCNICO (SEQUÊNCIA RÍGIDA):**\n"
                f"    Se o usuário precisar de ajuda técnica, inicie o processo de suporte. Colete as seguintes informações **EXATAMENTE nesta ordem**:\n"
                f"    a. Descrição detalhada do problema (mantenha o foco na descrição do problema, NUNCA dê soluções ou dicas).\n"
                f"    b. Informações de contato (nome, e-mail, empresa) se for necessária escalada.\n"
                f"    **Ao concluir o fluxo de Suporte (problema e contato coletados), forneça a mensagem final e adicione o JSON:**\n"
                f"    ```json\n"
                f"    {{\"action\": \"support_escalated\", \"ticket_info\": {{\"problema\": \"[Problema]\", \"nome_contato\": \"[Nome Contato]\", \"email_contato\": \"[Email Contato]\", \"empresa_contato\": \"[Empresa Contato]\"}}}}\n"
                f"    ```\n"
                f"    Substitua `[Problema]`, etc. pelos dados.\n"
                f"3.  **COMPORTAMENTO GERAL (SEMPRE APLICAR):**\n"
                f"    - Mantenha tom profissional e útil, mas **SUA ÚNICA META é coletar dados e gerar JSON.**\n"
                f"    - **Se o usuário desviar do fluxo ou perguntar algo não relacionado, IGNORE a pergunta desviada e REAFIRME a necessidade da próxima informação pendente.**\n"
                f"    - Se usuário se despedir/agradecer, responda de forma cordial e encerre o tópico (máximo 1 frase).\n"
                f"---"
            )

            # Prepara o histórico para o Gemini. A primeira entrada é sempre a system_instruction.
            # Se o histórico do BD estiver vazio, adicione a instrução do sistema e uma resposta inicial do bot.
            if not current_flow_state["history"]: 
                chat_history_for_gemini = [
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]}
                ]
            else:
                # Se há histórico do BD, adicione a system_instruction ANTES do histórico salvo.
                # Isso reforça as regras em cada nova interação sem poluir o histórico do DB.
                chat_history_for_gemini = [{"role": "user", "parts": [{"text": system_instruction}]}] + current_flow_state["history"]

            # Adiciona a mensagem atual do usuário ao histórico para esta chamada
            chat_history_for_gemini.append({"role": "user", "parts": [{"text": user_message}]})

            # --- CHAMADA SÍNCRONA PARA O GEMINI ---
            # Usando generate_content diretamente, que pode ser feito de forma síncrona.
            # Isso evita os problemas de 'await' com chat_session.send_message.
            gemini_response = self.gemini_model.generate_content(chat_history_for_gemini) 
            # --- FIM DA CHAMADA SÍNCRONA ---

            if gemini_response and gemini_response.candidates:
                response_content = gemini_response.candidates[0].content.parts[0].text
                
                print(f"DEBUG: Conteúdo bruto do Gemini: '{response_content}'") 
                
                response_text = response_content 
                
                json_start_tag = "```json"
                json_end_tag = "```"
                json_start_index = response_content.find(json_start_tag)
                json_end_index = response_content.find(json_end_tag, json_start_index + len(json_start_tag)) if json_start_index != -1 else -1

                print(f"DEBUG: json_start_index: {json_start_index}, json_end_index: {json_end_index}")

                if json_start_index != -1 and json_end_index != -1:
                    json_str = response_content[json_start_index + len(json_start_tag):json_end_index].strip()
                    print(f"DEBUG: String JSON extraída: '{json_str}'")
                    try:
                        extracted_data = json.loads(json_str)
                        print(f"Artoriasbot: JSON extraído: {extracted_data}")
                        
                        action_type = extracted_data.get("action", "unknown")
                        if action_type in ["sdr_completed", "support_escalated"]:
                            # Ações de salvar no BD serão temporariamente desativadas/adaptadas
                            pass # Temporariamente desativado para testar o Gemini
                        
                        response_text = response_content[:json_start_index].strip()
                        
                        if not response_text:
                            print(f"DEBUG: response_text está vazio. Tentando resposta padrão.")
                            action = extracted_data.get("action", "")
                            print(f"DEBUG: Ação extraída do JSON: '{action}')")

                            if "sdr_completed" in action:
                                response_text = "Perfeito! Agradeço as informações. Um dos nossos SDRs entrará em contato em breve para agendar uma conversa com um consultor de vendas."
                            elif "support_escalated" in action:
                                response_text = "Obrigado! Sua solicitação de suporte foi encaminhada para nossa equipe. Eles entrarão em contato em breve."
                            else:
                                response_text = "Concluído! Agradeço as informações." 

                        print(f"DEBUG: Resposta textual final: '{response_text}'")

                    except json.JSONDecodeError as e:
                        print(f"Artoriasbot: ERRO ao parsear JSON: {e}")
                        extracted_data = {} 
                
                # Salvamento de histórico em memória apenas
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
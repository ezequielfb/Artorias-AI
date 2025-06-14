import sys
import traceback
import google.generativeai as genai
import os
import json
import requests # Para chamadas HTTP síncronas

class Artoriasbot:
    def __init__(self):
        self.conversation_states = {} # Histórico em memória apenas

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)

        self.gemini_model_name = 'gemini-2.0-flash' 
        self.gemini_api_key = gemini_api_key
        
        self.generation_config = {"temperature": 0.9, "maxOutputTokens": 500} 

        print(f"Artoriasbot: Modelo Gemini configurado para {self.gemini_model_name} (orgânico, chamada síncrona).")

        # Configuração para salvar leads extraídos (agora síncrona, se o DB for síncrono ou chamado via requests)
        # O pool de BD será inicializado para a tabela de leads apenas quando _save_extracted_data for chamado
        self.db_pool = None # Pool de conexões (apenas se for usar BD para leads)

    # NOVO: Inicializa pool de BD APENAS para leads (se for usar BD)
    def _init_db_pool_for_leads(self):
        """Inicializa o pool de conexões com o banco de dados para salvar leads."""
        # Se você decidir reintroduzir o BD para SALVAR O JSON FINAL, você pode adaptar isso.
        # Por enquanto, se o BD foi removido, esta função e seu uso serão ignorados ou adaptados.
        pass # Não faz nada nesta versão sem BD

    # REMOVIDO: _load_conversation_history, _save_conversation_entry (não haverá histórico no BD)

    def _save_extracted_data(self, user_id: str, data: dict, action_type: str):
        """Salva os dados estruturados extraídos (SDR/Suporte) no banco de dados.
           Temporariamente, imprime no console, pois o BD foi removido."""
        # Esta função será o ponto de integração para o BD de leads
        # Por enquanto, apenas imprime, mas futuramente salvará no BD.
        print(f"Artoriasbot: Dados '{action_type}' prontos para serem salvos: {data}")
        # Implementação real de salvamento no BD viria aqui, usando por exemplo psycopg2-binary de forma síncrona.
        # Ex:
        # import psycopg2
        # conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        # cur = conn.cursor()
        # cur.execute("INSERT INTO extracted_leads_tickets (user_id, action_type, data_json, timestamp) VALUES (%s, %s, %s, NOW());",
        #             (user_id, action_type, json.dumps(data)))
        # conn.commit()
        # cur.close()
        # conn.close()
        # print(f"Artoriasbot: Dados extraídos de '{action_type}' SALVOS no BD para '{user_id}'.")


    def process_message(self, user_message: str, user_id: str = "default_user") -> str: # Síncrono
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        # Histórico em memória apenas
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
                f"3.  **Gerar os dados em formato de registro (JSON) estruturado** ao final do fluxo, quando todas as informações forem coletadas. O usuário NÃO verá este registro na conversa, apenas a mensagem final.\n" # <-- ATUALIZADO
                f"4.  **Manter um tom profissional e útil**, sendo conciso, mas completo na resposta.\n"
                f"\n"
                f"--- REGRAS DE FLUXO E COLETA DE DADOS ---\n"
                f"**Priorize sempre coletar informações para SDR ou Suporte. Tente encaixar o usuário em um desses fluxos.**\n"
                f"1.  **QUALIFICAÇÃO SDR (SEQUÊNCIA PRIORITÁRIA):**\n"
                f"    Informações a coletar sequencialmente para SDR:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades.\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    e. E-mail de contato e/ou número de WhatsApp.\n"
                f"    Ao final do fluxo SDR (todas as infos coletadas), forneça a mensagem final para o usuário (ex: 'Obrigado(a)! Sua solicitação foi registrada.') e, em uma nova linha, **então adicione o bloco JSON** (o usuário não verá este bloco).\n" # <-- ATUALIZADO
                f"    ```json\n"
                f"    {{\"action\": \"sdr_completed\", \"lead_info\": {{\"nome\": \"[Nome]\", \"funcao\": \"[Funcao]\", \"empresa\": \"[Empresa]\", \"desafios\": \"[Desafios]\", \"tamanho\": \"[Tamanho]\", \"email\": \"[Email]\", \"whatsapp\": \"[WhatsApp]\"}}}}\n"
                f"    ```\n"
                f"2.  **SUPORTE TÉCNICO (SEQUÊNCIA PRIORITÁRIA):**\n"
                f"    Informações a coletar sequencialmente para Suporte:\n"
                f"    a. Descrição detalhada do problema.\n"
                f"    b. Informações de contato (nome, e-mail, empresa).\n"
                f"    Ao final do fluxo de Suporte (todas as infos coletadas), forneça a mensagem final para o usuário (ex: 'Certo! Seu caso foi registrado.') e, em uma nova linha, **então adicione o bloco JSON** (o usuário não verá este bloco).\n" # <-- ATUALIZADO
                f"    ```json\n"
                f"    {{\"action\": \"support_escalated\", \"ticket_info\": {{\"problema\": \"[Problema]\", \"nome_contato\": \"[Nome Contato]\", \"email_contato\": \"[Email Contato]\", \"empresa_contato\": \"[Empresa Contato]\"}}}}\n"
                f"    ```\n"
                f"\n"
                f"--- COMPORTAMENTO GERAL ---\n"
                f"1.  **Sempre tente encaixar o usuário em um dos fluxos (SDR ou Suporte).** Se a intenção for clara, comece pelo passo 1 do fluxo. Se o usuário fornecer informações para ambos os fluxos, priorize o SDR.\n"
                f"2.  **Se o usuário fornecer todas as informações necessárias para um fluxo em um único turno, responda a mensagem final e inclua o JSON na mesma resposta.**\n"
                f"3.  **Se o usuário desviar ou perguntar algo não relacionado, redirecione-o ao fluxo, pedindo a próxima informação necessária.**\n"
                f"4.  Se o usuário se despedir ou agradecer, responda cordialmente.\n"
                f"5.  Se não entender, peça para reformular.\n"
                f"6.  **Se o usuário perguntar 'o que é JSON' ou sobre o formato dos dados, explique de forma simples e contextualizada (ex: 'É um formato para organizar informações, como um formulário digital').**\n" # ADICIONADO
                f"---"
            )

            # Prepara o histórico para o Gemini na payload da requisição HTTP
            gemini_contents = []
            
            # Adiciona a system_instruction como a primeira parte do "user" role
            gemini_contents.append({"role": "user", "parts": [{"text": system_instruction}]})
            
            # Adiciona a resposta inicial do bot (se aplicável ao primeiro turno da conversa)
            if not current_flow_state["history"]: # Se é o início da conversa
                gemini_contents.append({"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]})
            else:
                gemini_contents.extend(current_flow_state["history"])

            # Adiciona a mensagem atual do usuário
            gemini_contents.append({"role": "user", "parts": [{"text": user_message}]})

            # --- CHAMADA SÍNCRONA DIRETA PARA A API DO GEMINI VIA REQUESTS ---
            # Usa o nome do modelo e a API key para a URL
            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model_name}:generateContent?key={self.gemini_api_key}"
            
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": gemini_contents, # O histórico completo
                "generationConfig": {
                    "temperature": self.generation_config["temperature"], 
                    "maxOutputTokens": self.generation_config["maxOutputTokens"]
                }
            }
            
            gemini_raw_response = requests.post(gemini_api_url, headers=headers, json=payload)
            gemini_raw_response.raise_for_status() # Levanta um erro para status 4xx/5xx
            
            gemini_json_response = gemini_raw_response.json()
            
            if gemini_json_response and "candidates" in gemini_json_response and gemini_json_response["candidates"]:
                response_content = gemini_json_response["candidates"][0]["content"]["parts"][0]["text"]
                
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
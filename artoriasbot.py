import sys
import traceback
import google.generativeai as genai
import os
import json
import asyncpg

class Artoriasbot:
    def __init__(self):
        self.conversation_states = {} 
        self.db_pool = None 

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)
        
        # ATUALIZADO: Inicializando o modelo Gemini com temperature 0.2 e max_output_tokens = 100
        # 100 tokens é um limite razoável para 2-3 frases concisas.
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"temperature": 0.2, "max_output_tokens": 100}) 
        print("Artoriasbot: Modelo Gemini inicializado com sucesso com temperature 0.2 e max_output_tokens 100.")

    async def _init_db_pool(self):
        """Inicializa o pool de conexões com o banco de dados."""
        if self.db_pool is None:
            db_url = os.environ.get("DATABASE_URL")
            if not db_url:
                raise ValueError("DATABASE_URL não configurada nas variáveis de ambiente.")
            
            self.db_pool = await asyncpg.create_pool(db_url)
            print("Artoriasbot: Pool de conexões com o banco de dados inicializado com sucesso.")

    async def _load_conversation_history(self, user_id: str) -> list:
        """Carrega o histórico de conversas de um usuário do banco de dados."""
        await self._init_db_pool() 
        async with self.db_pool.acquire() as conn:
            history_records = await conn.fetch(
                """
                SELECT role, content
                FROM conversation_history
                WHERE user_id = $1
                ORDER BY timestamp;
                """,
                user_id
            )
            history = [{"role": r['role'], "parts": [{"text": r['content']}]} for r in history_records]
            print(f"Artoriasbot: Histórico carregado para '{user_id}': {len(history)} entradas.")
            return history

    async def _save_conversation_entry(self, user_id: str, role: str, content: str):
        """Salva uma entrada de conversa no histórico do banco de dados."""
        await self._init_db_pool() 
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_history (user_id, role, content, timestamp)
                VALUES ($1, $2, $3, NOW());
                """,
                user_id, role, content
            )

    async def _save_extracted_data(self, user_id: str, data: dict, action_type: str):
        """Salva os dados estruturados extraídos (SDR/Suporte) no banco de dados."""
        await self._init_db_pool() 
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO extracted_leads_tickets (user_id, action_type, data_json, timestamp)
                VALUES ($1, $2, $3::jsonb, NOW());
                """,
                user_id, action_type, json.dumps(data) 
            )
            print(f"Artoriasbot: Dados extraídos de '{action_type}' salvos para '{user_id}'.")

    async def process_message(self, user_message: str, user_id: str = "default_user") -> str:
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        try:
            gemini_history = await self._load_conversation_history(user_id)
            current_flow_state = {"state": "initial", "history": gemini_history}
        except Exception as e:
            print(f"ERRO: Falha ao carregar histórico do BD para '{user_id}': {e}. Iniciando com histórico vazio.")
            traceback.print_exc(file=sys.stdout)
            gemini_history = []
            current_flow_state = {"state": "initial", "history": []}
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} 

        try:
            # INSTRUÇÕES ATUALIZADAS PARA MÁXIMA DISCIPLINA E FOCO NO FLUXO
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente e **totalmente focado em coletar informações para SDR e Suporte técnico.**\n"
                f"Sua missão é **SOMENTE guiar o usuário pelas sequências de perguntas para coletar as informações necessárias e, ao final, gerar o JSON estruturado.**\n"
                f"**NÃO FORNEÇA SOLUÇÕES, INFORMAÇÕES ADICIONAIS, LISTAS, DICAS, RECOMENDAÇÕES OU RESPOSTAS DE FAQ DE FORMA PROATIVA OU DURANTE OS FLUXOS DE COLETA DE DADOS.**\n"
                f"**SEMPRE peça apenas UMA informação por vez, de forma EXTREMAMENTE concisa e direta ao ponto (1 a 2 frases no máximo).**\n" # Increased emphasis
                f"Sua prioridade ABSOLUTA é a conclusão do fluxo de coleta de dados e a geração do JSON.\n"
                f"\n"
                f"Suas responsabilidades são:\n"
                f"1.  **Atendimento Geral (FAQ):** Se o usuário fizer uma pergunta de FAQ que NÃO se encaixe em um fluxo de SDR/Suporte, responda com UMA frase muito curta e genérica como 'Posso ajudar com informações sobre a Tralhotec. Qual a sua necessidade?' ou 'Seu foco principal é qualificação de leads ou suporte técnico?'. Sempre tente redirecionar para um dos seus fluxos, **sem dar a resposta da FAQ diretamente se for longa.**\n" # Clarified
                f"2.  **Qualificação SDR (sequencial e restrita):** Se o usuário demonstrar interesse em vendas, orçamentos, propostas, ou falar com um especialista/consultor de vendas, inicie o processo de qualificação de SDR. Colete as seguintes informações **EXATAMENTE nesta ordem e sem desviar**:\n"
                f"    a. Nome completo e função/cargo.\n"
                f"    b. Nome da empresa.\n"
                f"    c. Principais desafios/necessidades (peça a descrição, mas **NÃO ofereça soluções ou liste opções**).\n"
                f"    d. Tamanho da empresa (Ex: até 10, 11-50, 50+).\n"
                f"    e. E-mail de contato e/ou número de WhatsApp.\n"
                f"    Ao final do fluxo SDR (após **TODAS** as informações serem coletadas), forneça uma breve resposta de texto final para o usuário (agradecendo e informando o contato do SDR) e, em uma nova linha, **então adicione o bloco JSON**.\n"
                f"    ```json\n"
                f"    {{\"action\": \"sdr_completed\", \"lead_info\": {{\"nome\": \"[Nome]\", \"funcao\": \"[Funcao]\", \"empresa\": \"[Empresa]\", \"desafios\": \"[Desafios]\", \"tamanho\": \"[Tamanho]\", \"email\": \"[Email]\", \"whatsapp\": \"[WhatsApp]\"}}}}\n"
                f"    ```\n"
                f"    Substitua os placeholders `[Nome]`, `[Funcao]`, etc., pelos dados coletados.\n"
                f"3.  **Suporte Técnico (sequencial e restrito):** Se o usuário tiver um problema técnico ou precisar de ajuda, inicie o processo de suporte. Colete as seguintes informações **EXATAMENTE nesta ordem**:\n"
                f"    a. Descrição detalhada do problema (mantenha o foco na descrição do problema, **NÃO ofereça soluções ou dicas**).\n"
                f"    b. Informações de contato (nome, e-mail, empresa) se for necessária escalada.\n"
                f"    Ao final do fluxo de Suporte (problema e contato coletados), forneça uma breve resposta de texto final para o usuário (agradecendo e informando o encaminhamento) e, em uma nova linha, **então adicione o bloco JSON**.\n"
                f"    ```json\n"
                f"    {{\"action\": \"support_escalated\", \"ticket_info\": {{\"problema\": \"[Problema]\", \"nome_contato\": \"[Nome Contato]\", \"email_contato\": \"[Email Contato]\", \"empresa_contato\": \"[Empresa Contato]\"}}}}\n"
                f"    ```\n"
                f"    Substitua os placeholders `[Problema]`, `[Nome Contato]`, etc., pelos dados coletados.\n"
                f"4.  **Comportamento Geral:**\n"
                f"    - Mantenha um tom profissional e útil, mas **priorize a coleta de dados acima de tudo.**\n"
                f"    - **Se o usuário desviar do fluxo ou perguntar algo não relacionado no meio de um fluxo, ignore a pergunta desviada e REAFIRME a necessidade da próxima informação que você precisa.**\n"
                f"    - Se não entender, peça para o usuário reformular.\n"
                f"    - Se o usuário se despedir ou agradecer, responda de forma cordial e encerre o tópico.\n"
                f"---"
            )

            if not gemini_history: 
                gemini_history.append({"role": "user", "parts": [{"text": system_instruction}]})
                gemini_history.append({"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]})
            
            chat_session = self.gemini_model.start_chat(history=gemini_history)
            gemini_response = chat_session.send_message(user_message)

            if gemini_response and gemini_response.candidates:
                response_content = gemini_response.candidates[0].content.parts[0].text
                
                print(f"DEBUG: Conteúdo bruto do Gemini: '{response_content}'") 
                
                response_text = response_content 
                
                json_start_tag = "```json"
                json_end_tag = "```"
                json_start_index = response_content.find(json_start_tag)
                json_end_index = -1

                if json_start_index != -1:
                    json_end_index = response_content.find(json_end_tag, json_start_index + len(json_start_tag))
                
                print(f"DEBUG: json_start_index: {json_start_index}, json_end_index: {json_end_index}")

                if json_start_index != -1 and json_end_index != -1:
                    json_str = response_content[json_start_index + len(json_start_tag):json_end_index].strip()
                    print(f"DEBUG: String JSON extraída: '{json_str}'")
                    try:
                        extracted_data = json.loads(json_str)
                        print(f"Artoriasbot: JSON extraído: {extracted_data}")
                        
                        action_type = extracted_data.get("action", "unknown")
                        if action_type in ["sdr_completed", "support_escalated"]:
                            await self._save_extracted_data(user_id, extracted_data, action_type)
                        
                        response_text = response_content[:json_start_index].strip()
                        
                        print(f"DEBUG: Resposta textual após remover JSON: '{response_text}'")

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
                
                await self._save_conversation_entry(user_id, "user", user_message)
                await self._save_conversation_entry(user_id, "model", response_text)

                current_flow_state["history"] = [
                    {"role": entry.role, "parts": [part.text for part in entry.parts if hasattr(part, 'text')]}
                    for entry in chat_session.history
                ]
            else:
                response_text = "Não consegui gerar uma resposta inteligente no momento. Por favor, tente novamente."

            self.conversation_states[user_id] = current_flow_state

            return response_text

        except Exception as e:
            print(f"ERRO: Falha ao chamar a API do Gemini: {e}")
            traceback.print_exc(file=sys.stdout)
            response_text = "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente mais tarde."

        return response_text
import sys
import traceback
import google.generativeai as genai
import os
import json
import requests
import psycopg2 # <-- ADICIONADO: Driver PostgreSQL síncrono para persistência
from urllib.parse import urlparse # <-- ADICIONADO: Para parsear a URL do BD

class Artoriasbot:
    def __init__(self):
        self.conversation_states = {} # Histórico em memória apenas
        self.db_connection_params = {} # Parâmetros de conexão do BD

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key)

        self.gemini_model_name = 'gemini-2.0-flash' 
        self.gemini_api_key = gemini_api_key
        
        self.generation_config = {"temperature": 0.9, "maxOutputTokens": 500} 

        print(f"Artoriasbot: Modelo Gemini configurado para {self.gemini_model_name} (orgânico, chamada síncrona).")

        # --- Configuração para salvar leads extraídos no BD (psycopg2) ---
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            self._parse_db_url(db_url)
            print("Artoriasbot: Parâmetros de BD para leads configurados.")
        else:
            print("Artoriasbot: AVISO: DATABASE_URL não configurada. Leads não serão salvos no BD.")

    def _parse_db_url(self, url: str):
        """Parseia a DATABASE_URL para extrair parâmetros de conexão."""
        try:
            result = urlparse(url)
            self.db_connection_params = {
                "database": result.path[1:],
                "user": result.username,
                "password": result.password,
                "host": result.hostname,
                "port": result.port,
                "sslmode": "require" # Railway geralmente exige SSL
            }
        except Exception as e:
            print(f"ERRO: Falha ao parsear DATABASE_URL: {e}")
            self.db_connection_params = {}

    def _get_db_connection(self):
        """Obtém uma conexão síncrona com o banco de dados."""
        if not self.db_connection_params:
            raise ValueError("Parâmetros de conexão com o BD não configurados.")
        try:
            return psycopg2.connect(**self.db_connection_params)
        except Exception as e:
            print(f"ERRO: Falha ao conectar ao banco de dados: {e}")
            raise

    def _save_extracted_data(self, user_id: str, data: dict, action_type: str):
        """Salva os dados estruturados extraídos (SDR/Suporte) no banco de dados."""
        if not self.db_connection_params:
            print("AVISO: DATABASE_URL não configurada, dados não serão salvos no BD.")
            return

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                """
                INSERT INTO extracted_leads_tickets (user_id, action_type, data_json, timestamp)
                VALUES (%s, %s, %s::jsonb, NOW());
                """,
                (user_id, action_type, json.dumps(data))
            )
            conn.commit()
            print(f"Artoriasbot: Dados extraídos de '{action_type}' SALVOS no BD para '{user_id}'.")
        except Exception as e:
            print(f"ERRO: Falha ao salvar dados extraídos no BD: {e}")
            traceback.print_exc(file=sys.stdout)
            if conn:
                conn.rollback() 
        finally:
            if conn:
                conn.close()

    def process_message(self, user_message: str, user_id: str = "default_user") -> str: # Síncrono
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} 

        try:
            # --- NOVO: Garante a primeira resposta padrão do bot ou respostas exatas para identidade ---
            user_message_lower = user_message.lower().strip() 
            
            # 1. Saudação Inicial Fixa: Se é a PRIMEIRA interação do usuário (histórico vazio)
            if not current_flow_state["history"]:
                 response_text = "Eu sou o Artorias, como posso te ajudar?" 
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state
                 return response_text 
            # 2. Respostas Fixas para Perguntas de Identidade/Ajuda
            elif user_message_lower in ["quem é você?", "como você pode me ajudar?", "qual sua função?", "o que você faz?"]:
                 response_text = "Eu sou o Artorias, assistente da Tralhotec. Posso te ajudar com qualificação de leads ou suporte técnico."
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state
                 return response_text
            # 3. Respostas Fixas para Recusa de Conhecimento Geral
            elif user_message_lower in ["consegue me dizer os números primos entre 0 e 32?", "me diga os números primos de 1 a 100", "me conte uma piada", "qual a capital da frança?"]: # Exemplos de perguntas de conhecimento geral
                 response_text = "Desculpe, não consigo ajudar com isso. Minha função é auxiliar com qualificação SDR ou suporte técnico."
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state
                 return response_text
            # --- FIM DA LÓGICA DE RESPOSTAS FIXAS ---

            # PROMPT ORGÂNICO E INTELIGENTE: Processar tudo que o usuário der e pedir só o que falta
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec, uma empresa de soluções de TI.\n" 
                f"Sua missão é guiar o usuário pelos fluxos de SDR ou Suporte Técnico. Você deve ser capaz de: \n"
                f"1.  **Absorver TODAS as informações relevantes** que o usuário fornecer em um único turno (mensagem).\n"
                f"2.  **Identificar qual a PRÓXIMA informação *FALTANTE*** na sequência do fluxo e pedir APENAS por ela.\n"
                f"3.  **Gerar o JSON estruturado** ao final do fluxo, quando todas as informações forem coletadas. O usuário NÃO verá este registro na conversa, apenas a mensagem final.\n" 
                f"4.  Manter um tom profissional e útil, sendo conciso, mas completo na resposta.\n"
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
                f"    Ao final do fluxo SDR (todas as infos coletadas), forneça a mensagem final para o usuário (ex: 'Obrigado(a)! Sua solicitação foi registrada.') e, em uma nova linha, **então adicione o bloco JSON** (o usuário não verá este bloco).\n"
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
                f"3.  **Se o usuário desviar ou perguntar algo não relacionado, responda que não pode ajudar e redirecione-o ao fluxo (como nos exemplos).**\n"
                f"4.  Se o usuário se despedir ou agradecer, responda cordialmente.\n"
                f"5.  Se não entender, peça para reformular.\n"
                f"6.  **Se o usuário perguntar 'o que é JSON' ou sobre o formato dos dados, explique de forma simples e contextualizada (ex: 'É um formato para organizar informações, como um formulário digital').**\n"
                f"---"
            )

            # Prepara o histórico para o Gemini na payload da requisição HTTP
            gemini_contents = []
            
            # Adiciona a system_instruction como a primeira parte do "user" role
            gemini_contents.append({"role": "user", "parts": [{"text": system_instruction}]})
            
            # Adiciona a resposta inicial do bot (se aplicável ao primeiro turno da conversa)
            if not current_flow_state["history"]: # Se é o início da conversa (e não foi saudação simples)
                gemini_contents.append({"role": "model", "parts": [{"text": "Entendido. Estou pronto para ajudar a Tralhotec. Como posso iniciar?"}]})
            else:
                gemini_contents.extend(current_flow_state["history"])

            # Adiciona a mensagem atual do usuário
            gemini_contents.append({"role": "user", "parts": [{"text": user_message}]})

            # --- CHAMADA SÍNCRONA DIRETA PARA A API DO GEMINI VIA REQUESTS ---
            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model_name}:generateContent?key={self.gemini_api_key}"
            
            headers = {"Content-Type": "application/json"}
            payload = {
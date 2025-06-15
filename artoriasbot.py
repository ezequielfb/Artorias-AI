import sys
import traceback
import google.generativeai as genai
import os
import json
import requests
import psycopg2 # Importa o driver PostgreSQL síncrono para persistência de dados


class Artoriasbot:
    """
    Classe principal do Artorias AI, responsável por processar mensagens de usuários,
    interagir com a API do Google Gemini e gerenciar o estado da conversa em memória.
    Também inclui lógica para salvar dados extraídos em um banco de dados PostgreSQL.
    """

    def __init__(self):
        """
        Inicializa o bot, configurando a API do Gemini e os parâmetros
        de conexão com o banco de dados.
        """
        # Dicionário para armazenar o histórico de conversa de cada usuário em memória RAM.
        # Ele reseta a cada reinício do bot, o que está de acordo com o objetivo atual.
        self.conversation_states = {}

        # Dicionário para armazenar parâmetros de conexão com o BD para salvar leads.
        # Será preenchido se DATABASE_URL estiver configurada.
        self.db_connection_params = {}

        # --- Configuração da API do Gemini ---
        # A chave de API é lida das variáveis de ambiente (localmente do .env, em produção do Render).
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            # Se a chave não estiver configurada, um erro é levantado, impedindo o bot de iniciar.
            raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
        genai.configure(api_key=gemini_api_key) # Configura a API key globalmente para a biblioteca genai

        # Define o nome do modelo Gemini a ser usado. 'gemini-2.0-flash' é uma escolha balanceada.
        self.gemini_model_name = 'gemini-2.0-flash'
        # Armazena a API key localmente para uso direto na chamada HTTP com requests.
        self.gemini_api_key = gemini_api_key

        # Configurações de geração para o modelo Gemini.
        # temperature: Controla a aleatoriedade/criatividade da resposta (0.0 = previsível, 1.0 = criativo).
        #              0.9 é um bom balanço para conversas "orgânicas".
        # maxOutputTokens: Limita o tamanho máximo da resposta gerada em tokens.
        #                  500 tokens é um limite generoso para a maioria das respostas do bot.
        self.generation_config = {"temperature": 0.9, "maxOutputTokens": 500}

        print(f"Artoriasbot: Modelo Gemini configurado para {self.gemini_model_name} (orgânico, chamada síncrona).")

        # --- Configuração para salvar leads extraídos no BD (psycopg2) ---
        # Tenta ler a URL de conexão do banco de dados das variáveis de ambiente.
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            # Se a URL do BD existe, tenta parseá-la para extrair os parâmetros de conexão.
            self._parse_db_url(db_url)
            print("Artoriasbot: Parâmetros de BD para leads configurados.")
        else:
            # Aviso se a URL do BD não estiver configurada. Os leads não serão salvos no BD.
            print("Artoriasbot: AVISO: DATABASE_URL não configurada. Leads não serão salvos no BD.")

    def _parse_db_url(self, url: str):
        """
        Parseia a DATABASE_URL fornecida para extrair os parâmetros de conexão
        necessários para o psycopg2.
        Args:
            url (str): A string de conexão do banco de dados (ex: postgresql://user:pass@host:port/dbname).
        """
        try:
            # Importa urlparse dentro da função para evitar erro de importação se não for usada.
            from urllib.parse import urlparse
            result = urlparse(url)
            # Extrai componentes da URL e os armazena no dicionário db_connection_params.
            self.db_connection_params = {
                "database": result.path[1:],  # Nome do banco (ex: 'railway')
                "user": result.username,      # Usuário do banco
                "password": result.password,  # Senha do usuário
                "host": result.hostname,      # Host do banco
                "port": result.port,          # Porta do banco
                "sslmode": "require"          # Modo SSL, comum para bancos em nuvem como Railway.
            }
        except Exception as e:
            print(f"ERRO: Falha ao parsear DATABASE_URL: {e}")
            # Em caso de erro, os parâmetros de conexão ficam vazios, desativando o salvamento no BD.
            self.db_connection_params = {}

    def _get_db_connection(self):
        """
        Obtém e retorna uma nova conexão síncrona com o banco de dados PostgreSQL.
        Levanta um erro se os parâmetros de conexão não estiverem configurados ou se a conexão falhar.
        Returns:
            psycopg2.connection: Um objeto de conexão com o banco de dados.
        """
        if not self.db_connection_params:
            # Garante que os parâmetros de conexão existam antes de tentar conectar.
            raise ValueError("Parâmetros de conexão com o BD não configurados.")
        try:
            # Conecta ao banco de dados usando os parâmetros parseados.
            return psycopg2.connect(**self.db_connection_params)
        except Exception as e:
            print(f"ERRO: Falha ao conectar ao banco de dados: {e}")
            raise # Re-levanta o erro para ser tratado mais acima no traceback.

    def _save_extracted_data(self, user_id: str, data: dict, action_type: str):
        """
        Salva os dados estruturados extraídos (leads SDR ou tickets de suporte) no banco de dados.
        Esta função é chamada APENAS quando um JSON é extraído com sucesso ao final de um fluxo.
        Args:
            user_id (str): ID do usuário para associar o dado (ex: 'test_user_123').
            data (dict): O dicionário Python contendo os dados extraídos (convertido para JSONB no BD).
            action_type (str): Tipo de ação (ex: 'sdr_completed', 'support_escalated').
        """
        if not self.db_connection_params:
            # Se a DATABASE_URL não foi configurada, não tenta salvar e apenas avisa.
            print("AVISO: DATABASE_URL não configurada, dados não serão salvos no BD.")
            return

        conn = None  # Inicializa conn como None para o bloco finally
        try:
            conn = self._get_db_connection() # Obtém uma nova conexão.
            cur = conn.cursor()              # Cria um cursor para executar comandos SQL.

            # Executa o comando INSERT.
            # %s são placeholders para evitar SQL Injection.
            # %s::jsonb converte o JSON string para o tipo JSONB do PostgreSQL.
            cur.execute(
                """
                INSERT INTO extracted_leads_tickets (user_id, action_type, data_json, timestamp)
                VALUES (%s, %s, %s::jsonb, NOW());
                """,
                (user_id, action_type, json.dumps(data)) # Converte o dicionário 'data' para string JSON.
            )
            conn.commit()  # Confirma a transação (salva as mudanças no BD).
            print(f"Artoriasbot: Dados extraídos de '{action_type}' SALVOS no BD para '{user_id}'.")
        except Exception as e:
            # Captura qualquer erro que ocorra durante a conexão ou execução SQL.
            print(f"ERRO: Falha ao salvar dados extraídos no BD: {e}")
            traceback.print_exc(file=sys.stdout) # Imprime o traceback completo do erro.
            if conn:
                conn.rollback() # Desfaz qualquer mudança se a transação falhou.
        finally:
            if conn:
                conn.close() # Sempre fecha a conexão para liberar recursos.


    def process_message(self, user_message: str, user_id: str = "default_user") -> str:
        """
        Processa uma mensagem de texto do usuário, interage com o Gemini,
        e gerencia o fluxo da conversa, incluindo respostas fixas e
        salvamento de dados extraídos. Esta função é totalmente síncrona.

        Args:
            user_message (str): A mensagem de texto enviada pelo usuário.
            user_id (str): Um ID para identificar o usuário (para histórico em memória e BD).
        Returns:
            str: A resposta textual do bot ao usuário.
        """
        print(f"Artoriasbot: Processando mensagem de '{user_id}': '{user_message}'")

        # Recupera o estado atual da conversa do usuário da memória.
        # Se for um novo usuário ou a primeira interação, inicializa com histórico vazio.
        current_flow_state = self.conversation_states.get(user_id, {"state": "initial", "history": []})
        
        # Inicializa a resposta padrão em caso de falha.
        response_text = "Desculpe, não consegui processar sua requisição no momento. Tente novamente."
        extracted_data = {} # Dicionário para armazenar dados extraídos do Gemini.

        try:
            # Normaliza a mensagem do usuário para comparação (minúsculas e sem espaços extras).
            user_message_lower = user_message.lower().strip() 
            
            # --- Lógica de Respostas Fixas e Prioritárias (Hardcoded para garantir comportamento) ---
            # Estas respostas são retornadas IMEDIATAMENTE e o Gemini NÃO é chamado para este turno,
            # garantindo que o bot se comporte EXATAMENTE como desejado para essas interações chave.

            # 1. Saudação Inicial Fixa: Ativada se o histórico da conversa estiver vazio (primeira interação).
            if not current_flow_state["history"]:
                 response_text = "Eu sou o Artorias, como posso te ajudar?" # A frase exata de saudação.
                 # Adiciona a mensagem do usuário e a resposta do bot ao histórico em memória.
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state # Atualiza o estado em memória.
                 return response_text # Retorna a saudação imediatamente.
            
            # 2. Respostas Fixas para Perguntas de Identidade/Ajuda:
            #    Ativadas se o usuário perguntar "quem é você?", "como pode me ajudar?", etc.
            elif user_message_lower in ["quem é você?", "como você pode me ajudar?", "qual sua função?", "o que você faz?"]: 
                 response_text = "Eu sou o Artorias, assistente da Tralhotec. Posso te ajudar com qualificação de leads ou suporte técnico."
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state
                 return response_text
            
            # 3. Respostas Fixas para Recusa de Conhecimento Geral:
            #    Ativadas para perguntas que o bot não deve responder (ex: matemática, história, piadas).
            elif user_message_lower in ["consegue me dizer os números primos entre 0 e 32?", "me diga os números primos de 1 a 100", "me conte uma piada", "qual a capital da frança?", "me fale sobre historia", "me diga os numeros primos entre 0 e 32?", "quais os numeros primos de 0 a 32?"]: 
                 response_text = "Desculpe, não consigo ajudar com isso. Minha função é auxiliar com qualificação SDR ou suporte técnico."
                 current_flow_state["history"].append({"role": "user", "parts": [{"text": user_message}]})
                 current_flow_state["history"].append({"role": "model", "parts": [{"text": response_text}]})
                 self.conversation_states[user_id] = current_flow_state
                 return response_text
            # --- FIM DA LÓGICA DE RESPOSTAS FIXAS FORÇADAS ---

            # --- PROMPT ORGÂNICO E INTELIGENTE (Chamada ao Gemini) ---
            # Este bloco só é executado se nenhuma das respostas fixas acima foi ativada.
            # A partir daqui, o Gemini é chamado para processar a mensagem do usuário
            # e guiar o fluxo de SDR/Suporte de forma orgânica.
            system_instruction = (
                f"Você é Artorias AI, um assistente inteligente para a Tralhotec, uma empresa de soluções de TI.\n" 
                f"Sua missão é guiar o usuário pelos fluxos de SDR ou Suporte Técnico. Você deve ser capaz de: \n"
                f"1.  **Absorver TODAS as informações relevantes** que o usuário fornecer em um único turno (mensagem).\n"
                f"2.  **Identificar qual a PRÓXIMA informação *FALTANTE*** na sequência do fluxo e pedir APENAS por ela.\n"
                f"3.  **Gerar os dados em formato de registro (JSON) estruturado** ao final do fluxo, quando todas as informações forem coletadas. O usuário NÃO verá este registro na conversa, apenas a mensagem final.\n" 
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
                "contents": gemini_contents, # O histórico completo
                "generationConfig": {
                    "temperature": self.generation_config["temperature"], 
                    "maxOutputTokens": self.generation_config["maxOutputTokens"]
                }
            }
            
            gemini_raw_response = requests.post(gemini_api_url, headers=headers, json=payload)
            gemini_raw_response.raise_for_status() 
            
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
                        
                        # --- NOVO: SALVAR DADOS EXTRAÍDOS NO BANCO DE DADOS (AGORA ATIVO) ---
                        action_type = extracted_data.get("action", "unknown")
                        if action_type in ["sdr_completed", "support_escalated"]:
                            self._save_extracted_data(user_id, extracted_data, action_type) # Chamada para salvar o JSON
                        # --- FIM DO NOVO ---
                        
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
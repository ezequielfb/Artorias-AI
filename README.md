# Artorias AI: Agente Conversacional Inteligente

## Visão Geral

O **Artorias AI** é um bot de IA construído em **Python** com **Flask**, utilizando a **API do Google Gemini** para inteligência conversacional. Sua arquitetura **síncrona** garante estabilidade e desempenho.

Ele foi projetado para:

- **Atendimento Inteligente e Orgânico**: Responde a FAQs e interage de forma natural, iniciando sempre com a saudação  
  `"Eu sou o Artorias, como posso te ajudar?"`.

- **Qualificação SDR Eficiente**: Conduz diálogos avançados para coletar dados essenciais de leads  
  (**nome, função, empresa, desafios, tamanho e contato preferencial**).  
  Processa múltiplas informações em um único turno, pedindo apenas o dado faltante.

- **Extração de Dados Estruturados**: Converte informações coletadas em **JSON**, prontas para automação e registro em base de dados.

- **Comportamento Disciplinado**: Recusa perguntas fora do escopo (ex: conhecimento geral) de forma direta, mantendo o foco nas suas funções principais.

---

## Teste o Artorias AI Agora!

**Experimente o bot em ação:**

- **Chat Interativo**: [https://ezequielfb.github.io/Artorias-AI/](https://ezequielfb.github.io/Artorias-AI/)
- **Backend (API)**: [https://artorias-ai-bot.onrender.com/api/messages](https://artorias-ai-bot.onrender.com/api/messages)

---

## Tecnologias

- **Python**: Linguagem principal.
- **Flask**: Framework web para a API do bot.
- **Google Gemini API**: O "cérebro" de IA. Utilizado de forma **síncrona** para garantir estabilidade.
- **python-dotenv**: Gerenciamento seguro de credenciais.
- **requests**: Biblioteca Python para chamadas HTTP síncronas.
- **Flask-Cors**: Gerenciamento de Cross-Origin Resource Sharing para comunicação segura.
- **Git & GitHub**: Controle de versão e hospedagem da interface web.
- **Render**: Plataforma de nuvem para o deploy contínuo e escalável do backend do bot.
- **psycopg2-binary** *(para futura integração de BD)*: Driver para conexão com PostgreSQL.

---

## Como Rodar Localmente (Desenvolvimento)

**Mergulhe no código e experimente o Artorias AI em sua máquina!**

### Pré-requisitos

Certifique-se de ter instalado:

- **Python 3.9+** (Verifique sua versão: `python --version`)
- **Git**
- Uma **Chave de API do Google Gemini**: Essencial para a inteligência do bot.  
  Obtenha a sua em [Google AI Studio](https://makersuite.google.com/).

---

### Configuração Rápida

**Clone este repositório para sua máquina:**

```bash
git clone https://github.com/SEU_USUARIO/Artorias-AI.git
cd Artorias-AI
```

> *(Substitua `SEU_USUARIO` pelo seu nome de usuário no GitHub)*

**Crie e ative um ambiente virtual:**

```bash
python -m venv .venv
.venv\Scripts\activate   # No Windows PowerShell/CMD
# source .venv/bin/activate  # No Linux/macOS ou Git Bash
```

**Instale as dependências essenciais:**

```bash
pip install -r requirements.txt
```

**Configure suas variáveis de ambiente:**

1. Crie um arquivo chamado `.env` na raiz do projeto (na mesma pasta de `app_flask.py`).
2. Adicione sua chave de API do Gemini a ele:

```env
GEMINI_API_KEY=SUA_CHAVE_DE_API_DO_GEMINI_AQUI
```

> *(Este arquivo `.env` é ignorado pelo Git para sua segurança.)*

---

### Executar o Bot

Com seu ambiente virtual ativado, inicie o servidor Flask:

```bash
python app_flask.py
```

O bot estará rodando localmente em:  
[http://127.0.0.1:3979](http://127.0.0.1:3979)

---

## Como Testar a API Localmente

Com o bot rodando (`python app_flask.py`), envie um POST com:

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"text\": \"Olá, Artorias!\"}" http://localhost:3979/api/messages
```

---

## Próximos Passos & Oportunidades Futuras

O **Artorias AI** é uma **prova de conceito poderosa**, com um comportamento refinado e pronto para novas expansões!

- **Persistência de Dados**: integrar o salvamento do JSON final em um banco de dados (PostgreSQL no Railway), garantindo que os leads sejam armazenados permanentemente para acesso externo, sem a necessidade de o bot "lembrar" o histórico completo da conversa.
- **Automação Real**: Utilizar os dados salvos para acionar automações (e-mails de notificação, integração com planilhas/CRMs).
- **Novos Canais**: Expandir a presença do bot para **WhatsApp**, **Slack**, etc.
- **Contêineres (Docker)**: Empacotar o bot em contêineres para facilitar o deploy e a escalabilidade em qualquer ambiente de nuvem.

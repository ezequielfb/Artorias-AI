# Artorias AI - Agente para Atendimento e SDR

## Visão Geral

O **Artorias AI** é um protótipo de agente conversacional desenvolvido em Python com Flask, utilizando a API do Google Gemini como seu "cérebro" de inteligência artificial. Ele é projetado para atuar em duas frentes principais:

1.  **Atendimento Inteligente (FAQ):** Responde a perguntas frequentes sobre produtos, serviços e processos da empresa.
2.  **Qualificação de SDR (Sales Development Representative):** Conduz conversas para coletar informações essenciais de leads (nome, função, empresa, desafios, tamanho), qualificando-os para o time de vendas.

Este projeto representa uma evolução de um bot anterior, com foco em uma arquitetura mais flexível, portável e poderosa, utilizando LLMs (Large Language Models) como base da inteligência.

## Status do Projeto

Atualmente em fase de desenvolvimento e teste local, com integração funcional da API do Google Gemini.

## Como Rodar Localmente

### Pré-requisitos

Certifique-se de ter instalado:

* **Python 3.9+** (Verifique sua versão com `python --version`)
* **Git**
* Uma **Chave de API do Google Gemini**: Obtenha-a no [Google AI Studio](https://aistudio.google.com/apikeys).

### Configuração

1.  **Clone este repositório:**
    ```bash
       git clone https://github.com/ezequielfb/Artorias-AI.git
       cd Artorias-AI
    ```
    ```se você fez um fork para sua conta do GitHub,
       substitua SEU_USUARIO pelo seu nome de usuário:
        git clone https://github.com/SEU_USUARIO/Artorias-AI.git
        cd Artorias-AI
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv .venv
    .venv\Scripts\activate   # No Windows PowerShell/CMD
    # source .venv/bin/activate # No Linux/macOS ou Git Bash
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure suas variáveis de ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto (na mesma pasta de `app_flask.py`).
    Adicione sua chave de API do Gemini a ele:
    ```
    GEMINI_API_KEY=SUA_CHAVE_DE_API_DO_GEMINI_AQUI
    ```
    *(Este arquivo `.env` está no `.gitignore` e não será enviado para o GitHub por segurança.)*

### Executar o Bot

1.  Com o ambiente virtual ativado, inicie o servidor Flask:
    ```bash
    python app_flask.py
    ```
    O bot estará rodando em `http://127.0.0.1:3979`.

## Como Testar Localmente

Com o servidor Flask rodando (`python app_flask.py`):

### Opção 1: Usando `curl` (terminal)

Abra um **novo terminal** e envie uma requisição POST:

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"text\": \"Olá, Artorias!\"}" http://localhost:3979/api/messages
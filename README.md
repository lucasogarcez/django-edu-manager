# 🏛️ Sistema de Gestão Acadêmica

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Aviso: Esta é uma versão de portfólio (sanitizada e anonimizada) baseada em um software real desenvolvido como projeto de extensão universitária (IFTM) para otimizar processos em fundações públicas de esporte e lazer.

## 📌 Visão Geral do Projeto
Plataforma de gestão acadêmica projetada para otimizar fluxos administrativos e matrículas de instituições públicas. Desenvolvida em Django e PostgreSQL, o sistema funde a visão de produto (eficiência em alocações de turmas e modalidades) com engenharia avançada: integração robusta de planilhas, fluxos de saúde dinâmicos e cobertura de testes automatizados.

---

## ✨ Destaques de Engenharia (Features)

*   📊 **Parser de Excel Resiliente:** Algoritmo de varredura customizado (`import_utils.py`) capaz de ingerir dados desestruturados de planilhas complexas, contornando células mescladas, dados ausentes e colisões de chaves compostas (Strict Identity).
*   📋 **Máquina de Estados em Formulários:** Módulo de atestados de saúde dinâmico com intertravamento mecânico de campos. Aplica regras estritas de preenchimento com bypass condicional de validação para a diretoria/secretaria.
*   🛡️ **Segurança e Rate Limit:** Proteção ativa contra ataques de força bruta no painel de autenticação utilizando `django-axes`, incluindo interface gráfica (IHM) de bloqueio com contagem regressiva em cache.
*   🧪 **Testes Automatizados:** Suíte de testes validando desde lógicas internas de modelos (`pytest`) até simulações completas de usuário (End-to-End) para upload de arquivos em formulários multi-etapas utilizando `Playwright`.

---

## 🚀 Live Demo (Acesso Rápido)

O sistema está hospedado na nuvem com um banco de dados populado para demonstração imediata.

🔗 **Acesse a plataforma aqui:** [django-edu-manager.onrender.com](django-edu-manager.onrender.com)

Para auditar as barreiras de segurança, painéis customizados e fluxos de cada nível hierárquico, utilize as credenciais de calibração abaixo. 

🔑 **Senha universal para todas as contas:** `senha123`

| Perfil de Acesso | E-mail de Login (Usuário) | Nível de Permissão na Planta |
| :--- | :--- | :--- |
| **⚙️ Admin (Mestre)** | `admin@portfolio.com` | **Acesso Irrestrito:** Visão global e absoluta de todas as tabelas. Único nível hierárquico com chave de acesso para **responder e fechar** tickets de suporte. |
| **🛡️ Diretoria** | `diretor@portfolio.com` | **Acesso Global:** Gestão total de polos, matrizes curriculares, usuários e auditoria do sistema. |
| **📂 Secretaria** | `secretaria@portfolio.com` | **Operacional:** Gerenciamento de alunos, matrículas, alocação de turmas e emissão de tickets de suporte. |
| **👨‍🏫 Professor** | `professor@portfolio.com` | **Restrito (Multitenancy):** Visualização blindada. Acessa apenas as turmas nas quais está fisicamente alocado (relação N:N). |
| **🧑‍💻 Estagiário** | `estagiario@portfolio.com` | **Super Restrito:** Perfil de leitura/auxílio com bloqueios severos de endpoints para demonstrar validação de backend. |

> **💡 Dica de Teste (Auditoria de Intertravamento de Privilégios):** Qualquer usuário do sistema pode acionar a equipe técnica. Faça login como **Professor** ou **Secretaria** e abra um Ticket de Suporte. Em seguida, note que a interface bloqueia a sua capacidade de interagir com a resolução. Acesse a conta **Admin (Mestre)** para visualizar todos os chamados abertos e emitir a resposta, validando a proteção contra escalonamento de privilégios.

---

## 🛠️ Tecnologias Utilizadas

*   **Backend:** Python 3, Django, Django REST Framework
*   **Banco de Dados:** PostgreSQL (Produção) / SQLite3 (Testes)
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Bootstrap
*   **Testes:** Pytest, Playwright (E2E E2E Testing)
*   **Infraestrutura:** Docker, Docker Compose
*   **Segurança:** Django Axes (Rate Limiting)

---

## ⚙️ Como Executar o Projeto Localmente

### Pré-requisitos
Certifique-se de ter o [Python](https://www.python.org/) (3.10+) e o [PostgreSQL](https://www.postgresql.org/) instalados em sua máquina.

### 1. Clonando o Repositório
```bash
git clone https://github.com/lucasogarcez/django-edu-manager.git
cd django-edu-manager
```

### 2. Configurando o Ambiente Virtual
```bash
python -m venv venv
# Ativar no Windows:
venv\Scripts\activate
# Ativar no Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```
### 3. Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto e configure as credenciais básicas do seu banco de dados local:

```
SECRET_KEY=sua_chave_secreta_aqui
DEBUG=True
DB_NAME=nome_do_banco
DB_USER=usuario_postgres
DB_PASSWORD=senha_postgres
DB_HOST=localhost
DB_PORT=5432
```

### 4. Preparando o Banco de Dados e Populando (*Seed*)
```bash
# Criar as tabelas no PostgreSQL
python manage.py makemigrations
python manage.py migrate

# Popular o banco com dados falsos realistas, grupos e criar o superusuário de testes
python manage.py setup_grupos
python manage.py seed_portfolio
```

### 5. Iniciando o Servidor
```bash
python manage.py runserver
```
Acesse `http://localhost:8000` e utilize as credenciais de demonstração informadas na seção de "Acesso Rápido".

## 🧪 Rodando a Suíte de Testes
Para executar os testes unitários, integração do backend e visuais End-to-End (E2E):
```bash
pytest
```

## 📄 Licença
Este projeto está sob a licença Apache 2.0. Consulte o arquivo [LICENSE](LICENCE) para mais detalhes.

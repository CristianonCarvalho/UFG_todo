# UFG_todo

Micro-API de tarefas para equipes, com prioridade sugerida automaticamente.

## O que o projeto resolve?

Equipes precisam registrar e acompanhar tarefas de forma simples, sem uma ferramenta pesada. A prioridade é sugerida automaticamente para reduzir o trabalho manual, e a pessoa pode ajustá-la depois. O público é o uso interno de uma equipe.

Funcionalidades do MVP:
- criar, listar, detalhar, editar e remover tarefas;
- marcar como concluída e filtrar por status;
- prioridade automática (Jev, com fallback local) e edição manual da prioridade;
- mensagens de erro amigáveis, em português.

## Como instalar e executar?

Pré-requisito: Python 3.12.

1. Crie o ambiente virtual: `python3.12 -m venv .venv`
2. Ative-o: `source .venv/bin/activate`
3. Instale as dependências: `pip install -r requirements-dev.txt`
4. Copie as variáveis de ambiente: `cp .env.example .env`
5. Crie o banco: `alembic upgrade head`
6. Suba a API: `uvicorn app.main:app`

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

| Variável | Obrigatória? | Padrão | Para que serve |
|---|---|---|---|
| `OPENROUTER_API_KEY` | não | (vazia) | chave do OpenRouter para o Jev |
| `OPENROUTER_BASE_URL` | não | `https://openrouter.ai/api` | endereço base do OpenRouter |
| `JEV_MODEL` | não | `typesafe/jev-1.13` | modelo do Jev (versão fixa) |
| `CLASSIFIER_TIMEOUT_SECONDS` | não | `5.0` | tempo máximo de espera pelo Jev |
| `CLASSIFIER_MAX_RETRIES` | não | `1` | novas tentativas em falha temporária |
| `JEV_MIN_CONFIDENCE` | não | `0.5` | confiança mínima aceita do Jev |
| `DATABASE_URL` | não | `sqlite:///./tasks.db` | endereço do banco SQLite |

Sem `OPENROUTER_API_KEY`, a API continua funcionando e a prioridade usa o fallback local.

Endpoints:

| Método e rota | Função |
|---|---|
| `POST /tasks` | criar tarefa |
| `GET /tasks?status=pendente` | listar, com filtro opcional por status (`pendente` ou `concluida`) |
| `GET /tasks/{id}` | detalhar |
| `PATCH /tasks/{id}` | editar campos e prioridade |
| `PATCH /tasks/{id}/complete` | marcar como concluída |
| `DELETE /tasks/{id}` | remover |

## Como rodar os testes?

```bash
pytest
pytest --cov=app
ruff check app tests
mypy app
```

Os testes não usam rede nem precisam de chave de API. Resultado da última execução: 119 testes passando, cobertura total de 94%.

## Quais limites existem?

- **Escopo do MVP:** sem autenticação, sem multiusuário, sem cache nem filas.
- **SQLite:** arquivo local, adequado a uma equipe pequena, sem concorrência alta nem alta disponibilidade.
- **Listagem:** sem paginação.
- **Prioridade automática:** depende de um serviço externo (Jev/OpenRouter). Em falha, usa uma heurística simples por palavras-chave, menos precisa. A pessoa é avisada (`priority_notice`) e pode corrigir.
- **Privacidade:** título e descrição das tarefas são enviados ao OpenRouter/TypeSafe para classificar. Sem chave, nada é enviado.
- **Recalculo:** a prioridade não é recalculada quando título ou descrição são editados.
- **Descrição:** não é possível apagá-la por `PATCH`; só substituí-la.
- **Validações:** título de 1 a 100 caracteres e descrição de até 500.
- **Idioma:** mensagens apenas em português do Brasil.
- **Endpoint do Jev:** a documentação do OpenRouter diverge sobre o endpoint (`/v1/systemone` ou `/alpha/decisions`); ele ainda precisa ser validado com uma chave real.
- **Frontend:** ainda não existe.

## Como a IA foi usada no processo?

**IA no produto (em tempo de execução):** o Jev classifica a prioridade na criação da tarefa, via OpenRouter, com fallback local. Usamos o Jev, e não um LLM de chat, porque ele é um modelo de decisão estruturada, que devolve respostas tipadas com probabilidades.

**IA no desenvolvimento:** o agente de codificação gerou as dependências, a configuração das ferramentas, os schemas, o tratamento de erros, o classificador, o model, o repository, o service, as rotas, os testes, os diagramas, as decisões técnicas, o CI e este README. O fluxo foi: contexto e escopo definidos em prompt, geração, verificação automática (testes, `ruff`, `mypy`, `pip check`) e relatório de evidências para revisão humana.

- Ferramenta/modelo do agente: [preencher]
- Revisão humana feita por: [preencher]

O código gerado por IA foi revisado e validado por testes. As decisões de escopo e as regras de negócio vieram de pessoas.

## Arquitetura

Veja os diagramas e o modelo de dados em [docs/arquitetura.md](docs/arquitetura.md) e as decisões em [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md).

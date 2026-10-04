# Micro-API To-Do — Design

Data: 2026-10-04. Fonte dos requisitos: `spec_inicial.txt` (prevalece) + decisões desta conversa.

## Objetivo

API interna de tarefas (FastAPI, SQLAlchemy 2.x, SQLite, Pydantic v2) com prioridade
automática via Jev (OpenRouter) com fallback local e erros sempre amigáveis em português.
Este ciclo entrega dependências, schemas, erros, classificador, testes, documentação e CI.
Rotas, models ORM, services, repositories e `app/main.py` ficam para um ciclo posterior.

## Decisões desta conversa

| Tema | Decisão |
|---|---|
| Execução | Direta na sessão, commits pequenos por funcionalidade (Conventional Commits, em português). O meister fica só como configuração do projeto |
| Idioma | Docstrings em português, estilo Google, em módulos, classes e funções públicas; nos schemas, uma linha por classe |
| Testes | Unitários do classificador e dos erros, sem rede. Integração adiada até existirem as rotas |
| Python | 3.12 fixado em `.python-version` e `requires-python = ">=3.12,<3.13"` |
| Lockfile | Não (versões diretas fixadas com `==`) |
| Ferramentas | `ruff` (com regras `D`, convenção Google), `black`, `mypy` e `pytest` configurados no `pyproject.toml` |
| Mermaid | Validar com `npx @mermaid-js/mermaid-cli` |
| README e CI | Incluídos. CI com lint, tipos e testes |
| Frontend | Fora deste ciclo |
| Decisões técnicas | `docs/decisoes-tecnicas.md`, ADRs curtos |
| Endpoint do Jev | `POST {base_url}/v1/systemone`, com corpo no formato `choice` do tutorial |
| Modelo do Jev | `typesafe/jev-1.13` (a documentação usa esse id; o spec original dizia `jev-1.13`) |

## Divergência registrada (Jev)

O guia do Jev aponta `/api/v1/systemone`; o tutorial usa `/api/alpha/decisions`. Seguimos
`/v1/systemone` e isolamos a chamada em uma função pequena. Formato de pergunta/resposta
(do tutorial): pergunta `{"type":"choice","instructions":...,"criteria":{opção: descrição}}`;
resposta `{"type":"choice","choice":...,"confidence":...,"probabilities":{...}}`.
Constar em "Pendências" do relatório final: validar com chave real.

## Arquivos

Código (`app/`): `schemas/task.py`, `core/config.py`, `core/errors.py`,
`services/priority_classifier.py`.
Testes: `tests/test_priority_classifier.py`, `tests/test_errors.py`.
Config: `requirements.txt`, `requirements-dev.txt`, `.env.example`, `pyproject.toml`,
`.python-version`, `.github/workflows/ci.yml`.
Docs: `docs/arquitetura.md` (4 diagramas Mermaid + seção de texto com campos da tarefa e
endpoints), `docs/decisoes-tecnicas.md`, `README.md` (criado por último).

## Dependências (versões consultadas no PyPI em 2026-10-02)

Produção: fastapi 0.142.2, uvicorn[standard] 0.54.0, sqlalchemy 2.1.2, alembic 1.20.0,
pydantic 2.13.5, pydantic-settings 2.15.0, python-dotenv 1.2.4, httpx 0.28.1.
Desenvolvimento (`-r requirements.txt` primeiro): pytest 9.1.1, pytest-cov 7.1.0,
ruff 0.16.10, black 26.5.1, mypy 2.4.0.
Sem drivers de banco, sem SDKs de IA. Compatibilidade confirmada na instalação.

## Schemas (`app/schemas/task.py`)

Enums de texto: `TaskStatus` (pendente, concluida), `TaskPriority` (baixa, media, alta),
`PrioritySource` (jev, fallback, manual).
- `TaskCreate`: `title` (1–100, sem espaços nas pontas, não só espaços), `description`
  (opcional, até 500), `extra="forbid"`.
- `TaskUpdate`: `title`, `description`, `status`, `priority`, todos opcionais, mesmas
  validações, `extra="forbid"`, exige ao menos um campo.
- `TaskOut`: `id`, `title`, `description`, `status`, `priority`, `priority_source`,
  `created_at`, `priority_notice` (`computed_field`, texto fixo quando `fallback`, senão
  `None`), `from_attributes=True`.
Sintaxe Pydantic v2 apenas, `str | None`, mensagens de validação em português.

## Erros (`app/core/errors.py`)

Resposta única `{"erro": {codigo, mensagem, detalhes?, id_requisicao}}` com modelos
`ErrorDetail`, `ErrorBody`, `ErrorResponse`. `id_requisicao` é um UUID por requisição,
também no log. Exceções: `AppError` (base) e `TaskNotFoundError` (404,
`TAREFA_NAO_ENCONTRADA`). `register_exception_handlers(app)` cobre `AppError`,
`RequestValidationError` (422 `DADOS_INVALIDOS`, tradução por tipo de erro e rótulos de
campo), `StarletteHTTPException` (404, 405 e demais em português), `SQLAlchemyError`
(503 `BANCO_INDISPONIVEL`) e `Exception` (500 `ERRO_INTERNO`). O erro real (tipo, mensagem,
traceback) vai para o log em ERROR com o `id_requisicao`, nunca para a resposta, e sem
chave de API, título ou descrição. Falha do Jev não é erro para o usuário.

## Classificador (`app/services/priority_classifier.py`)

`PriorityResult` (dataclass imutável: `priority`, `source` nunca `manual`),
`PriorityClassifier` (`Protocol`), `JevPriorityClassifier` (síncrono, `httpx.Client`
injetável). `classify` nunca levanta exceção. Envia só título e descrição; pergunta
`choice` com `baixa`, `media`, `alta`; usa a opção mais provável; confiança abaixo de
`jev_min_confidence` (0.5) conta como falha. Fallback em: chave ausente, timeout, erro de
rede, não-2xx após tentativas, JSON inválido, opção fora do conjunto, confiança baixa.
Retry (`classifier_max_retries`, padrão 1) só para timeout, rede, 5xx e 429. Depois,
heurística por palavras-chave (alta: urgente, bloqueio, produção, prazo hoje, incidente;
baixa: quando possível, opcional, ideia; senão média), e `media` se a heurística falhar.
Falhas vão para o log em WARNING só com o tipo. Resultados de fallback usam
`source=fallback`.

Configuração (`app/core/config.py`, `pydantic-settings`, lê ambiente e `.env`):
`openrouter_api_key: SecretStr | None`, `openrouter_base_url="https://openrouter.ai/api"`,
`jev_model="typesafe/jev-1.13"`, `classifier_timeout_seconds=5.0`,
`classifier_max_retries=1`, `jev_min_confidence=0.5`.

## Diagramas (`docs/arquitetura.md`)

Quatro blocos Mermaid, cada um com título e uma frase: (1) componentes em `flowchart LR`,
com classificador, fallback, handlers de erro e Jev; (2) `POST /tasks` com `alt` Jev/fallback
e `opt` de falha do banco; (3) `PATCH /tasks/{id}/complete`; (4) `PATCH /tasks/{id}` com
prioridade manual. Sem diagrama para a listagem filtrada.

## Testes

`httpx.MockTransport` para o classificador (sucesso, timeout, 500→200, 500 sempre, 401 sem
retry, JSON inválido, opção inválida, confiança baixa, chave ausente sem requisição,
heurística, nunca levanta exceção). `tests/test_errors.py` com `FastAPI()` mínimo e
`TestClient` cobre 422 (título ausente, 101 caracteres, prioridade inválida, campo extra),
404, 405, 503, 500 (sem vazar "segredo-interno", com `id_requisicao` no log via `caplog`),
formato único em todos os casos e `priority_notice` no `TaskOut`. Cobertura mínima de 90%
em `priority_classifier.py` e `errors.py`.

## Verificação

Venv limpo; `pip install -r requirements-dev.txt`; `pip check`; imports; `select 1` no
SQLite em memória; script dos schemas; `pytest --cov=app`; `ruff check app tests`;
`black --check`; `mypy app`; JSON real de cada erro (422, 404, 405, 503, 500); chamada real
ao Jev só se `OPENROUTER_API_KEY` já existir no ambiente; renderização dos 4 diagramas com
`npx @mermaid-js/mermaid-cli`; validação do README (5 seções na ordem, comandos executados,
tabela de variáveis igual a `.env.example` e `config.py`, links existentes, `[preencher]`
mantidos, "em construção" para a execução da API). Relatório final com as evidências,
pendências, estabilidade e riscos.

## Commits previstos

1. dependências; 2. versão do Python e ferramentas; 3. configuração e `.env.example`;
4. schemas; 5. erros e seus testes; 6. classificador e seus testes; 7. diagramas;
8. decisões técnicas; 9. README; 10. CI. Sem push sem pedido.

## Fora do escopo

Autenticação, cache, filas, Docker, deploy, outros bancos, outros modelos de IA ou SDKs,
reclassificação ao editar título ou descrição (vai para "Pendências"), internacionalização,
rotas, models ORM, services, repositories, `main.py`, frontend, testes de integração.

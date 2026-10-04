# UFG_todo

Micro-API de tarefas para equipes, com prioridade sugerida automaticamente.

> **Estado:** em construção. A execução da API ainda não está disponível; o ponto de entrada e as rotas HTTP não foram implementados.

## Visão geral

O objetivo é permitir que equipes registrem tarefas, acompanhem seu andamento e recebam uma sugestão automática de prioridade. O desenho prevê uma API em camadas, com validação de dados, regras de negócio, acesso a dados e tratamento centralizado de erros.

O código disponível nesta etapa inclui schemas, configurações, classificação de prioridade e tratamento de erros. Rotas, service, repository e persistência ainda fazem parte do desenho futuro.

## Prioridade automática

O classificador consulta o Jev pela API System One do OpenRouter usando `POST {base_url}/v1/systemone` e o modelo `typesafe/jev-1.13`. A chamada é feita com `httpx`, sem SDK de IA. Uma confiança mínima é exigida; se a consulta falhar ou a resposta não for válida, o classificador usa regras locais por palavras-chave e, como último recurso, prioridade média.

O uso do Jev é opcional. Sem uma chave, a classificação usa o fallback local. Os testes não fazem chamadas de rede.

## Requisitos

- Python `>=3.12,<3.13` (versão definida em `.python-version`).
- Dependências diretas com versões fixadas nos arquivos de requisitos.
- Nenhum driver de banco ou SDK de IA é necessário.

## Preparar o ambiente

No macOS ou Linux:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

O arquivo `.env` é opcional. Para usar o Jev, informe a chave em `OPENROUTER_API_KEY`; sem ela, o fallback local continua disponível:

```dotenv
OPENROUTER_API_KEY=[preencher]
OPENROUTER_BASE_URL=https://openrouter.ai/api
JEV_MODEL=typesafe/jev-1.13
CLASSIFIER_TIMEOUT_SECONDS=5.0
CLASSIFIER_MAX_RETRIES=1
JEV_MIN_CONFIDENCE=0.5
```

Não compartilhe nem registre a chave de API. Os nomes e valores padrão das configurações estão disponíveis em `.env.example`.

## Executar

**Em construção:** ainda não há ponto de entrada da aplicação nem rotas para iniciar a API. Os endpoints abaixo descrevem o desenho previsto e não estão disponíveis para uso.

| Método | Caminho previsto | Função |
|---|---|---|
| `POST` | `/tasks` | Criar uma tarefa e sugerir sua prioridade |
| `GET` | `/tasks?status=pendente` | Listar tarefas, com filtro opcional |
| `GET` | `/tasks/{id}` | Consultar uma tarefa |
| `PATCH` | `/tasks/{id}` | Editar campos e prioridade |
| `PATCH` | `/tasks/{id}/complete` | Concluir uma tarefa |
| `DELETE` | `/tasks/{id}` | Remover uma tarefa |

O desenho dos componentes e dos fluxos está em [docs/arquitetura.md](docs/arquitetura.md). As escolhas de tecnologia e comportamento estão em [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md).

## Testes e qualidade

Execute os testes e as verificações a partir da raiz do projeto:

```bash
.venv/bin/pytest --cov=app --cov-report=term-missing
.venv/bin/ruff check app tests
.venv/bin/black --check app tests
.venv/bin/mypy app
.venv/bin/pip check
```

Última execução registrada neste README:

- **Testes:** 55 passaram.
- **Cobertura total:** 96%.
- **Classificador de prioridade:** 96%.
- **Tratamento de erros:** 94%.
- **Ruff, Black e dependências:** verificações aprovadas.
- **Mypy:** ainda não aprovado; aponta uma anotação de tipo ignorada que não é mais necessária.

## Modelo de tarefa previsto

O desenho da tarefa inclui identificador, título (de 1 a 100 caracteres), descrição opcional (até 500 caracteres), estado (`pendente` ou `concluida`), prioridade (`baixa`, `media` ou `alta`), origem da prioridade (`jev`, `fallback` ou `manual`) e data de criação.

Quando uma pessoa define a prioridade manualmente, essa escolha deve prevalecer sobre a classificação automática. O modelo de dados e os endpoints ainda não foram implementados.

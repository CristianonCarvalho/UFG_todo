# Diretrizes de Agentes

## Contexto do projeto

- **Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, httpx, pytest, ruff, black, mypy. Venv em `.venv` (use `.venv/bin/<comando>`).
- **Comando de testes:** `.venv/bin/pytest` (qualidade: `.venv/bin/ruff check app tests`, `.venv/bin/black --check app tests`, `.venv/bin/mypy app`)
- **Convenções:** Docstrings em português (estilo Google) em tudo que for público; mensagens ao usuário em português do Brasil; sem rede nos testes; commits pequenos em Conventional Commits (português) com o trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; não faça push. Plano e spec em `docs/superpowers/`.

## Execução de tarefas

- Siga o escopo e os arquivos-alvo indicados na tarefa recebida.
- Preserve alterações preexistentes e evite mudanças fora do escopo.
- Execute os testes relevantes e relate resultados e limitações com clareza.

## Se você é um worker do MeisterRouter

Considere-se um worker se `MEISTER_IN_PANE=1` estiver definido no ambiente ou se estiver
em uma worktree criada para uma subtarefa. Implemente diretamente a tarefa recebida,
somente nos arquivos-alvo. Execute os testes relevantes e informe as evidências.
Não execute comandos de classificação, execução de workers, orquestração ou controle do
MeisterRouter; não delegue a tarefa a outro agente.

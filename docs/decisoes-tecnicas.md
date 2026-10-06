# Decisões técnicas

Cada decisão segue o formato: contexto, decisão e motivo.

## 1. Arquitetura em camadas
- **Contexto:** a API precisa de regras de negócio testáveis e independentes de HTTP e de banco.
- **Decisão:** controller (rotas e validação), service (regras), repository (SQLAlchemy), mais o classificador e os handlers de erro como componentes isolados.
- **Motivo:** cada camada tem uma responsabilidade e pode ser testada com dublês das vizinhas.

## 2. SQLite com SQLAlchemy 2.x
- **Contexto:** uso interno por equipe pequena, sem necessidade de servidor de banco.
- **Decisão:** SQLite em arquivo local (`tasks.db`) acessado por SQLAlchemy, com Alembic para migrações; sem driver extra, pois o módulo `sqlite3` vem com o Python.
- **Motivo:** simplicidade de instalação. Limite: pouca concorrência e sem alta disponibilidade.

## 3. Versões fixadas, sem lockfile
- **Contexto:** o resultado precisa ser reproduzível.
- **Decisão:** `==` nas dependências diretas, em `requirements.txt` e `requirements-dev.txt`; dependências transitivas ficam a cargo do resolvedor.
- **Motivo:** menos manutenção. Risco: transitivas podem variar entre instalações; um lockfile pode ser adicionado depois.

## 4. Python 3.12 fixado
- **Contexto:** a aplicação e suas dependências precisam de um ambiente Python definido.
- **Decisão:** `.python-version` e `requires-python = ">=3.12,<3.13"` no `pyproject.toml`.
- **Motivo:** evitar diferenças de comportamento entre versões.

## 5. Jev via `httpx`, sem SDK
- **Contexto:** o Jev é um modelo de decisão estruturada (perguntas tipadas e respostas com probabilidades), não um LLM de chat.
- **Decisão:** chamar `POST {base_url}/v1/systemone` com `httpx`, pergunta do tipo `choice` e modelo `typesafe/jev-1.13` (versão fixa).
- **Motivo:** resposta tipada e resultado estável, sem dependência de SDK.
- **Validação:** a documentação do OpenRouter divergia entre `/v1/systemone` (guia) e `/alpha/decisions` (tutorial). Com uma chave real, os dois responderam HTTP 200 com o mesmo formato (`choice`, `probabilities`, `confidence`); o app segue com `/v1/systemone`. Chaves de gerenciamento (`is_management_key`) recebem 401 nesses endpoints, então é preciso uma chave de API comum.

## 6. Fallback obrigatório na prioridade
- **Contexto:** a criação de tarefas não deve depender da disponibilidade do serviço externo de classificação.
- **Decisão:** `classify` nunca levanta exceção. Em falha, tenta de novo (timeout, rede, 5xx, 429), depois usa heurística por palavras-chave e, por último, `media`.
- **Motivo:** falha de serviço externo não pode impedir a criação da tarefa. O aviso ao usuário vem de `priority_notice`.

## 7. Prioridade manual prevalece
- **Contexto:** a pessoa pode corrigir a classificação automática de uma tarefa.
- **Decisão:** ao editar a prioridade, a origem passa a `manual` e o classificador nunca a sobrescreve. A prioridade não é recalculada quando título ou descrição mudam.
- **Motivo:** preservar a escolha explícita e evitar reclassificações inesperadas.

## 8. Tratamento de erros
- **Contexto:** erros técnicos e detalhes internos não devem ser expostos nas respostas da API.
- **Decisão:** exceções de domínio no service; handlers globais convertem tudo em `{"erro": {codigo, mensagem, detalhes?, id_requisicao}}` em português. Banco indisponível vira 503 e erro inesperado vira 500.
- **Motivo:** nenhum detalhe técnico chega ao usuário. O erro real vai para o log com o mesmo `id_requisicao`, sem chave de API, título ou descrição.

## 9. Docstrings em português
- **Contexto:** a documentação do código precisa ser consistente e acessível à equipe.
- **Decisão:** estilo Google, em módulos, classes e funções públicas; o `ruff` (regras `D`) cobra a presença. O idioma é verificado em revisão.
- **Motivo:** facilitar leitura e manutenção do projeto em português.

## 10. Testes sem rede
- **Contexto:** testes devem ser reproduzíveis sem depender de serviços externos ou credenciais.
- **Decisão:** testes unitários do classificador (`httpx.MockTransport`) e dos erros (`TestClient`). Testes de integração entram quando as rotas existirem.
- **Motivo:** validar o comportamento de forma rápida e previsível, sem tráfego de rede.

## 11. Sessão síncrona e rotas `def`
- **Contexto:** o classificador usa `httpx.Client` síncrono e o SQLite não se beneficia de I/O assíncrono.
- **Decisão:** SQLAlchemy síncrono, uma sessão por requisição (`get_db`, com rollback em falha) e rotas declaradas com `def`, que o FastAPI executa em threadpool.
- **Motivo:** menos complexidade e nenhuma chamada bloqueante no loop de eventos.

## 12. Esquema do banco por migração
- **Decisão:** Alembic com a migração `0001`; produção usa `alembic upgrade head`. Os testes criam as tabelas com `Base.metadata.create_all`.
- **Motivo:** evolução do esquema rastreável, sem criar tabelas implicitamente ao subir a API.

## 13. Repository atrás de um `Protocol`
- **Decisão:** o service depende de `TaskRepositoryPort`, e `TaskRepository` o implementa.
- **Motivo:** o service é testado com um repository em memória, sem banco. Os métodos de listagem se chamam `list_tasks` para não sombrear o `list` embutido.

## 14. Regras do `PATCH` e de concluir
- **Decisão:** só campos informados e não nulos são aplicados; por isso a descrição não pode ser apagada. Editar a prioridade grava `manual` (mesmo com o valor igual) e não chama o classificador. Concluir uma tarefa já concluída responde 200.
- **Motivo:** regra simples e previsível; reclassificação ao editar título ou descrição fica como pendência.

## 15. `id` limitado ao intervalo do SQLite
- **Decisão:** `id` na rota exige inteiro entre 1 e 9223372036854775807.
- **Motivo:** um inteiro maior que o suportado pelo SQLite gerava erro interno (500); agora gera 422 amigável.

## 16. Frontend em React com Vite, sem bibliotecas extras
- **Contexto:** a interface precisa ser leve e simples, e o spec já definia React.
- **Decisão:** Vite + React em JavaScript, CSS simples, estado com `useState` e `useEffect` encapsulados no hook `useTasks`; sem Redux, router nem bibliotecas de dados.
- **Motivo:** a tela é uma única página com poucas ações. Menos dependências significam menos manutenção.

## 17. Proxy do Vite em vez de CORS
- **Decisão:** em desenvolvimento, o Vite encaminha `/tasks` para a API; o backend não foi alterado e não tem CORS.
- **Motivo:** mantém o backend intacto. Servir o frontend em outra origem em produção exigirá `CORSMiddleware` ou um servidor de arquivos estáticos.

## 18. Um único módulo fala com a API
- **Decisão:** `api.js` concentra o `fetch`, trata o 204 do `DELETE` e converte o formato `{"erro": {...}}` em `ApiError`; falhas de rede e respostas fora do formato viram mensagens amigáveis.
- **Motivo:** os componentes não conhecem HTTP, e nenhum erro técnico chega ao usuário.

## 19. Sem estado otimista
- **Decisão:** depois de cada ação, o hook recarrega a lista do servidor e ignora respostas antigas quando o filtro muda rápido.
- **Motivo:** a tela sempre reflete o que a API tem, inclusive a origem da prioridade (`jev`, `fallback` ou `manual`).

# Frontend React — Ciclo 3

Data: 2026-10-06. Continua os specs `2026-10-04-todo-api-design.md` (ciclo 1) e
`2026-10-04-todo-api-rotas-design.md` (ciclo 2). O backend está completo e publicado;
este ciclo entrega a interface web que consome a API.

## Objetivo

Uma interface web simples e leve, em React, para a equipe criar, acompanhar e concluir
tarefas, ver a prioridade sugerida pelo Jev (ou pelo fallback) e corrigi-la quando quiser,
mostrando sempre as mensagens amigáveis em português que a API já devolve.

## Decisões deste ciclo

| Tema | Decisão |
|---|---|
| Stack | Vite 8.3.3 + React 19.3.0, JavaScript com JSX (sem TypeScript), CSS simples sem framework |
| Estado | `useState` e `useEffect`, encapsulados em um hook `useTasks`; sem Redux, sem router, sem bibliotecas de dados |
| Escopo (premissa a confirmar) | Criar, listar, filtrar por status, concluir, remover e **editar a prioridade** (regra central do negócio). Editar título e descrição fica de fora |
| Comunicação | `fetch` em um único módulo (`api.js`). Em desenvolvimento, o Vite encaminha `/tasks` para `http://127.0.0.1:8000` (proxy), então o backend não muda e não precisa de CORS |
| Erros | A API já devolve `{"erro": {codigo, mensagem, detalhes?, id_requisicao}}` em português; o frontend exibe `mensagem`, os `detalhes` por campo e o `id_requisicao` quando houver |
| Testes | Vitest + React Testing Library + user-event + jest-dom em jsdom, com `fetch` falso; sem rede e sem backend |
| Lint | Não incluído neste ciclo (YAGNI); a qualidade é garantida por testes e pelo build |
| Dependências | Versões fixadas com `=` exato no `package.json` e `package-lock.json` versionado |
| Idioma | Interface e mensagens em português do Brasil |
| Backend | Nenhuma alteração |

## Versões (consultadas no npm em 2026-10-06; reconferir na execução)

Produção: `react` 19.3.0, `react-dom` 19.3.0.
Desenvolvimento: `vite` 8.3.3, `@vitejs/plugin-react` 6.1.2, `vitest` 5.0.3, `jsdom` 30.1.2,
`@testing-library/react` 16.3.3, `@testing-library/user-event` 14.6.7,
`@testing-library/jest-dom` 7.0.1. Node 26.8.2 e npm 11.19.1 no ambiente atual.

## Estrutura

```
frontend/
├── index.html
├── package.json            # scripts: dev, build, test
├── package-lock.json
├── vite.config.js          # plugin React, proxy /tasks, configuração do Vitest
└── src/
    ├── main.jsx            # monta o App
    ├── App.jsx             # compõe a tela
    ├── api.js              # chamadas HTTP e ApiError
    ├── useTasks.js         # estado da lista, filtro, carregamento e ações
    ├── styles.css
    ├── components/
    │   ├── TaskForm.jsx    # criar tarefa
    │   ├── StatusFilter.jsx
    │   ├── TaskList.jsx
    │   ├── TaskItem.jsx    # concluir, remover, editar prioridade
    │   └── ErrorBanner.jsx
    └── test/
        └── setup.js        # jest-dom
```

Os testes ficam ao lado dos arquivos (`*.test.jsx` e `*.test.js`).

## Camada de API (`src/api.js`)

Funções: `listTasks(status)`, `createTask({title, description})`,
`updateTask(id, changes)`, `completeTask(id)`, `deleteTask(id)`. Todas usam um `request`
interno que:
- envia e recebe JSON; `DELETE` responde 204 sem corpo e retorna `null`;
- em resposta não 2xx, lê `{"erro": {...}}` e lança `ApiError` com `codigo`, `mensagem`,
  `detalhes` (lista de `{campo, mensagem}`) e `idRequisicao`;
- se a resposta não vier no formato esperado, lança `ApiError` com uma mensagem genérica
  amigável;
- se a rede falhar (`fetch` rejeita), lança `ApiError` com
  "Não foi possível conectar ao servidor. Verifique se a API está no ar e tente novamente.".

`status` só vai na query quando for `pendente` ou `concluida` (o filtro "todas" não envia).

## Estado (`src/useTasks.js`)

Expõe `tasks`, `filter`, `setFilter`, `loading`, `error`, `clearError`, `create`, `complete`,
`remove`, `changePriority`. Regras:
- recarrega a lista ao montar e sempre que o filtro muda;
- cada ação chama a API e depois atualiza a lista a partir da resposta do servidor
  (recarregando a lista), sem estado otimista;
- ações em andamento desabilitam os botões da tarefa; `loading` cobre a carga da lista;
- erros viram `error` (um `ApiError`) e são exibidos no banner; `create` devolve os
  `detalhes` por campo ao formulário e não derruba a tela.

## Interface

Uma única página, em português:
- **Cabeçalho:** título "Tarefas".
- **`TaskForm`:** campos título (obrigatório, até 100) e descrição (opcional, até 500), com
  `label`, contador simples ou `maxLength`, botão "Adicionar" e a mensagem de cada campo
  vinda de `detalhes` logo abaixo dele. Limpa os campos após criar com sucesso.
- **`StatusFilter`:** três botões, "Todas", "Pendentes" e "Concluídas", com o ativo
  marcado (`aria-pressed`).
- **`TaskList` e `TaskItem`:** título, descrição, status, e a prioridade com sua origem
  (rótulos: `jev` → "Sugerida pela IA", `fallback` → "Estimativa automática",
  `manual` → "Definida por você"). Quando `priority_notice` vier preenchido, aparece junto
  ao item. Ações: "Concluir" (some quando já concluída), "Remover" (pede confirmação
  inline, sem `window.confirm`) e um `select` de prioridade (baixa, média, alta) que dispara
  `PATCH` e, no sucesso, mostra a origem como "Definida por você".
- **Estados:** carregando, lista vazia ("Nenhuma tarefa por aqui ainda.") e erro.
- **`ErrorBanner`:** região `role="alert"` com `mensagem`, e "Código da requisição: ..."
  quando `idRequisicao` existir; botão para dispensar.
- **Acessibilidade:** `label` associado a cada campo, foco visível, botões com texto, áreas
  de status com `aria-live` quando fizer sentido.

## Testes

Todos com `fetch` falso (`vi.fn`), sem rede e sem backend.
- `api.test.js`: sucesso com corpo, 204 devolve `null`, erro 422 vira `ApiError` com
  `detalhes`, erro 404 e 503 usam a mensagem da API, corpo fora do formato gera mensagem
  genérica, falha de rede gera a mensagem de conexão, filtro "todas" não envia `status`.
- `TaskForm.test.jsx`: envia título e descrição, mostra `detalhes` por campo, limpa após
  sucesso, não limpa após erro.
- `TaskItem.test.jsx`: rótulos de origem da prioridade, `priority_notice` visível só no
  `fallback`, "Concluir" some em tarefa concluída, remover exige confirmação, trocar a
  prioridade chama a ação com o valor escolhido.
- `TaskList.test.jsx` e `StatusFilter.test.jsx`: lista vazia, filtro marca o botão ativo.
- `App.test.jsx` (integração com `fetch` falso): carga inicial, criar uma tarefa e vê-la na
  lista, filtrar, concluir, editar prioridade, remover, e erro da API visível no banner com
  o código da requisição.

## Verificação

`npm ci`, `npm test`, `npm run build`; subir o backend (`uvicorn app.main:app`) e o frontend
(`npm run dev`) e exercitar a tela no navegador: criar, filtrar, concluir, mudar a
prioridade, remover e provocar um erro (título em branco). Verificação visual feita pelo
arquiteto.

## Documentação

- `README.md`: acrescentar a execução do frontend (`cd frontend && npm install`,
  `npm run dev`, `npm test`), e atualizar "Limites" (o frontend deixa de ser pendência).
  Só comandos executados e verificados.
- `docs/decisoes-tecnicas.md`: ADRs sobre React com Vite sem bibliotecas extras, proxy do
  Vite em vez de CORS, estado local com hook e erros exibidos como vêm da API.
- `docs/arquitetura.md`: acrescentar uma seção curta com a estrutura do frontend; os
  diagramas existentes já mostram o Frontend (React).
- `.gitignore`: já cobre `node_modules/` e `dist/`.

## Notas para o plano (lições dos ciclos 1 e 2)

- Formato do plano para o `meister plan import`: um arquivo por linha em `**Files:**`, sem
  texto entre parênteses nas linhas de arquivo, e um bloco `**Interfaces:**` em toda tarefa.
- `--deps files` não detecta dependências; declará-las manualmente em `plano-ciclo3.json`.
- Worktrees do Meister não têm `node_modules`: cada tarefa roda `npm ci` em `frontend/` antes
  de testar.
- Manter o portão mínimo do `meister.config.yaml`; a verificação real é do arquiteto ao
  fim de cada onda.
- Conferir no resultado dos workers o que o plano pedia literalmente (textos, rótulos e a
  estrutura do README).

## Fora do escopo

Edição de título e descrição, paginação, autenticação, rotas de página, TypeScript, lint,
CORS no backend, build de produção servido pela API, deploy, modo escuro, internacionalização,
testes de ponta a ponta com navegador automatizado.

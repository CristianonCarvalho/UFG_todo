# Arquitetura

Visão da Micro-API de tarefas. As rotas, o service e o repository ainda não foram implementados; os diagramas descrevem o desenho alvo.

## Tarefa e endpoints

| Campo | Tipo | Observação |
|---|---|---|
| `id` | inteiro | gerado pelo banco |
| `title` | texto | 1 a 100 caracteres |
| `description` | texto ou nulo | até 500 caracteres |
| `status` | `pendente` ou `concluida` | inicial: `pendente` |
| `priority` | `baixa`, `media` ou `alta` | automática na criação |
| `priority_source` | `jev`, `fallback` ou `manual` | muda para `manual` ao editar a prioridade |
| `created_at` | data e hora | gerado pelo banco |

| Método e rota | Função |
|---|---|
| `POST /tasks` | criar tarefa |
| `GET /tasks?status=pendente` | listar com filtro opcional por status |
| `GET /tasks/{id}` | detalhar |
| `PATCH /tasks/{id}` | editar campos e prioridade |
| `PATCH /tasks/{id}/complete` | marcar como concluída |
| `DELETE /tasks/{id}` | remover |

## Diagrama 1: Componentes

Mostra as camadas do backend, o classificador com fallback local, os handlers de erro e os sistemas externos.

```mermaid
flowchart LR
    FE["Frontend (React)"]
    DB[("SQLite tasks.db")]
    JEV["Jev (OpenRouter)"]
    subgraph BE["Backend (FastAPI)"]
        CT["Controller"]
        SC["Schemas (Pydantic)"]
        SV["Service"]
        RP["Repository"]
        ER["Handlers de erro"]
        subgraph CL["Classificador de prioridade"]
            CLS["Classificação via Jev"]
            FB["Fallback local"]
        end
    end
    FE -->|"HTTP/JSON"| CT
    CT -->|"valida"| SC
    CT -->|"delega"| SV
    SV -->|"chama"| RP
    RP -->|"SQL via ORM"| DB
    SV -->|"classifica"| CLS
    CLS -->|"HTTPS"| JEV
    CLS -->|"em falha"| FB
    CT -->|"erros"| ER
    SV -->|"erros"| ER
    ER -.->|"mensagem amigável"| FE
    DB -.->|"dados"| RP
    RP -.->|"retorna"| SV
    SV -.->|"retorna"| CT
    CT -.->|"HTTP/JSON"| FE
```

## Diagrama 2: Criar tarefa

Mostra `POST /tasks`, com validação, classificação de prioridade (Jev ou fallback) e falha do banco.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant FE as Frontend
    participant CT as Controller
    participant SV as Service
    participant CL as Classificador
    participant JEV as Jev (OpenRouter)
    participant RP as Repository
    participant DB as SQLite
    U->>FE: Preenche título e descrição
    FE->>CT: POST /tasks com JSON
    CT->>CT: Valida o corpo com TaskCreate
    alt Corpo inválido
        CT-->>FE: 422 com mensagem amigável
        FE-->>U: Mostra o que corrigir
    else Corpo válido
        CT->>SV: Delega a criação
        SV->>SV: Define status pendente
        SV->>CL: classify com título e descrição
        alt Jev respondeu com confiança
            CL->>JEV: HTTPS pergunta de prioridade
            JEV-->>CL: Prioridade e confiança
            CL-->>SV: Resultado com source jev
        else Falha ou resposta inválida
            CL->>CL: Heurística local por palavras-chave
            CL-->>SV: Resultado com source fallback
        end
        SV->>RP: Salva tarefa com prioridade e origem
        RP->>DB: INSERT
        opt Falha do banco
            DB--xRP: Erro de acesso
            RP--xSV: SQLAlchemyError
            SV--xCT: Erro propagado
            CT-->>FE: 503 com mensagem amigável
        end
        DB-->>RP: Linha criada
        RP-->>SV: Tarefa salva
        SV-->>CT: Tarefa
        CT-->>FE: 201 com TaskOut e priority_notice se fallback
        FE-->>U: Mostra a tarefa e o aviso
    end
```

## Diagrama 3: Concluir tarefa

Mostra `PATCH /tasks/{id}/complete`, com o caso de tarefa não encontrada.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant CT as Controller
    participant SV as Service
    participant RP as Repository
    participant DB as SQLite
    FE->>CT: PATCH /tasks/id/complete
    CT->>SV: Delega a conclusão
    SV->>RP: Busca por id
    RP->>DB: SELECT
    DB-->>RP: Resultado
    alt Tarefa não encontrada
        RP-->>SV: Nada encontrado
        SV--xCT: TaskNotFoundError
        CT-->>FE: 404 com mensagem amigável
    else Tarefa encontrada
        SV->>RP: Atualiza status para concluída
        RP->>DB: UPDATE
        DB-->>RP: Confirmação
        RP-->>SV: Tarefa atualizada
        SV-->>CT: Tarefa
        CT-->>FE: 200 com TaskOut
    end
```

## Diagrama 4: Editar a prioridade

Mostra `PATCH /tasks/{id}` com prioridade manual, que nunca é sobrescrita pelo classificador.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant FE as Frontend
    participant CT as Controller
    participant SV as Service
    participant RP as Repository
    participant DB as SQLite
    U->>FE: Escolhe a nova prioridade
    FE->>CT: PATCH /tasks/id com JSON
    CT->>CT: Valida o corpo com TaskUpdate
    alt Prioridade inválida ou nenhum campo enviado
        CT-->>FE: 422 com mensagem amigável
        FE-->>U: Mostra o que corrigir
    else Corpo válido
        CT->>SV: Delega a edição
        SV->>RP: Busca por id
        RP->>DB: SELECT
        DB-->>RP: Resultado
        alt Tarefa não encontrada
            RP-->>SV: Nada encontrado
            SV--xCT: TaskNotFoundError
            CT-->>FE: 404 com mensagem amigável
        else Tarefa encontrada
            Note over SV: Define priority_source como manual. O classificador não é chamado
            SV->>RP: Atualiza prioridade e origem
            RP->>DB: UPDATE
            DB-->>RP: Confirmação
            RP-->>SV: Tarefa atualizada
            SV-->>CT: Tarefa
            CT-->>FE: 200 com TaskOut
            FE-->>U: Mostra a tarefa atualizada
        end
    end
```

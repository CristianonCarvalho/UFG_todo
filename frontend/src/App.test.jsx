import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

const AVISO = "Não foi possível classificar a prioridade automaticamente agora, então usamos uma estimativa. Você pode ajustá-la quando quiser.";

function json(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function erro(status, codigo, mensagem, extra = {}) {
  return json(status, { erro: { codigo, mensagem, id_requisicao: "req-1", ...extra } });
}

function tarefa(id, extra = {}) {
  return {
    id,
    title: `Tarefa ${id}`,
    description: null,
    status: "pendente",
    priority: "media",
    priority_source: "jev",
    priority_notice: null,
    created_at: "2026-10-04T10:00:00",
    ...extra,
  };
}

function fakeApi(inicial = [], { origem = "jev" } = {}) {
  let tasks = [...inicial];
  let proximoId = inicial.length + 1;
  return vi.fn(async (url, options = {}) => {
    const method = options.method ?? "GET";
    const [path, query] = url.split("?");
    if (path === "/tasks" && method === "GET") {
      const status = new URLSearchParams(query).get("status");
      return json(200, tasks.filter((t) => !status || t.status === status));
    }
    if (path === "/tasks" && method === "POST") {
      const dados = JSON.parse(options.body);
      if (!dados.title || !dados.title.trim()) {
        return erro(422, "DADOS_INVALIDOS", "Confira os campos destacados e tente novamente.", {
          detalhes: [{ campo: "title", mensagem: "O título não pode ficar em branco." }],
        });
      }
      const nova = tarefa(proximoId++, {
        title: dados.title,
        description: dados.description ?? null,
        priority: "alta",
        priority_source: origem,
        priority_notice: origem === "fallback" ? AVISO : null,
      });
      tasks.push(nova);
      return json(201, nova);
    }
    const correspondencia = path.match(/^\/tasks\/(\d+)(\/complete)?$/);
    if (correspondencia) {
      const id = Number(correspondencia[1]);
      const atual = tasks.find((t) => t.id === id);
      if (!atual) {
        return erro(404, "TAREFA_NAO_ENCONTRADA", "Não encontramos essa tarefa. Ela pode ter sido removida.");
      }
      if (method === "DELETE") {
        tasks = tasks.filter((t) => t.id !== id);
        return new Response(null, { status: 204 });
      }
      if (method === "PATCH" && correspondencia[2]) {
        atual.status = "concluida";
        return json(200, atual);
      }
      if (method === "PATCH") {
        const mudancas = JSON.parse(options.body);
        Object.assign(atual, mudancas, { priority_source: "manual", priority_notice: null });
        return json(200, atual);
      }
    }
    return erro(404, "NAO_ENCONTRADO", "Não encontramos o que você procurou.");
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", fakeApi());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("mostra as tarefas existentes na carga inicial", async () => {
    vi.stubGlobal("fetch", fakeApi([tarefa(1), tarefa(2)]));
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Tarefa 1" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tarefa 2" })).toBeInTheDocument();
  });

  it("mostra a mensagem de lista vazia", async () => {
    render(<App />);
    expect(await screen.findByText("Nenhuma tarefa por aqui ainda.")).toBeInTheDocument();
  });

  it("cria uma tarefa, mostra na lista e limpa o formulário", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Nenhuma tarefa por aqui ainda.");
    await user.type(screen.getByLabelText("Título"), "Escrever relatório");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByRole("heading", { name: "Escrever relatório" })).toBeInTheDocument();
    expect(screen.getByText("Sugerida pela IA")).toBeInTheDocument();
    expect(screen.getByLabelText("Título")).toHaveValue("");
  });

  it("mostra o aviso amigável quando a prioridade veio do fallback", async () => {
    vi.stubGlobal("fetch", fakeApi([], { origem: "fallback" }));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Nenhuma tarefa por aqui ainda.");
    await user.type(screen.getByLabelText("Título"), "Corrigir bug");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByText(AVISO)).toBeInTheDocument();
    expect(screen.getByText("Estimativa automática")).toBeInTheDocument();
  });

  it("título em branco mostra o erro abaixo do campo, sem banner e sem apagar o texto", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Nenhuma tarefa por aqui ainda.");
    await user.type(screen.getByLabelText("Título"), "   ");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByText("O título não pode ficar em branco.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Título")).toHaveValue("   ");
  });

  it("filtra por pendentes e concluídas", async () => {
    vi.stubGlobal("fetch", fakeApi([tarefa(1), tarefa(2, { status: "concluida" })]));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Tarefa 1" });
    await user.click(screen.getByRole("button", { name: "Concluídas" }));
    expect(await screen.findByRole("heading", { name: "Tarefa 2" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tarefa 1" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pendentes" }));
    expect(await screen.findByRole("heading", { name: "Tarefa 1" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tarefa 2" })).not.toBeInTheDocument();
  });

  it("conclui uma tarefa", async () => {
    vi.stubGlobal("fetch", fakeApi([tarefa(1)]));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Tarefa 1" });
    await user.click(screen.getByRole("button", { name: "Concluir" }));
    expect(await screen.findByText("Concluída")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Concluir" })).not.toBeInTheDocument();
  });

  it("edita a prioridade e passa a mostrar 'Definida por você'", async () => {
    vi.stubGlobal("fetch", fakeApi([tarefa(1)]));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Tarefa 1" });
    await user.selectOptions(screen.getByRole("combobox", { name: /alterar prioridade/i }), "alta");
    expect(await screen.findByText("Definida por você")).toBeInTheDocument();
    expect(screen.getByText("Prioridade Alta")).toBeInTheDocument();
  });

  it("remove uma tarefa depois da confirmação", async () => {
    vi.stubGlobal("fetch", fakeApi([tarefa(1), tarefa(2)]));
    const user = userEvent.setup();
    render(<App />);
    const item = (await screen.findByRole("heading", { name: "Tarefa 1" })).closest("li");
    await user.click(within(item).getByRole("button", { name: "Remover" }));
    await user.click(within(item).getByRole("button", { name: "Confirmar remoção" }));
    expect(await screen.findByRole("heading", { name: "Tarefa 2" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tarefa 1" })).not.toBeInTheDocument();
  });

  it("mostra o erro da API no banner, com o código da requisição", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        erro(503, "BANCO_INDISPONIVEL", "Não conseguimos acessar os dados agora. Tente novamente em instantes."),
      ),
    );
    render(<App />);
    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Não conseguimos acessar os dados agora.");
    expect(banner).toHaveTextContent("Código da requisição: req-1");
  });

  it("API fora do ar mostra a mensagem de conexão em vez de tela branca", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível conectar ao servidor. Verifique se a API está no ar e tente novamente.",
    );
    expect(screen.getByRole("heading", { name: "Tarefas" })).toBeInTheDocument();
  });

  it("ação sobre tarefa já removida mostra erro amigável e atualiza a lista", async () => {
    const api = fakeApi([tarefa(1)]);
    vi.stubGlobal("fetch", api);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Tarefa 1" });
    await fetch("/tasks/1", { method: "DELETE" });
    await user.click(screen.getByRole("button", { name: "Concluir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não encontramos essa tarefa. Ela pode ter sido removida.",
    );
    expect(screen.queryByRole("heading", { name: "Tarefa 1" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dispensar" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

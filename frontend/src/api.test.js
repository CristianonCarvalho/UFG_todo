import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  completeTask,
  createTask,
  deleteTask,
  listTasks,
  updateTask,
} from "./api.js";

const fetchMock = vi.fn();

function jsonResponse(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function erroApi(status, erro) {
  return jsonResponse(status, { erro });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listTasks", () => {
  it("não envia status para o filtro 'todas'", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []));
    await listTasks("todas");
    expect(fetchMock.mock.calls[0][0]).toBe("/tasks");
  });

  it("envia o status para pendente e concluida", async () => {
    fetchMock.mockImplementation(() => jsonResponse(200, []));
    await listTasks("pendente");
    await listTasks("concluida");
    expect(fetchMock.mock.calls[0][0]).toBe("/tasks?status=pendente");
    expect(fetchMock.mock.calls[1][0]).toBe("/tasks?status=concluida");
  });

  it("devolve o corpo da resposta", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ id: 1 }]));
    expect(await listTasks("todas")).toEqual([{ id: 1 }]);
  });
});

describe("createTask", () => {
  it("envia título e descrição", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: 1 }));
    await createTask({ title: "Escrever", description: "rascunho" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/tasks");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ title: "Escrever", description: "rascunho" });
  });

  it("omite a descrição vazia", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: 1 }));
    await createTask({ title: "Escrever", description: "   " });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ title: "Escrever" });
  });
});

describe("updateTask, completeTask e deleteTask", () => {
  it("updateTask envia PATCH com as alterações", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 3 }));
    await updateTask(3, { priority: "alta" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/tasks/3");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ priority: "alta" });
  });

  it("completeTask chama PATCH em /complete", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 3 }));
    await completeTask(3);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/tasks/3/complete");
    expect(options.method).toBe("PATCH");
  });

  it("deleteTask trata o 204 sem corpo e devolve null", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    expect(await deleteTask(3)).toBeNull();
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });
});

describe("erros", () => {
  it("422 vira ApiError com detalhes e id da requisição", async () => {
    fetchMock.mockResolvedValue(
      erroApi(422, {
        codigo: "DADOS_INVALIDOS",
        mensagem: "Confira os campos destacados e tente novamente.",
        detalhes: [{ campo: "title", mensagem: "O título é obrigatório." }],
        id_requisicao: "abc-123",
      }),
    );
    const erro = await createTask({ title: "", description: "" }).catch((e) => e);
    expect(erro).toBeInstanceOf(ApiError);
    expect(erro.message).toBe("Confira os campos destacados e tente novamente.");
    expect(erro.codigo).toBe("DADOS_INVALIDOS");
    expect(erro.detalhes).toEqual([{ campo: "title", mensagem: "O título é obrigatório." }]);
    expect(erro.idRequisicao).toBe("abc-123");
    expect(erro.status).toBe(422);
  });

  it.each([
    [404, "TAREFA_NAO_ENCONTRADA", "Não encontramos essa tarefa. Ela pode ter sido removida."],
    [503, "BANCO_INDISPONIVEL", "Não conseguimos acessar os dados agora. Tente novamente em instantes."],
  ])("%i usa a mensagem amigável da API", async (status, codigo, mensagem) => {
    fetchMock.mockResolvedValue(erroApi(status, { codigo, mensagem, id_requisicao: "x" }));
    const erro = await completeTask(1).catch((e) => e);
    expect(erro.message).toBe(mensagem);
    expect(erro.codigo).toBe(codigo);
    expect(erro.detalhes).toEqual([]);
  });

  it("resposta de erro fora do formato gera mensagem genérica amigável", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html>Bad Gateway</html>", {
        status: 502,
        headers: { "Content-Type": "text/html" },
      }),
    );
    const erro = await listTasks("todas").catch((e) => e);
    expect(erro).toBeInstanceOf(ApiError);
    expect(erro.message).toBe("Algo deu errado. Tente novamente em instantes.");
    expect(erro.message).not.toContain("html");
  });

  it("resposta de sucesso sem JSON válido gera mensagem genérica", async () => {
    fetchMock.mockResolvedValue(new Response("não é json", { status: 200 }));
    const erro = await listTasks("todas").catch((e) => e);
    expect(erro).toBeInstanceOf(ApiError);
    expect(erro.message).toBe("Algo deu errado. Tente novamente em instantes.");
  });

  it("falha de rede gera a mensagem de conexão", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const erro = await listTasks("todas").catch((e) => e);
    expect(erro).toBeInstanceOf(ApiError);
    expect(erro.codigo).toBe("SEM_CONEXAO");
    expect(erro.message).toBe(
      "Não foi possível conectar ao servidor. Verifique se a API está no ar e tente novamente.",
    );
  });
});

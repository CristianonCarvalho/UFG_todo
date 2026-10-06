import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    completeTask: vi.fn(),
    deleteTask: vi.fn(),
  };
});

import * as api from "./api.js";
import { ApiError } from "./api.js";
import { useTasks } from "./useTasks.js";

const tarefa = (id) => ({ id, title: `t${id}` });

beforeEach(() => {
  vi.resetAllMocks();
  api.listTasks.mockResolvedValue([]);
});

describe("useTasks", () => {
  it("carrega a lista ao montar", async () => {
    api.listTasks.mockResolvedValue([tarefa(1)]);
    const { result } = renderHook(() => useTasks());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(api.listTasks).toHaveBeenCalledWith("todas");
    expect(result.current.tasks).toEqual([tarefa(1)]);
  });

  it("recarrega ao mudar o filtro", async () => {
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setFilter("pendente"));
    await waitFor(() => expect(api.listTasks).toHaveBeenCalledWith("pendente"));
  });

  it("ignora a resposta antiga quando o filtro muda rápido", async () => {
    let resolverPrimeira;
    api.listTasks.mockImplementationOnce(
      () => new Promise((resolve) => (resolverPrimeira = resolve)),
    );
    api.listTasks.mockResolvedValueOnce([tarefa(2)]);
    const { result } = renderHook(() => useTasks());
    act(() => result.current.setFilter("pendente"));
    await waitFor(() => expect(result.current.tasks).toEqual([tarefa(2)]));
    await act(async () => resolverPrimeira([tarefa(1)]));
    expect(result.current.tasks).toEqual([tarefa(2)]);
  });

  it("create com sucesso grava, recarrega a lista e devolve ok", async () => {
    api.createTask.mockResolvedValue(tarefa(5));
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let resultado;
    await act(async () => {
      resultado = await result.current.create({ title: "x", description: "" });
    });
    expect(api.createTask).toHaveBeenCalledWith({ title: "x", description: "" });
    expect(resultado).toEqual({ ok: true, detalhes: [] });
    expect(api.listTasks).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeNull();
  });

  it("create com erro de validação devolve os detalhes ao formulário, sem banner", async () => {
    const detalhes = [{ campo: "title", mensagem: "O título é obrigatório." }];
    api.createTask.mockRejectedValue(
      new ApiError({ codigo: "DADOS_INVALIDOS", mensagem: "Confira os campos.", detalhes, status: 422 }),
    );
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let resultado;
    await act(async () => {
      resultado = await result.current.create({ title: "", description: "" });
    });
    expect(resultado).toEqual({ ok: false, detalhes });
    expect(result.current.error).toBeNull();
  });

  it("create com erro sem detalhes (ex.: banco fora) mostra o banner", async () => {
    api.createTask.mockRejectedValue(
      new ApiError({ codigo: "BANCO_INDISPONIVEL", mensagem: "Não conseguimos acessar os dados agora.", status: 503 }),
    );
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let resultado;
    await act(async () => {
      resultado = await result.current.create({ title: "x", description: "" });
    });
    expect(resultado).toEqual({ ok: false, detalhes: [] });
    expect(result.current.error.message).toBe("Não conseguimos acessar os dados agora.");
  });

  it("changePriority chama a API com a nova prioridade e recarrega", async () => {
    api.updateTask.mockResolvedValue(tarefa(3));
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.changePriority(3, "alta");
    });
    expect(api.updateTask).toHaveBeenCalledWith(3, { priority: "alta" });
    expect(api.listTasks).toHaveBeenCalledTimes(2);
  });

  it("complete e remove chamam a API correspondente", async () => {
    api.completeTask.mockResolvedValue(tarefa(3));
    api.deleteTask.mockResolvedValue(null);
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.complete(3);
      await result.current.remove(4);
    });
    expect(api.completeTask).toHaveBeenCalledWith(3);
    expect(api.deleteTask).toHaveBeenCalledWith(4);
  });

  it("ação sobre tarefa já removida mostra o erro amigável e recarrega a lista", async () => {
    api.completeTask.mockRejectedValue(
      new ApiError({
        codigo: "TAREFA_NAO_ENCONTRADA",
        mensagem: "Não encontramos essa tarefa. Ela pode ter sido removida.",
        status: 404,
      }),
    );
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.complete(5);
    });
    expect(result.current.error.message).toBe("Não encontramos essa tarefa. Ela pode ter sido removida.");
    expect(api.listTasks).toHaveBeenCalledTimes(2);
    expect(result.current.busyIds).toEqual([]);
  });

  it("falha ao carregar a lista vira erro e clearError o limpa", async () => {
    api.listTasks.mockRejectedValue(
      new ApiError({ codigo: "SEM_CONEXAO", mensagem: "Não foi possível conectar ao servidor." }),
    );
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.loading).toBe(false);
    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
  });

  it("marca a tarefa como ocupada durante a ação", async () => {
    let resolver;
    api.completeTask.mockImplementation(() => new Promise((resolve) => (resolver = resolve)));
    const { result } = renderHook(() => useTasks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let promessa;
    act(() => {
      promessa = result.current.complete(7);
    });
    await waitFor(() => expect(result.current.busyIds).toEqual([7]));
    await act(async () => {
      resolver(tarefa(7));
      await promessa;
    });
    expect(result.current.busyIds).toEqual([]);
  });
});

const NETWORK_MESSAGE =
  "Não foi possível conectar ao servidor. Verifique se a API está no ar e tente novamente.";
const GENERIC_MESSAGE = "Algo deu errado. Tente novamente em instantes.";

export class ApiError extends Error {
  constructor({ codigo = "ERRO", mensagem, detalhes = [], idRequisicao = null, status = 0 }) {
    super(mensagem);
    this.name = "ApiError";
    this.codigo = codigo;
    this.detalhes = detalhes;
    this.idRequisicao = idRequisicao;
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new ApiError({ codigo: "SEM_CONEXAO", mensagem: NETWORK_MESSAGE });
  }

  if (response.status === 204) {
    return null;
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (response.ok) {
    if (body === null) {
      throw new ApiError({ mensagem: GENERIC_MESSAGE, status: response.status });
    }
    return body;
  }

  const erro = body && body.erro;
  if (erro && typeof erro.mensagem === "string") {
    throw new ApiError({
      codigo: erro.codigo,
      mensagem: erro.mensagem,
      detalhes: Array.isArray(erro.detalhes) ? erro.detalhes : [],
      idRequisicao: erro.id_requisicao ?? null,
      status: response.status,
    });
  }
  throw new ApiError({ mensagem: GENERIC_MESSAGE, status: response.status });
}

export function listTasks(status) {
  const query = status === "pendente" || status === "concluida" ? `?status=${status}` : "";
  return request(`/tasks${query}`);
}

export function createTask({ title, description }) {
  const body = { title };
  if (description && description.trim()) {
    body.description = description;
  }
  return request("/tasks", { method: "POST", body: JSON.stringify(body) });
}

export function updateTask(id, changes) {
  return request(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(changes) });
}

export function completeTask(id) {
  return request(`/tasks/${id}/complete`, { method: "PATCH" });
}

export function deleteTask(id) {
  return request(`/tasks/${id}`, { method: "DELETE" });
}

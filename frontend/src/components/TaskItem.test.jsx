import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TaskItem from "./TaskItem.jsx";

const base = {
  id: 1,
  title: "Escrever relatório",
  description: "rascunho",
  status: "pendente",
  priority: "media",
  priority_source: "jev",
  priority_notice: null,
  created_at: "2026-10-04T10:00:00",
};

function renderItem(task = base, props = {}) {
  const handlers = {
    onComplete: vi.fn(),
    onRemove: vi.fn(),
    onChangePriority: vi.fn(),
  };
  render(<TaskItem task={task} busy={false} {...handlers} {...props} />);
  return handlers;
}

describe("TaskItem", () => {
  it("mostra título, descrição, status e prioridade", () => {
    renderItem();
    expect(screen.getByRole("heading", { name: "Escrever relatório" })).toBeInTheDocument();
    expect(screen.getByText("rascunho")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Prioridade Média")).toBeInTheDocument();
  });

  it.each([
    ["jev", "Sugerida pela IA"],
    ["fallback", "Estimativa automática"],
    ["manual", "Definida por você"],
  ])("mostra o rótulo da origem %s", (origem, rotulo) => {
    renderItem({ ...base, priority_source: origem });
    expect(screen.getByText(rotulo)).toBeInTheDocument();
  });

  it("mostra o aviso da prioridade só quando ele existe", () => {
    const aviso = "Não foi possível classificar a prioridade automaticamente agora.";
    const { unmount } = render(
      <TaskItem
        task={{ ...base, priority_source: "fallback", priority_notice: aviso }}
        busy={false}
        onComplete={vi.fn()}
        onRemove={vi.fn()}
        onChangePriority={vi.fn()}
      />,
    );
    expect(screen.getByText(aviso)).toBeInTheDocument();
    unmount();
    renderItem();
    expect(screen.queryByText(aviso)).not.toBeInTheDocument();
  });

  it("chama onComplete e esconde 'Concluir' em tarefa concluída", async () => {
    const user = userEvent.setup();
    const { onComplete } = renderItem();
    await user.click(screen.getByRole("button", { name: "Concluir" }));
    expect(onComplete).toHaveBeenCalledWith(1);
  });

  it("não oferece 'Concluir' para tarefa já concluída", () => {
    renderItem({ ...base, status: "concluida" });
    expect(screen.queryByRole("button", { name: "Concluir" })).not.toBeInTheDocument();
    expect(screen.getByText("Concluída")).toBeInTheDocument();
  });

  it("remover exige confirmação", async () => {
    const user = userEvent.setup();
    const { onRemove } = renderItem();
    await user.click(screen.getByRole("button", { name: "Remover" }));
    expect(onRemove).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirmar remoção" }));
    expect(onRemove).toHaveBeenCalledWith(1);
  });

  it("permite cancelar a remoção", async () => {
    const user = userEvent.setup();
    const { onRemove } = renderItem();
    await user.click(screen.getByRole("button", { name: "Remover" }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onRemove).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Remover" })).toBeInTheDocument();
  });

  it("trocar a prioridade chama onChangePriority com o valor escolhido", async () => {
    const user = userEvent.setup();
    const { onChangePriority } = renderItem();
    await user.selectOptions(
      screen.getByRole("combobox", { name: /alterar prioridade/i }),
      "alta",
    );
    expect(onChangePriority).toHaveBeenCalledWith(1, "alta");
  });

  it("desabilita as ações enquanto a tarefa está ocupada", () => {
    renderItem(base, { busy: true });
    expect(screen.getByRole("button", { name: "Concluir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remover" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: /alterar prioridade/i })).toBeDisabled();
  });
});

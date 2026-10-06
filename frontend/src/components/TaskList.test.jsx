import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TaskList from "./TaskList.jsx";

const handlers = {
  onComplete: vi.fn(),
  onRemove: vi.fn(),
  onChangePriority: vi.fn(),
};

function tarefa(id, title) {
  return {
    id,
    title,
    description: null,
    status: "pendente",
    priority: "media",
    priority_source: "jev",
    priority_notice: null,
    created_at: "2026-10-04T10:00:00",
  };
}

describe("TaskList", () => {
  it("mostra a mensagem de lista vazia", () => {
    render(<TaskList tasks={[]} loading={false} busyIds={[]} {...handlers} />);
    expect(screen.getByText("Nenhuma tarefa por aqui ainda.")).toBeInTheDocument();
  });

  it("mostra o carregamento quando ainda não há tarefas", () => {
    render(<TaskList tasks={[]} loading={true} busyIds={[]} {...handlers} />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando tarefas");
    expect(screen.queryByText("Nenhuma tarefa por aqui ainda.")).not.toBeInTheDocument();
  });

  it("renderiza uma tarefa por item e marca as ocupadas", () => {
    render(
      <TaskList
        tasks={[tarefa(1, "Primeira"), tarefa(2, "Segunda")]}
        loading={false}
        busyIds={[2]}
        {...handlers}
      />,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Primeira" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Segunda" })).toBeInTheDocument();
    const concluir = screen.getAllByRole("button", { name: "Concluir" });
    expect(concluir[0]).toBeEnabled();
    expect(concluir[1]).toBeDisabled();
  });
});

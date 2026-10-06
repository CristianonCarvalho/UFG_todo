import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TaskForm from "./TaskForm.jsx";

describe("TaskForm", () => {
  it("envia título e descrição e limpa os campos após o sucesso", async () => {
    const onSubmit = vi.fn().mockResolvedValue({ ok: true, detalhes: [] });
    const user = userEvent.setup();
    render(<TaskForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Título"), "Comprar café");
    await user.type(screen.getByLabelText("Descrição"), "o forte");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));

    expect(onSubmit).toHaveBeenCalledWith({ title: "Comprar café", description: "o forte" });
    expect(screen.getByLabelText("Título")).toHaveValue("");
    expect(screen.getByLabelText("Descrição")).toHaveValue("");
  });

  it("mostra o erro de cada campo e preserva o que foi digitado", async () => {
    const onSubmit = vi.fn().mockResolvedValue({
      ok: false,
      detalhes: [
        { campo: "title", mensagem: "O título não pode ficar em branco." },
        { campo: "description", mensagem: "A descrição tem caracteres demais." },
      ],
    });
    const user = userEvent.setup();
    render(<TaskForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Título"), "   ");
    await user.type(screen.getByLabelText("Descrição"), "texto");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));

    expect(await screen.findByText("O título não pode ficar em branco.")).toBeInTheDocument();
    expect(screen.getByText("A descrição tem caracteres demais.")).toBeInTheDocument();
    expect(screen.getByLabelText("Título")).toHaveValue("   ");
    expect(screen.getByLabelText("Descrição")).toHaveValue("texto");
  });

  it("envia mesmo com o título vazio, para o servidor responder com a mensagem amigável", async () => {
    const onSubmit = vi.fn().mockResolvedValue({
      ok: false,
      detalhes: [{ campo: "title", mensagem: "O título é obrigatório." }],
    });
    const user = userEvent.setup();
    render(<TaskForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Adicionar" }));

    expect(onSubmit).toHaveBeenCalledWith({ title: "", description: "" });
    expect(await screen.findByText("O título é obrigatório.")).toBeInTheDocument();
  });

  it("limita o tamanho dos campos", () => {
    render(<TaskForm onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("Título")).toHaveAttribute("maxlength", "100");
    expect(screen.getByLabelText("Descrição")).toHaveAttribute("maxlength", "500");
  });
});

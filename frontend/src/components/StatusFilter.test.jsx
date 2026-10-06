import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import StatusFilter from "./StatusFilter.jsx";

describe("StatusFilter", () => {
  it("marca o botão do filtro ativo", () => {
    render(<StatusFilter value="pendente" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Pendentes" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Todas" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Concluídas" })).toHaveAttribute("aria-pressed", "false");
  });

  it("chama onChange com o valor do filtro escolhido", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<StatusFilter value="todas" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Concluídas" }));
    expect(onChange).toHaveBeenCalledWith("concluida");
  });
});

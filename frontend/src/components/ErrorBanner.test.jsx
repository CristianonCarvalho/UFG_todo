import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ErrorBanner from "./ErrorBanner.jsx";

describe("ErrorBanner", () => {
  it("não renderiza nada sem erro", () => {
    const { container } = render(<ErrorBanner error={null} onDismiss={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra a mensagem e o código da requisição", () => {
    render(
      <ErrorBanner
        error={{ message: "Não conseguimos acessar os dados agora.", idRequisicao: "abc-123" }}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Não conseguimos acessar os dados agora.");
    expect(screen.getByText("Código da requisição: abc-123")).toBeInTheDocument();
  });

  it("não mostra o código quando não existe", () => {
    render(<ErrorBanner error={{ message: "Algo deu errado." }} onDismiss={vi.fn()} />);
    expect(screen.queryByText(/Código da requisição/)).not.toBeInTheDocument();
  });

  it("dispensa o erro pelo botão", async () => {
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(<ErrorBanner error={{ message: "Falhou." }} onDismiss={onDismiss} />);
    await user.click(screen.getByRole("button", { name: "Dispensar" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

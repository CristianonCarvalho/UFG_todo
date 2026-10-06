import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

test("o ambiente de testes renderiza e usa os matchers do jest-dom", () => {
  render(<p>ok</p>);
  expect(screen.getByText("ok")).toBeInTheDocument();
});

import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import PaymentsDocsPage from "@/app/(staff)/project-manager/payments/docs/page";

describe("PaymentsDocsPage", () => {
  it("renders the English documentation by default", () => {
    render(<PaymentsDocsPage />);
    expect(
      screen.getByRole("heading", {
        name: /what we receive and how we count it/i,
      }),
    ).toBeInTheDocument();
    // EN-only section heading.
    expect(screen.getByText("1. Where the data comes from")).toBeInTheDocument();
    // The Collected formula is shown verbatim.
    expect(
      screen.getByText(/Collected = Σ payment_recorded/),
    ).toBeInTheDocument();
    // The maintenance (doc-sync) note is surfaced.
    expect(
      screen.getByText(/Keep this document in sync with the code/i),
    ).toBeInTheDocument();
  });

  it("switches to Russian and back via the language toggle", async () => {
    const user = userEvent.setup();
    render(<PaymentsDocsPage />);

    // Russian content is absent before toggling.
    expect(screen.queryByText("1. Откуда берутся данные")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /switch to russian/i }));

    // RU-only section heading appears; EN one is gone.
    expect(screen.getByText("1. Откуда берутся данные")).toBeInTheDocument();
    expect(
      screen.queryByText("1. Where the data comes from"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Держите этот документ синхронным с кодом/i),
    ).toBeInTheDocument();

    // Toggle back to English.
    await user.click(screen.getByRole("button", { name: /switch to english/i }));
    expect(screen.getByText("1. Where the data comes from")).toBeInTheDocument();
  });
});

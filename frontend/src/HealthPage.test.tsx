import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HealthPage from "./pages/HealthPage";
import { getHealth } from "./api/health";

vi.mock("./api/health", () => ({
  getHealth: vi.fn(),
}));

describe("HealthPage", () => {
  it("shows a loading state initially", () => {
    vi.mocked(getHealth).mockReturnValue(new Promise(() => {}));

    render(<HealthPage />);

    expect(screen.getByText(/checking backend health/i)).toBeInTheDocument();
  });

  it("shows the healthy state", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "healthy",
      app: "Stanford-AI OS",
      environment: "development",
    });

    render(<HealthPage />);

    expect(await screen.findByText(/backend is healthy/i)).toBeInTheDocument();
    expect(screen.getByText("Stanford-AI OS")).toBeInTheDocument();
  });

  it("shows an unavailable state", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("Network down"));

    render(<HealthPage />);

    expect(
      await screen.findByText(/backend unavailable: network down/i),
    ).toBeInTheDocument();
  });
});

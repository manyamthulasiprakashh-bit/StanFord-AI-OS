import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useState } from "react";
import { flushSync } from "react-dom";

function Repro() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<string | null>(null);

  async function load() {
    const result = await Promise.resolve("loaded");
    flushSync(() => {
      setData(result);
    });
  }

  return (
    <div>
      <button type="button" onClick={() => { setOpen(true); void load(); }}>
        View history
      </button>
      {open && data ? <p>Execution history {data}</p> : null}
    </div>
  );
}

describe("repro", () => {
  it("finds async text", async () => {
    render(<Repro />);
    fireEvent.click(screen.getByRole("button", { name: /view history/i }));
    expect(await screen.findByText(/execution history/i)).toBeInTheDocument();
  });
});

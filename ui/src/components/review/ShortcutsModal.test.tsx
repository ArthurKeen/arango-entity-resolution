import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShortcutsModal } from "./ShortcutsModal";

describe("ShortcutsModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(<ShortcutsModal open={false} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the shortcut list when open", () => {
    render(<ShortcutsModal open onClose={() => {}} />);
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
    expect(screen.getByText(/Mark focused pair as Match/)).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    render(<ShortcutsModal open onClose={onClose} />);
    await userEvent.click(screen.getByText("Keyboard shortcuts"));
    expect(onClose).not.toHaveBeenCalled(); // clicks inside the dialog don't close
  });
});

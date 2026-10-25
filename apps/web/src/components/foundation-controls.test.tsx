import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { FoundationControls } from "./foundation-controls";

const setTheme = vi.fn();

vi.mock("next/navigation", () => ({ usePathname: () => "/en" }));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme }) }));

describe("FoundationControls", () => {
  beforeEach(() => setTheme.mockClear());

  it("links to the alternate locale", () => {
    render(<FoundationControls dictionary={en.header} locale="en" />);
    expect(screen.getByRole("link", { name: /Language: FA/ })).toHaveAttribute("href", "/fa");
  });

  it("switches from dark to light", () => {
    render(<FoundationControls dictionary={en.header} locale="en" />);
    fireEvent.click(screen.getByRole("button", { name: /Theme: Light/ }));
    expect(setTheme).toHaveBeenCalledWith("light");
  });
});

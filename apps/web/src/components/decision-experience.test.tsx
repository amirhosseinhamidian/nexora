import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { DecisionExperience } from "./decision-experience";

vi.mock("@/components/decision-feed", () => ({
  DecisionFeed: ({ onDecisionChange }: { onDecisionChange?: (decisionId: string) => void }) => (
    <button onClick={() => onDecisionChange?.("decision-evaluation-1")} type="button">
      Select Decision evidence
    </button>
  ),
}));
vi.mock("@/components/outcome-journal-panel", () => ({
  OutcomeJournalPanel: ({ decisionId }: { decisionId?: string }) => (
    <output data-testid="journal-context">{decisionId ?? "none"}</output>
  ),
}));
vi.mock("@/components/alert-inbox", () => ({ AlertInbox: () => <section>Alerts</section> }));
vi.mock("@/components/watchlist-panel", () => ({
  WatchlistPanel: () => <section>Watchlists</section>,
}));

describe("DecisionExperience", () => {
  it("connects selected Decision evidence to the outcome journal", () => {
    render(<DecisionExperience dictionary={en} locale="en" />);

    expect(screen.getByTestId("journal-context")).toHaveTextContent("none");
    const decisionStatus = screen.getByRole("status", { name: "Active Decision context" });
    expect(decisionStatus).toHaveTextContent(
      "Select Decision evidence to connect its outcome journal.",
    );

    fireEvent.click(screen.getByRole("button", { name: "Select Decision evidence" }));

    expect(screen.getByTestId("journal-context")).toHaveTextContent("decision-evaluation-1");
    expect(decisionStatus).toHaveTextContent("decision-evaluation-1");
  });
});

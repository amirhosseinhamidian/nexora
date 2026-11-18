import { fireEvent, render, screen } from "@testing-library/react";
import {
  Alert,
  Button,
  ChartContainer,
  Checkbox,
  ConfirmationDialog,
  EmptyState,
  FormField,
  Input,
  Progress,
  Switch,
  Table,
  ToastRegion,
} from "@nexora/ui/primitives";
import { describe, expect, it, vi } from "vitest";

describe("shared UI primitives", () => {
  it("exposes labelled form controls and contextual errors", () => {
    render(
      <FormField error="Enter a valid name." id="portfolio-name" label="Portfolio name">
        <Input aria-describedby="portfolio-name-error" aria-invalid="true" id="portfolio-name" />
      </FormField>,
    );

    expect(screen.getByRole("textbox", { name: "Portfolio name" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid name.");
  });

  it("keeps choice and switch labels accessible", () => {
    render(
      <>
        <Checkbox>Include archived portfolios</Checkbox>
        <Switch>Compact navigation</Switch>
      </>,
    );

    expect(screen.getByRole("checkbox", { name: "Include archived portfolios" })).toBeVisible();
    expect(screen.getByRole("switch", { name: "Compact navigation" })).toBeVisible();
  });

  it("announces transient and persistent feedback with appropriate roles", () => {
    render(
      <>
        <Alert title="Unable to save" tone="danger">
          Check the highlighted fields and try again.
        </Alert>
        <ToastRegion
          label="Notifications"
          messages={[{ id: "saved", title: "Portfolio saved", tone: "success" }]}
        />
      </>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Check the highlighted fields");
    expect(screen.getByRole("region", { name: "Notifications" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("locks scrolling, closes on Escape and restores focus for overlays", () => {
    const onCancel = vi.fn();
    const dialog = (open: boolean) => (
      <>
        <button type="button">Open archive confirmation</button>
        <ConfirmationDialog
          cancelLabel="Cancel"
          confirmLabel="Archive portfolio"
          description="The portfolio remains available in archived records."
          destructive
          onCancel={onCancel}
          onConfirm={vi.fn()}
          open={open}
          title="Archive this portfolio?"
        />
      </>
    );
    const { rerender } = render(dialog(false));
    const trigger = screen.getByRole("button", { name: "Open archive confirmation" });
    trigger.focus();
    rerender(dialog(true));

    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByRole("dialog", { name: "Archive this portfolio?" })).toBeVisible();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledOnce();
    rerender(dialog(false));
    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });

  it("provides bounded progress and explicit loading button state", () => {
    render(
      <>
        <Progress label="Import progress" value={120} />
        <Button loading>Save</Button>
      </>,
    );

    expect(screen.getByRole("progressbar", { name: "Import progress" })).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("aria-busy", "true");
  });

  it("keeps chart data available as an accessible table", () => {
    render(
      <ChartContainer
        description="Allocation across asset classes"
        table={
          <Table>
            <caption>Allocation values</caption>
            <tbody>
              <tr>
                <th scope="row">Cash</th>
                <td>25%</td>
              </tr>
            </tbody>
          </Table>
        }
        title="Allocation"
      >
        <svg />
      </ChartContainer>,
    );

    expect(screen.getByRole("figure")).toHaveAccessibleDescription(
      "Allocation across asset classes",
    );
    expect(screen.getByRole("table", { name: "Allocation values" })).toHaveTextContent("25%");
  });

  it("renders reusable empty states with actions", () => {
    render(
      <EmptyState action={<Button>Create portfolio</Button>} title="No portfolios yet">
        Create your first portfolio to start tracking holdings.
      </EmptyState>,
    );

    expect(screen.getByRole("heading", { name: "No portfolios yet" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Create portfolio" })).toBeVisible();
  });
});

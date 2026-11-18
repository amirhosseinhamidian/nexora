import { Button } from "./button";
import { Modal, type OverlayProps } from "./dialog";

export function ConfirmationDialog({
  cancelLabel,
  confirmLabel,
  destructive = false,
  onCancel,
  onConfirm,
  ...props
}: Omit<OverlayProps, "children" | "closeLabel" | "footer" | "onClose" | "variant"> & {
  cancelLabel: string;
  confirmLabel: string;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal
      closeLabel={cancelLabel}
      footer={
        <>
          <Button onClick={onCancel} variant="secondary">
            {cancelLabel}
          </Button>
          <Button onClick={onConfirm} variant={destructive ? "danger" : "primary"}>
            {confirmLabel}
          </Button>
        </>
      }
      onClose={onCancel}
      {...props}
    >
      {null}
    </Modal>
  );
}

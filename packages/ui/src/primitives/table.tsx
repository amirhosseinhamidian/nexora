import {
  Children,
  cloneElement,
  isValidElement,
  type ComponentPropsWithoutRef,
  useId,
} from "react";
import { classes } from "./shared";

export function Table({ children, className, ...props }: ComponentPropsWithoutRef<"table">) {
  const id = useId();
  const caption = Children.toArray(children).find(
    (child) => isValidElement<{ id?: string }>(child) && child.type === "caption",
  );
  const captionId = isValidElement<{ id?: string }>(caption) ? (caption.props.id ?? id) : undefined;
  const labelledBy = props["aria-labelledby"] ?? (props["aria-label"] ? undefined : captionId);
  return (
    <div
      aria-label={props["aria-label"]}
      aria-labelledby={labelledBy}
      className="nx-table-scroll"
      role={labelledBy || props["aria-label"] ? "region" : undefined}
      tabIndex={0}
    >
      <table className={classes("nx-table", className)} {...props}>
        {Children.map(children, (child) =>
          isValidElement<{ id?: string }>(child) && child.type === "caption"
            ? cloneElement(child, { id: captionId })
            : child,
        )}
      </table>
    </div>
  );
}

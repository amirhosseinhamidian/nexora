import { Children, cloneElement, isValidElement, type AriaAttributes, type ReactNode } from "react";
import { FieldError } from "./field-error";
import { classes } from "./shared";

export type FieldProps = {
  children: ReactNode;
  className?: string;
  description?: ReactNode;
  error?: ReactNode;
  id: string;
  label: ReactNode;
  optionalLabel?: ReactNode;
};

export function FormField({
  children,
  className,
  description,
  error,
  id,
  label,
  optionalLabel,
}: FieldProps) {
  const controls = Children.map(children, (child) => {
    if (!isValidElement<AriaAttributes & { id?: string }>(child) || child.props.id !== id)
      return child;
    const describedBy = new Set([
      ...(child.props["aria-describedby"]?.split(/\s+/).filter(Boolean) ?? []),
      ...(description ? [`${id}-description`] : []),
      ...(error ? [`${id}-error`] : []),
    ]);
    return cloneElement(child, {
      "aria-describedby": [...describedBy].join(" ") || undefined,
      "aria-invalid": error ? true : child.props["aria-invalid"],
    });
  });

  return (
    <div className={classes("nx-field", className)} data-invalid={Boolean(error) || undefined}>
      <div className="nx-field__label-row">
        <label htmlFor={id} id={`${id}-label`}>
          {label}
        </label>
        {optionalLabel ? <span>{optionalLabel}</span> : null}
      </div>
      {description ? (
        <p className="nx-field__description" id={`${id}-description`}>
          {description}
        </p>
      ) : null}
      {controls}
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : null}
    </div>
  );
}

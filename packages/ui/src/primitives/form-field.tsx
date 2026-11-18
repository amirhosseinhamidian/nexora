import type { ReactNode } from "react";
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
      {children}
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : null}
    </div>
  );
}

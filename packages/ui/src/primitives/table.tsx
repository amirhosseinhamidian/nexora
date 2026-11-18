import type { ComponentPropsWithoutRef } from "react";
import { classes } from "./shared";

export function Table({ className, ...props }: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="nx-table-scroll" tabIndex={0}>
      <table className={classes("nx-table", className)} {...props} />
    </div>
  );
}

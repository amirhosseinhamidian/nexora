import { Input, type InputProps } from "./input";
import { classes } from "./shared";

export function SearchInput({ className, type = "search", ...props }: InputProps) {
  return <Input className={classes("nx-search-input", className)} type={type} {...props} />;
}

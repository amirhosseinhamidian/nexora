import {
  type ComponentPropsWithoutRef,
  type KeyboardEvent,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { classes } from "./shared";

export type SelectOption = {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
};

type SelectProps = Pick<
  ComponentPropsWithoutRef<"button">,
  | "aria-describedby"
  | "aria-invalid"
  | "aria-label"
  | "aria-labelledby"
  | "aria-required"
  | "className"
  | "dir"
  | "disabled"
  | "id"
> & {
  options: readonly SelectOption[];
  onValueChange: (value: string) => void;
  placeholder?: string;
  value: string;
};

export function Select({
  className,
  disabled,
  onValueChange,
  options,
  placeholder,
  value,
  ...props
}: SelectProps) {
  const listId = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const search = useRef({ text: "", time: 0 });
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const selectedIndex = options.findIndex((option) => option.value === value);
  const enabled = options.flatMap((option, index) =>
    option.disabled ? [] : [index],
  );
  const initialIndex = enabled.includes(selectedIndex)
    ? selectedIndex
    : enabled[0];
  const unavailable = disabled || enabled.length === 0;
  const expanded = open && !unavailable;
  const active = enabled.includes(activeIndex)
    ? activeIndex
    : (enabled[0] ?? -1);

  function close() {
    search.current = { text: "", time: 0 };
    setOpen(false);
  }

  function choose(index: number) {
    const option = options[index];
    if (option && !option.disabled && option.value !== value)
      onValueChange(option.value);
    close();
  }

  function show(index: number) {
    setActiveIndex(index);
    setOpen(true);
  }

  useLayoutEffect(() => {
    if (!expanded || !trigger.current || !list.current) return;
    const anchor = trigger.current;
    const popup = list.current;

    function place() {
      const rect = anchor.getBoundingClientRect();
      const viewport = window.visualViewport;
      const insetTop = viewport?.offsetTop ?? 0;
      const viewportHeight = viewport?.height ?? window.innerHeight;
      const spaceBelow = insetTop + viewportHeight - rect.bottom - 12;
      const spaceAbove = rect.top - insetTop - 12;
      const above = spaceBelow < 180 && spaceAbove > spaceBelow;
      const height = Math.max(0, above ? spaceAbove : spaceBelow);

      popup.style.setProperty("--nx-select-left", `${rect.left}px`);
      popup.style.setProperty("--nx-select-width", `${rect.width}px`);
      popup.style.setProperty("--nx-select-height", `${height}px`);
      popup.style.setProperty(
        "--nx-select-top",
        above ? "auto" : `${rect.bottom + 4}px`,
      );
      popup.style.setProperty(
        "--nx-select-bottom",
        above ? `${window.innerHeight - rect.top + 4}px` : "auto",
      );
    }

    function closeOutside(event: Event) {
      const path = event.composedPath();
      if (path.includes(anchor) || path.includes(popup)) return;
      close();
    }

    if (
      !popup.hasAttribute("aria-label") &&
      !popup.hasAttribute("aria-labelledby")
    ) {
      const labels = Array.from(anchor.labels ?? []);
      if (labels.length && labels.every((label) => label.id)) {
        popup.setAttribute(
          "aria-labelledby",
          labels.map((label) => label.id).join(" "),
        );
      } else {
        const text = labels
          .map((label) => label.textContent?.trim())
          .filter(Boolean)
          .join(" ");
        if (text) popup.setAttribute("aria-label", text);
      }
    }

    // The top layer lets the list extend outside a scrolling form or sheet.
    // Fixed positioning also supports browsers without the Popover API.
    const nativePopover = typeof popup.showPopover === "function";
    if (nativePopover) {
      popup.setAttribute("popover", "manual");
      popup.showPopover();
    }
    place();
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("focusin", closeOutside);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    const viewport = window.visualViewport;
    viewport?.addEventListener("resize", place);
    viewport?.addEventListener("scroll", place);

    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("focusin", closeOutside);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      viewport?.removeEventListener("resize", place);
      viewport?.removeEventListener("scroll", place);
      if (nativePopover && popup.matches(":popover-open")) popup.hidePopover();
    };
  }, [expanded]);

  useLayoutEffect(() => {
    const popup = list.current;
    const option = popup?.children[active];
    if (!expanded || !popup || !option) return;
    const bounds = popup.getBoundingClientRect();
    const row = option.getBoundingClientRect();
    if (row.bottom > bounds.bottom)
      popup.scrollTop += row.bottom - bounds.bottom;
    if (row.top < bounds.top) popup.scrollTop += row.top - bounds.top;
  }, [active, expanded]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Tab") {
      if (expanded) choose(active);
      return;
    }
    if (event.key === "Escape") {
      if (!expanded) return;
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (expanded) choose(active);
      else show(initialIndex);
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      if (event.key === "Home") show(enabled[0]);
      else if (event.key === "End") show(enabled[enabled.length - 1]);
      else {
        const index = enabled.indexOf(expanded ? active : selectedIndex);
        const offset = event.key === "ArrowDown" ? 1 : -1;
        const next =
          index === -1 && offset === -1 ? enabled.length - 1 : index + offset;
        show(enabled[Math.max(0, Math.min(next, enabled.length - 1))]);
      }
      return;
    }
    if (
      event.key.length !== 1 ||
      event.ctrlKey ||
      event.metaKey ||
      event.altKey
    )
      return;

    const now = Date.now();
    const key = event.key.toLocaleLowerCase();
    const previous = now - search.current.time < 600 ? search.current.text : "";
    const query = previous === key ? key : previous + key;
    search.current = { time: now, text: query };
    const start = enabled.indexOf(expanded ? active : selectedIndex);
    const offset = previous && previous !== key ? start : start + 1;
    const match = enabled
      .slice(Math.max(0, offset))
      .concat(enabled.slice(0, Math.max(0, offset)))
      .find((index) =>
        options[index].label.toLocaleLowerCase().startsWith(query),
      );
    if (match !== undefined) show(match);
  }

  return (
    <>
      <button
        {...props}
        aria-activedescendant={expanded ? `${listId}-${active}` : undefined}
        aria-controls={expanded ? listId : undefined}
        aria-expanded={expanded}
        className={classes("nx-input", "nx-select", className)}
        disabled={unavailable}
        onClick={() => {
          if (expanded) close();
          else show(initialIndex);
        }}
        onKeyDown={handleKeyDown}
        ref={trigger}
        role="combobox"
        type="button"
        value={value}
      >
        <span className="nx-select__value">
          {options[selectedIndex]?.label ?? placeholder}
        </span>
        <span aria-hidden="true" className="nx-select__chevron" />
      </button>
      {expanded ? (
        <ul
          aria-label={props["aria-label"]}
          aria-labelledby={props["aria-labelledby"]}
          className="nx-select__list"
          dir={props.dir}
          id={listId}
          ref={list}
          role="listbox"
        >
          {options.map((option, index) => (
            <li
              aria-disabled={option.disabled || undefined}
              aria-selected={index === selectedIndex}
              className="nx-select__option"
              data-active={index === active || undefined}
              id={`${listId}-${index}`}
              key={option.value}
              onClick={() => {
                if (!option.disabled) choose(index);
              }}
              onMouseDown={(event) => event.preventDefault()}
              role="option"
            >
              <span className="nx-select__option-text">
                <span>{option.label}</span>
                {option.description ? (
                  <small>{option.description}</small>
                ) : null}
              </span>
              {index === selectedIndex ? (
                <span aria-hidden="true">✓</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

import { Button } from "./button";

export function Pagination({
  currentPage,
  label,
  nextLabel,
  onPageChange,
  previousLabel,
  totalPages,
}: {
  currentPage: number;
  label: string;
  nextLabel: string;
  onPageChange: (page: number) => void;
  previousLabel: string;
  totalPages: number;
}) {
  return (
    <nav aria-label={label} className="nx-pagination">
      <Button
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        variant="secondary"
      >
        {previousLabel}
      </Button>
      <span aria-current="page">
        {currentPage} / {totalPages}
      </span>
      <Button
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        variant="secondary"
      >
        {nextLabel}
      </Button>
    </nav>
  );
}

import { Link } from "react-router-dom";

interface QualityEmptyStateProps {
  message: string;
  title?: string;
  /** Acción sugerida, p. ej. "Ver configuración" o el comando del pipeline. */
  action?: { label: string; to: string };
}

/**
 * Estado "sin datos" explícito. Se distingue del error a propósito: que un
 * artefacto todavía no exista es normal durante el desarrollo, no una falla.
 */
export function QualityEmptyState({
  message,
  title = "Sin datos",
  action,
}: QualityEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-strong bg-surface px-6 py-16 text-center">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="max-w-lg text-sm text-ink-muted">{message}</p>
      {action && (
        <Link
          to={action.to}
          className="mt-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-sidebar hover:text-ink"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}

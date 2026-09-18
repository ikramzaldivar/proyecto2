import type { CategoryRef, SpatialBiasReport, SpatialStats } from "../../../api/quality";
import { QualityStat } from "../QualityStat";

function StatsTable({ title, stats }: { title: string; stats: SpatialStats }) {
  const rows: Array<[string, number, number]> = [
    ["Media", stats.mean_x, stats.mean_y],
    ["Mediana", stats.median_x, stats.median_y],
    ["Desviación", stats.std_x, stats.std_y],
    ["Percentil 25", stats.p25_x, stats.p25_y],
    ["Percentil 75", stats.p75_x, stats.p75_y],
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <div className="border-b border-border bg-sidebar px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
        {title}
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-medium">Estadístico</th>
            <th className="px-4 py-2 font-medium">Centro X</th>
            <th className="px-4 py-2 font-medium">Centro Y</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, x, y]) => (
            <tr key={label} className="border-b border-border last:border-b-0">
              <td className="px-4 py-2 font-medium text-ink">{label}</td>
              <td className="px-4 py-2 text-ink-muted">{x.toFixed(3)}</td>
              <td className="px-4 py-2 text-ink-muted">{y.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SpatialBiasPanel({
  report,
  categories,
}: {
  report: SpatialBiasReport;
  categories: CategoryRef[];
}) {
  const names = new Map(categories.map((category) => [category.id, category.name]));
  const entries = Object.entries(report.stats_by_category);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <QualityStat label="Objetos medidos" value={report.global_stats.count} />
        <QualityStat label="Centro medio X" value={report.global_stats.mean_x.toFixed(3)} />
        <QualityStat label="Centro medio Y" value={report.global_stats.mean_y.toFixed(3)} />
        <QualityStat label="Dispersión X" value={report.global_stats.std_x.toFixed(3)} />
      </div>

      <StatsTable title="Estadística global (centro normalizado 0–1)" stats={report.global_stats} />

      <div className="rounded-2xl border border-border bg-surface p-5 shadow-card">
        <h3 className="mb-3 text-sm font-medium text-ink">Centro medio por categoría</h3>
        <div className="relative mx-auto aspect-square w-full max-w-sm rounded-xl border border-dashed border-border-strong bg-canvas">
          {entries.map(([categoryId, stats]) => (
            <span
              key={categoryId}
              title={`${names.get(Number(categoryId)) ?? `#${categoryId}`}: (${stats.mean_x.toFixed(2)}, ${stats.mean_y.toFixed(2)})`}
              className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent-lilac ring-2 ring-white"
              style={{ left: `${stats.mean_x * 100}%`, top: `${stats.mean_y * 100}%` }}
            >
              <span className="sr-only">{names.get(Number(categoryId)) ?? `#${categoryId}`}</span>
            </span>
          ))}
        </div>
        <p className="mt-2 text-center text-xs text-ink-faint">
          Posición promedio del centro de cada caja, normalizada por el tamaño de su imagen.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {entries.map(([categoryId, stats]) => (
          <StatsTable
            key={categoryId}
            title={`Categoría ${names.get(Number(categoryId)) ?? `#${categoryId}`} (${stats.count} objetos)`}
            stats={stats}
          />
        ))}
      </div>
    </div>
  );
}

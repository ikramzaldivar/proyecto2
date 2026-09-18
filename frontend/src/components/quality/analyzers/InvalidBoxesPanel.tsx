import type { InvalidBoxesReport } from "../../../api/quality";
import { QualityStat } from "../QualityStat";
import { type SampleRef, SamplesList } from "../SamplesList";

export function InvalidBoxesPanel({ report }: { report: InvalidBoxesReport }) {
  const samples: SampleRef[] = report.invalid_boxes.map((box) => ({
    id: box.annotation_id,
    imageId: box.image_id,
    caption: `bbox [${box.bbox.join(", ")}] · ${box.reasons.join(", ")}`,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <QualityStat
          label="Cajas inválidas"
          value={`${report.invalid_count} de ${report.total_annotations}`}
        />
        <QualityStat label="Umbral" value={report.threshold} />
        <QualityStat label="Severidad" value={report.severity} />
      </div>

      <SamplesList title="Cajas inválidas" samples={samples} />
    </div>
  );
}

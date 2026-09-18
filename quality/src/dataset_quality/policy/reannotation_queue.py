from pydantic import BaseModel

from dataset_quality.analyzers.invalid_boxes import InvalidBoxesReport
from dataset_quality.models.config import Severity


class ReannotationQueueItem(BaseModel):
    annotation_id: int
    image_id: int
    reason: str
    analyzer: str
    severity: Severity


def build_reannotation_queue(invalid_boxes: InvalidBoxesReport) -> list[ReannotationQueueItem]:
    """Función pura (CAL 00). Convierte las cajas inválidas detectadas por
    CAL 06 en una cola de reanotación consumible por el portal.

    Es deliberadamente derivada del reporte, no de estado propio: si se
    vuelve a correr analyze_invalid_boxes sobre un dataset ya corregido, la
    muestra corregida simplemente no aparece en el nuevo reporte, y por lo
    tanto tampoco en la cola — "salir de la cola" es una consecuencia
    natural de la función pura, no un estado que haya que limpiar aparte.
    """
    return [
        ReannotationQueueItem(
            annotation_id=box.annotation_id,
            image_id=box.image_id,
            reason=", ".join(box.reasons),
            analyzer="invalid_boxes",
            severity=invalid_boxes.severity,
        )
        for box in invalid_boxes.invalid_boxes
    ]

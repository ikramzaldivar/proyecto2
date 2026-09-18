import { Bot } from "lucide-react";
import { QualityPageShell } from "../../components/quality/QualityPageShell";

/**
 * Vista Copilot (Story B). Queda enrutada y consume el mismo contrato de
 * calidad; las tool calls del servidor MCP y el agente se conectan en la
 * story "MCP read-only y Dataset Copilot". No muestra cifras de ejemplo:
 * hasta que el backend exista, declara explícitamente que está pendiente.
 */
export function CopilotPage() {
  return (
    <QualityPageShell
      title="Copilot"
      subtitle="Preguntas sobre el dataset respondidas con herramientas de solo lectura."
    >
      <div className="rounded-2xl border border-dashed border-border-strong bg-surface px-6 py-16 text-center">
        <Bot className="mx-auto h-8 w-8 text-ink-faint" aria-hidden />
        <p className="mt-3 text-sm font-semibold text-ink">Copilot pendiente de integración</p>
        <p className="mx-auto mt-1 max-w-lg text-sm text-ink-muted">
          La vista ya está enrutada. El servidor MCP y las tool calls del agente se conectan en la
          siguiente story, sobre los mismos artefactos de calidad que alimentan a las otras
          pantallas.
        </p>
      </div>
    </QualityPageShell>
  );
}

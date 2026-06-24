import { Card, CardContent } from "@/components/ui/card";

/**
 * Compact KPI card shared across the Revenue-Intelligence pages: an uppercase
 * label, a large tabular value, and an optional sub-line. `value` is a
 * pre-formatted string ("$12,500" / "57.6%" / "—") so each page owns its
 * null → "—" rendering.
 */
export function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="space-y-1 py-4">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {sub ? (
          <div className="text-xs text-muted-foreground">{sub}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

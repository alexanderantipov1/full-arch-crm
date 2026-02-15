import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  TrendingUp,
  DollarSign,
  Users,
  Target,
  BarChart3,
  MapPin,
} from "lucide-react";

const locations = [
  { name: "Auburn Main", production: "$198,200", collections: "96.2%", newPts: "38", accept: "72%", overhead: "57.3%", margin: "42.7%" },
  { name: "Roseville", production: "$142,800", collections: "94.8%", newPts: "28", accept: "68%", overhead: "61.2%", margin: "33.6%" },
  { name: "Folsom", production: "$168,400", collections: "97.1%", newPts: "34", accept: "74%", overhead: "55.8%", margin: "41.3%" },
  { name: "Rocklin (New)", production: "$84,200", collections: "92.4%", newPts: "22", accept: "64%", overhead: "68.4%", margin: "24.0%" },
];

export default function MultiLocationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Multi-Location Command Center
        </h1>
        <p className="text-sm text-muted-foreground">
          Side-by-side performance, centralized management, location benchmarking
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <MapPin className="h-3.5 w-3.5" />
              Locations
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-locations">4</div>
            <p className="text-xs font-medium text-muted-foreground">1 new (Rocklin)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Total Production
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-total-prod">$593,600</div>
            <p className="text-xs font-medium text-muted-foreground">All locations MTD</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              New Patients
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-new-pts">122</div>
            <p className="text-xs font-medium text-muted-foreground">Across all locations</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Avg Margin
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-avg-margin">35.4%</div>
            <p className="text-xs font-medium text-muted-foreground">Weighted avg</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Location Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">Location</th>
                  <th className="pb-3 pr-4">Production</th>
                  <th className="pb-3 pr-4">Collections %</th>
                  <th className="pb-3 pr-4">New Pts</th>
                  <th className="pb-3 pr-4">Accept %</th>
                  <th className="pb-3 pr-4">Overhead</th>
                  <th className="pb-3">Net Margin</th>
                </tr>
              </thead>
              <tbody>
                {locations.map((loc, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`location-row-${i}`}>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <MapPin className="h-3.5 w-3.5 text-primary" />
                        <span className="font-bold">{loc.name}</span>
                      </div>
                    </td>
                    <td className="py-3 pr-4 font-mono font-bold">{loc.production}</td>
                    <td className="py-3 pr-4">
                      <span className={`font-bold ${parseFloat(loc.collections) >= 95 ? "text-emerald-600 dark:text-emerald-400" : "text-yellow-600 dark:text-yellow-400"}`}>
                        {loc.collections}
                      </span>
                    </td>
                    <td className="py-3 pr-4 font-bold">{loc.newPts}</td>
                    <td className="py-3 pr-4">
                      <span className={`font-bold ${parseInt(loc.accept) >= 70 ? "text-emerald-600 dark:text-emerald-400" : "text-yellow-600 dark:text-yellow-400"}`}>
                        {loc.accept}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`font-bold ${parseFloat(loc.overhead) < 60 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"}`}>
                        {loc.overhead}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`text-sm font-black ${parseFloat(loc.margin) >= 40 ? "text-emerald-600 dark:text-emerald-400" : parseFloat(loc.margin) >= 30 ? "text-yellow-600 dark:text-yellow-400" : "text-destructive"}`}>
                        {loc.margin}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {locations.map((loc, i) => (
          <Card key={i}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-primary" />
                  {loc.name}
                </div>
                <Badge variant={parseFloat(loc.margin) >= 40 ? "default" : "outline"}>
                  {loc.margin} margin
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-xs text-muted-foreground">Production</span>
                  <div className="font-bold font-mono">{loc.production}</div>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Collections</span>
                  <div className="font-bold">{loc.collections}</div>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">New Patients</span>
                  <div className="font-bold">{loc.newPts}</div>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Acceptance</span>
                  <div className="font-bold">{loc.accept}</div>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Overhead</span>
                  <div className={`font-bold ${parseFloat(loc.overhead) < 60 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"}`}>{loc.overhead}</div>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Net Margin</span>
                  <div className={`font-bold ${parseFloat(loc.margin) >= 40 ? "text-emerald-600 dark:text-emerald-400" : "text-yellow-600 dark:text-yellow-400"}`}>{loc.margin}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

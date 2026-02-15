import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Package,
  AlertTriangle,
  Calendar,
  DollarSign,
  Plus,
  Search,
  ShoppingCart,
  RefreshCcw,
} from "lucide-react";

const inventoryItems = [
  { item: "Composite A2 (4g)", category: "Restorative", stock: "12", reorder: "10", vendor: "Henry Schein", cost: "$42.50", status: "Low", statusColor: "outline" as const },
  { item: "Implant Body 4.1x10", category: "Implant", stock: "3", reorder: "5", vendor: "Straumann", cost: "$285", status: "Critical", statusColor: "destructive" as const },
  { item: "Nitrile Gloves (M)", category: "PPE", stock: "24 boxes", reorder: "10", vendor: "Amazon", cost: "$12.99", status: "OK", statusColor: "default" as const },
  { item: "Lidocaine 2%", category: "Anesthesia", stock: "48 carp", reorder: "20", vendor: "Patterson", cost: "$28.50", status: "OK", statusColor: "default" as const },
  { item: "Bite Registration", category: "Impression", stock: "6", reorder: "8", vendor: "Dentsply", cost: "$34", status: "Low", statusColor: "outline" as const },
  { item: "Sterilization Pouches", category: "Infection Ctrl", stock: "2 boxes", reorder: "5", vendor: "Crosstex", cost: "$18.50", status: "Critical", statusColor: "destructive" as const },
  { item: "Surgical Sutures 4-0", category: "Surgical", stock: "18", reorder: "12", vendor: "Ethicon", cost: "$8.50", status: "OK", statusColor: "default" as const },
  { item: "Prophy Paste", category: "Hygiene", stock: "8 jars", reorder: "6", vendor: "Patterson", cost: "$14.50", status: "OK", statusColor: "default" as const },
];

export default function InventoryPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            Inventory & Supply Management
          </h1>
          <p className="text-sm text-muted-foreground">
            Auto-reorder, vendor comparison, expiration tracking
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="button-auto-reorder">
            <ShoppingCart className="mr-2 h-4 w-4" />
            Auto-Reorder
          </Button>
          <Button data-testid="button-add-item">
            <Plus className="mr-2 h-4 w-4" />
            Add Item
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Package className="h-3.5 w-3.5" />
              Total SKUs
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-skus">342</div>
            <p className="text-xs font-medium text-muted-foreground">Across 12 categories</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Low Stock
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-low-stock">8</div>
            <p className="text-xs font-medium text-muted-foreground">3 critical</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" />
              Expiring &lt;90d
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-expiring">12</div>
            <p className="text-xs font-medium text-muted-foreground">Review by March</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Monthly Spend
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-spend">$11,400</div>
            <p className="text-xs font-medium text-muted-foreground">5.7% of production</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Inventory List
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">Item</th>
                  <th className="pb-3 pr-4">Category</th>
                  <th className="pb-3 pr-4">Stock</th>
                  <th className="pb-3 pr-4">Reorder At</th>
                  <th className="pb-3 pr-4">Vendor</th>
                  <th className="pb-3 pr-4">Unit Cost</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {inventoryItems.map((item, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`inventory-row-${i}`}>
                    <td className="py-3 pr-4 font-bold">{item.item}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{item.category}</td>
                    <td className="py-3 pr-4 font-mono">{item.stock}</td>
                    <td className="py-3 pr-4 text-muted-foreground font-mono">{item.reorder}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{item.vendor}</td>
                    <td className="py-3 pr-4 font-mono">{item.cost}</td>
                    <td className="py-3">
                      <Badge variant={item.statusColor}>{item.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

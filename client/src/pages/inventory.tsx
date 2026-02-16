import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  Package,
  AlertTriangle,
  Calendar,
  DollarSign,
  Plus,
  ShoppingCart,
  RefreshCcw,
  Truck,
  Store,
  Phone,
  Mail,
  CheckCircle,
  Clock,
  FileText,
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

const lowStockItems = inventoryItems.filter(i => i.status === "Critical" || i.status === "Low");

const orders = [
  { id: "PO-2026-041", vendor: "Straumann", items: 3, total: "$1,425.00", date: "Feb 14, 2026", eta: "Feb 18, 2026", status: "Shipped" },
  { id: "PO-2026-040", vendor: "Henry Schein", items: 8, total: "$892.50", date: "Feb 12, 2026", eta: "Feb 15, 2026", status: "Delivered" },
  { id: "PO-2026-039", vendor: "Patterson", items: 5, total: "$345.00", date: "Feb 10, 2026", eta: "Feb 14, 2026", status: "Delivered" },
  { id: "PO-2026-038", vendor: "Crosstex", items: 4, total: "$218.00", date: "Feb 8, 2026", eta: "Feb 12, 2026", status: "Delivered" },
  { id: "PO-2026-037", vendor: "Dentsply", items: 6, total: "$567.00", date: "Feb 5, 2026", eta: "Feb 10, 2026", status: "Delivered" },
];

const vendors = [
  { name: "Henry Schein", rep: "Mike Johnson", phone: "(800) 372-4346", email: "mjohnson@henryschein.com", category: "General", lastOrder: "Feb 12", avgDelivery: "3 days", rating: 4.5 },
  { name: "Straumann", rep: "Lisa Park", phone: "(800) 448-8168", email: "lpark@straumann.com", category: "Implants", lastOrder: "Feb 14", avgDelivery: "4 days", rating: 4.8 },
  { name: "Patterson", rep: "David Kim", phone: "(800) 328-5536", email: "dkim@pattersondental.com", category: "General", lastOrder: "Feb 10", avgDelivery: "3 days", rating: 4.3 },
  { name: "Dentsply Sirona", rep: "Amy Chen", phone: "(800) 532-2855", email: "achen@dentsplysirona.com", category: "Impression", lastOrder: "Feb 5", avgDelivery: "5 days", rating: 4.1 },
  { name: "Crosstex", rep: "John Miller", phone: "(888) 276-7783", email: "jmiller@crosstex.com", category: "Infection Ctrl", lastOrder: "Feb 8", avgDelivery: "4 days", rating: 4.0 },
  { name: "Amazon Business", rep: "\u2014", phone: "\u2014", email: "\u2014", category: "PPE/Supplies", lastOrder: "Feb 11", avgDelivery: "2 days", rating: 4.2 },
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
        <div className="flex gap-2 flex-wrap">
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

      <Tabs defaultValue="inventory" className="space-y-4">
        <TabsList data-testid="tabs-inventory">
          <TabsTrigger value="inventory" data-testid="tab-inventory">
            <Package className="mr-1.5 h-3.5 w-3.5" />
            Inventory
          </TabsTrigger>
          <TabsTrigger value="low-stock" data-testid="tab-low-stock">
            <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
            Low Stock Alerts
          </TabsTrigger>
          <TabsTrigger value="orders" data-testid="tab-orders">
            <Truck className="mr-1.5 h-3.5 w-3.5" />
            Orders
          </TabsTrigger>
          <TabsTrigger value="vendors" data-testid="tab-vendors">
            <Store className="mr-1.5 h-3.5 w-3.5" />
            Vendors
          </TabsTrigger>
        </TabsList>

        <TabsContent value="inventory">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2">
                <Package className="h-4 w-4" />
                Inventory List
              </CardTitle>
              <Button size="icon" variant="outline" data-testid="button-refresh-inventory">
                <RefreshCcw className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Stock</TableHead>
                      <TableHead>Reorder Level</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Unit Cost</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {inventoryItems.map((item, i) => (
                      <TableRow key={i} data-testid={`inventory-row-${i}`}>
                        <TableCell className="font-bold" data-testid={`inventory-name-${i}`}>{item.item}</TableCell>
                        <TableCell className="text-muted-foreground">{item.category}</TableCell>
                        <TableCell className="font-mono" data-testid={`inventory-stock-${i}`}>{item.stock}</TableCell>
                        <TableCell className="text-muted-foreground font-mono">{item.reorder}</TableCell>
                        <TableCell className="text-muted-foreground">{item.vendor}</TableCell>
                        <TableCell className="font-mono">{item.cost}</TableCell>
                        <TableCell>
                          <Badge variant={item.statusColor} data-testid={`inventory-status-${i}`}>{item.status}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="low-stock">
          <div className="space-y-4">
            <Alert variant="destructive" data-testid="alert-low-stock">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {lowStockItems.filter(i => i.status === "Critical").length} items are at critical stock levels and need immediate reorder. {lowStockItems.filter(i => i.status === "Low").length} items are running low.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Items Requiring Attention
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Current Stock</TableHead>
                        <TableHead>Reorder Level</TableHead>
                        <TableHead>Vendor</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {lowStockItems.map((item, i) => (
                        <TableRow key={i} data-testid={`low-stock-row-${i}`}>
                          <TableCell className="font-bold">{item.item}</TableCell>
                          <TableCell className="text-muted-foreground">{item.category}</TableCell>
                          <TableCell className="font-mono font-bold text-destructive">{item.stock}</TableCell>
                          <TableCell className="text-muted-foreground font-mono">{item.reorder}</TableCell>
                          <TableCell className="text-muted-foreground">{item.vendor}</TableCell>
                          <TableCell>
                            <Badge variant={item.statusColor}>{item.status}</Badge>
                          </TableCell>
                          <TableCell>
                            <Button size="sm" data-testid={`button-reorder-${i}`}>
                              <ShoppingCart className="mr-1 h-3 w-3" />
                              Reorder
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="orders">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2">
                <Truck className="h-4 w-4" />
                Recent Purchase Orders
              </CardTitle>
              <Button variant="outline" data-testid="button-new-order">
                <Plus className="mr-2 h-4 w-4" />
                New Order
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Order ID</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Items</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Order Date</TableHead>
                      <TableHead>ETA</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {orders.map((order, i) => (
                      <TableRow key={i} data-testid={`order-row-${i}`}>
                        <TableCell className="font-mono font-bold" data-testid={`order-id-${i}`}>{order.id}</TableCell>
                        <TableCell>{order.vendor}</TableCell>
                        <TableCell className="font-mono">{order.items}</TableCell>
                        <TableCell className="font-mono" data-testid={`order-total-${i}`}>{order.total}</TableCell>
                        <TableCell className="text-muted-foreground">{order.date}</TableCell>
                        <TableCell className="text-muted-foreground">{order.eta}</TableCell>
                        <TableCell>
                          <Badge
                            variant={order.status === "Shipped" ? "outline" : "default"}
                            data-testid={`order-status-${i}`}
                          >
                            {order.status === "Shipped" ? (
                              <Truck className="mr-1 h-3 w-3" />
                            ) : (
                              <CheckCircle className="mr-1 h-3 w-3" />
                            )}
                            {order.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="vendors">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2">
                <Store className="h-4 w-4" />
                Vendor Directory
              </CardTitle>
              <Button variant="outline" data-testid="button-add-vendor">
                <Plus className="mr-2 h-4 w-4" />
                Add Vendor
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Rep</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Last Order</TableHead>
                      <TableHead>Avg Delivery</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendors.map((vendor, i) => (
                      <TableRow key={i} data-testid={`vendor-row-${i}`}>
                        <TableCell className="font-bold" data-testid={`vendor-name-${i}`}>{vendor.name}</TableCell>
                        <TableCell className="text-muted-foreground">{vendor.rep}</TableCell>
                        <TableCell>
                          {vendor.phone !== "\u2014" ? (
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Phone className="h-3 w-3" />
                                {vendor.phone}
                              </div>
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Mail className="h-3 w-3" />
                                {vendor.email}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">Online</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{vendor.category}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{vendor.lastOrder}</TableCell>
                        <TableCell className="text-muted-foreground">{vendor.avgDelivery}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

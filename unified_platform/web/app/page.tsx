import { KpiCard } from "@/components/kpi-card";
import { WSStatus } from "@/components/ws-status";
import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type DashboardKpis = {
  products_total: number;
  variants_total: number;
  suppliers_total: number;
  purchase_orders_open: number;
  inbound_shipments_active: number;
  low_stock_alerts_open: number;
  stock_value_fifo: number;
  stock_value_wac: number;
};

type SyncStatus = {
  pending: number;
  processed: number;
  failed: number;
  last_error: string | null;
};

async function loadKpis(): Promise<DashboardKpis> {
  const token = await getDemoToken();
  if (!token) {
    return {
      products_total: 0,
      variants_total: 0,
      suppliers_total: 0,
      purchase_orders_open: 0,
      inbound_shipments_active: 0,
      low_stock_alerts_open: 0,
      stock_value_fifo: 0,
      stock_value_wac: 0
    };
  }
  try {
    return await apiGet<DashboardKpis>("/api/v1/dashboard/kpis", token);
  } catch {
    return {
      products_total: 0,
      variants_total: 0,
      suppliers_total: 0,
      purchase_orders_open: 0,
      inbound_shipments_active: 0,
      low_stock_alerts_open: 0,
      stock_value_fifo: 0,
      stock_value_wac: 0
    };
  }
}

async function loadSyncStatus(): Promise<SyncStatus> {
  const token = await getDemoToken();
  if (!token) {
    return { pending: 0, processed: 0, failed: 0, last_error: null };
  }
  try {
    return await apiGet<SyncStatus>("/api/v1/integration/sync-status", token);
  } catch {
    return { pending: 0, processed: 0, failed: 0, last_error: null };
  }
}

export default async function DashboardPage() {
  const [kpis, syncStatus] = await Promise.all([loadKpis(), loadSyncStatus()]);

  return (
    <section>
      <h1 className="page-title">Operations Dashboard</h1>
      <p className="page-subtitle">
        Single control plane for PIM, receiving, inventory and compliance-ready stock flows.{" "}
        <WSStatus path="/api/v1/ws/dashboard" />
      </p>
      <div className="kpi-grid">
        <KpiCard label="Products" value={kpis.products_total} />
        <KpiCard label="Variants" value={kpis.variants_total} />
        <KpiCard label="Suppliers" value={kpis.suppliers_total} />
        <KpiCard label="Open POs" value={kpis.purchase_orders_open} />
        <KpiCard label="Inbound Active" value={kpis.inbound_shipments_active} />
        <KpiCard label="Low Stock Alerts" value={kpis.low_stock_alerts_open} />
        <KpiCard label="FIFO Value" value={`${kpis.stock_value_fifo.toFixed(2)} SEK`} />
        <KpiCard label="WAC Value" value={`${kpis.stock_value_wac.toFixed(2)} SEK`} />
        <KpiCard label="Sync Queue Pending" value={syncStatus.pending} />
        <KpiCard label="Sync Failures" value={syncStatus.failed} />
      </div>
    </section>
  );
}

import { WSStatus } from "@/components/ws-status";
import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type StockRow = {
  id: number;
  location_id: number;
  variant_id: number;
  on_hand_qty: string;
  reserved_qty: string;
  available_qty: string;
};

async function loadStock(): Promise<StockRow[]> {
  const token = await getDemoToken();
  if (!token) {
    return [];
  }
  try {
    return await apiGet<StockRow[]>("/api/v1/inventory/stock", token);
  } catch {
    return [];
  }
}

export default async function InventoryStockPage() {
  const rows = await loadStock();

  return (
    <section>
      <h1 className="page-title">Inventory Matrix</h1>
      <p className="page-subtitle">
        Real-time stock by location, lot and variant. <WSStatus path="/api/v1/ws/inventory/1" />
      </p>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Location</th>
              <th>Variant</th>
              <th>On Hand</th>
              <th>Reserved</th>
              <th>Available</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6}>No stock records yet.</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.location_id}</td>
                  <td>{row.variant_id}</td>
                  <td>{row.on_hand_qty}</td>
                  <td>{row.reserved_qty}</td>
                  <td>{row.available_qty}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

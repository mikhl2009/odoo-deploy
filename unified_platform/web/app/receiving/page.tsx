import { WSStatus } from "@/components/ws-status";
import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type Shipment = {
  id: number;
  supplier_id: number;
  source_type: string;
  status: string;
};

async function loadShipments(): Promise<Shipment[]> {
  const token = await getDemoToken();
  if (!token) return [];
  try {
    return await apiGet<Shipment[]>("/api/v1/inbound-shipments", token);
  } catch {
    return [];
  }
}

export default async function ReceivingPage() {
  const shipments = await loadShipments();

  return (
    <section>
      <h1 className="page-title">Receiving Workstation</h1>
      <p className="page-subtitle">
        Tablet-friendly inbound flow for scan, discrepancy logging and receipt confirmation.{" "}
        <WSStatus path="/api/v1/ws/receiving/1" />
      </p>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Shipment</th>
              <th>Supplier</th>
              <th>Source</th>
              <th>Status</th>
              <th>Next Action</th>
            </tr>
          </thead>
          <tbody>
            {shipments.length === 0 ? (
              <tr>
                <td colSpan={5}>No inbound shipments yet.</td>
              </tr>
            ) : (
              shipments.map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.id}</td>
                  <td>{shipment.supplier_id}</td>
                  <td>{shipment.source_type}</td>
                  <td><span className="pill">{shipment.status}</span></td>
                  <td>Use API to scan/start/confirm</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type SalesOrder = {
  id: number;
  order_number: string;
  channel_type: string;
  status: string;
  total: string;
  customer_id: number | null;
};

async function loadOrders(): Promise<SalesOrder[]> {
  const token = await getDemoToken();
  if (!token) {
    return [];
  }
  try {
    return await apiGet<SalesOrder[]>("/api/v1/sales/orders", token);
  } catch {
    return [];
  }
}

export default async function SalesOrdersPage() {
  const orders = await loadOrders();

  return (
    <section>
      <h1 className="page-title">Sales Orders</h1>
      <p className="page-subtitle">
        Unified order lifecycle across web, wholesale and internal channels.
      </p>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Order No</th>
              <th>Channel</th>
              <th>Status</th>
              <th>Customer</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={6}>No sales orders yet.</td>
              </tr>
            ) : (
              orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td>
                  <td>{order.order_number}</td>
                  <td>{order.channel_type}</td>
                  <td>
                    <span className="pill">{order.status}</span>
                  </td>
                  <td>{order.customer_id || "-"}</td>
                  <td>{order.total}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

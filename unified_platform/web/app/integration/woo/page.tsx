import { WSStatus } from "@/components/ws-status";
import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type SyncStatus = {
  queue_pending: number;
  queue_failed: number;
  queue_done: number;
  webhooks_pending: number;
  webhooks_processed: number;
};

type Connection = {
  id: number;
  store_channel_id: number;
  provider: string;
  api_base_url: string;
  active: boolean;
};

async function loadSyncStatus(): Promise<SyncStatus> {
  const token = await getDemoToken();
  if (!token) {
    return { queue_pending: 0, queue_failed: 0, queue_done: 0, webhooks_pending: 0, webhooks_processed: 0 };
  }
  try {
    return await apiGet<SyncStatus>("/api/v1/integration/woo/sync-status", token);
  } catch {
    return { queue_pending: 0, queue_failed: 0, queue_done: 0, webhooks_pending: 0, webhooks_processed: 0 };
  }
}

async function loadConnections(): Promise<Connection[]> {
  const token = await getDemoToken();
  if (!token) return [];
  try {
    return await apiGet<Connection[]>("/api/v1/integration/woo/connections", token);
  } catch {
    return [];
  }
}

export default async function WooIntegrationPage() {
  const [status, connections] = await Promise.all([loadSyncStatus(), loadConnections()]);

  return (
    <section>
      <h1 className="page-title">WooCommerce Sync</h1>
      <p className="page-subtitle">
        Webhook ingestion, queue health and store connection control. <WSStatus path="/api/v1/ws/sync-status" />
      </p>

      <div className="kpi-grid">
        <article className="card kpi">
          <p className="kpi-label">Queue Pending</p>
          <p className="kpi-value">{status.queue_pending}</p>
        </article>
        <article className="card kpi">
          <p className="kpi-label">Queue Failed</p>
          <p className="kpi-value">{status.queue_failed}</p>
        </article>
        <article className="card kpi">
          <p className="kpi-label">Queue Done</p>
          <p className="kpi-value">{status.queue_done}</p>
        </article>
        <article className="card kpi">
          <p className="kpi-label">Webhooks Processed</p>
          <p className="kpi-value">{status.webhooks_processed}</p>
        </article>
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Store Channel</th>
              <th>Provider</th>
              <th>API Base URL</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {connections.length === 0 ? (
              <tr>
                <td colSpan={5}>No Woo connections configured yet.</td>
              </tr>
            ) : (
              connections.map((connection) => (
                <tr key={connection.id}>
                  <td>{connection.id}</td>
                  <td>{connection.store_channel_id}</td>
                  <td>{connection.provider}</td>
                  <td>{connection.api_base_url}</td>
                  <td>{connection.active ? "Yes" : "No"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

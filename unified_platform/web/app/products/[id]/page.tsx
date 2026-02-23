import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type Product = {
  id: number;
  name: string | null;
  brand: string | null;
  sku: string;
  ean: string | null;
  default_price: string | number | null;
  variant_count: number;
  status: string;
  product_type: string;
  is_tobacco: boolean;
};

type Revision = {
  id: number;
  revision_no: number;
  changed_at: string;
};

function formatCurrency(value: string | number | null | undefined): string {
  if (value == null) return "-";
  return Number(value).toLocaleString("sv-SE", { style: "currency", currency: "SEK" });
}

async function loadProduct(id: string): Promise<Product | null> {
  const token = await getDemoToken();
  if (!token) return null;
  try {
    return await apiGet<Product>(`/api/v1/products/${id}`, token);
  } catch {
    return null;
  }
}

async function loadRevisions(id: string): Promise<Revision[]> {
  const token = await getDemoToken();
  if (!token) return [];
  try {
    return await apiGet<Revision[]>(`/api/v1/revisions/pim_product/${id}`, token);
  } catch {
    return [];
  }
}

export default async function ProductDetailPage({
  params
}: {
  params: { id: string };
}) {
  const [product, revisions] = await Promise.all([
    loadProduct(params.id),
    loadRevisions(params.id)
  ]);

  if (!product) {
    return (
      <section>
        <h1 className="page-title">Product not found</h1>
      </section>
    );
  }

  return (
    <section>
      <h1 className="page-title">{product.name || product.sku}</h1>
      <p className="page-subtitle">
        SKU {product.sku} with synced brand, price and revision history.
      </p>

      <div className="card">
        <p><strong>Name:</strong> {product.name || product.sku}</p>
        <p><strong>Brand:</strong> {product.brand || "-"}</p>
        <p><strong>Price:</strong> {formatCurrency(product.default_price)}</p>
        <p><strong>Variants:</strong> {product.variant_count}</p>
        <p><strong>Status:</strong> {product.status}</p>
        <p><strong>EAN:</strong> {product.ean || "-"}</p>
        <p><strong>Type:</strong> {product.product_type}</p>
        <p><strong>Tobacco:</strong> {product.is_tobacco ? "Yes" : "No"}</p>
      </div>

      <div className="card table-wrap">
        <h3>Change History</h3>
        <table>
          <thead>
            <tr>
              <th>Revision</th>
              <th>Changed At</th>
            </tr>
          </thead>
          <tbody>
            {revisions.length === 0 ? (
              <tr>
                <td colSpan={2}>No revisions yet.</td>
              </tr>
            ) : (
              revisions.map((revision) => (
                <tr key={revision.id}>
                  <td>#{revision.revision_no}</td>
                  <td>{revision.changed_at}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

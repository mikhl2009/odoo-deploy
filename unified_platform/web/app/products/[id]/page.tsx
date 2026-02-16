import { apiGet } from "@/lib/api";
import { getDemoToken } from "@/lib/demo-auth";

type Product = {
  id: number;
  sku: string;
  ean: string | null;
  status: string;
  product_type: string;
  is_tobacco: boolean;
};

type Revision = {
  id: number;
  revision_no: number;
  changed_at: string;
};

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
      <h1 className="page-title">Product {product.sku}</h1>
      <p className="page-subtitle">
        Tabs baseline: General, Variants, Pricing, Compliance, Media, History.
      </p>

      <div className="card">
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

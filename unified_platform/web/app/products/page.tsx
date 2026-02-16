import Link from "next/link";

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

async function loadProducts(query?: string): Promise<Product[]> {
  const token = await getDemoToken();
  if (!token) {
    return [];
  }
  const path = query
    ? `/api/v1/products?sku=${encodeURIComponent(query)}`
    : "/api/v1/products";
  try {
    return await apiGet<Product[]>(path, token);
  } catch {
    return [];
  }
}

export default async function ProductsPage({
  searchParams
}: {
  searchParams: { q?: string };
}) {
  const products = await loadProducts(searchParams.q);
  return (
    <section>
      <h1 className="page-title">PIM Catalog</h1>
      <p className="page-subtitle">
        Central product source of truth with tobacco attributes, pricing and revision history.
      </p>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>SKU</th>
              <th>EAN</th>
              <th>Status</th>
              <th>Type</th>
              <th>Tobacco</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 ? (
              <tr>
                <td colSpan={6}>No products yet. Create products through `POST /api/v1/products`.</td>
              </tr>
            ) : (
              products.map((product) => (
                <tr key={product.id}>
                  <td>
                    <Link href={`/products/${product.id}`}>{product.id}</Link>
                  </td>
                  <td>{product.sku}</td>
                  <td>{product.ean || "-"}</td>
                  <td>
                    <span className="pill">{product.status}</span>
                  </td>
                  <td>{product.product_type}</td>
                  <td>{product.is_tobacco ? "Yes" : "No"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

import Link from "next/link";

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

function formatCurrency(value: string | number | null | undefined): string {
  if (value == null) return "-";
  return Number(value).toLocaleString("sv-SE", { style: "currency", currency: "SEK" });
}

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
              <th>Name</th>
              <th>Brand</th>
              <th>SKU</th>
              <th>EAN</th>
              <th>Price</th>
              <th>Variants</th>
              <th>Status</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 ? (
              <tr>
                <td colSpan={9}>No products yet. Run Woo import to populate catalog data.</td>
              </tr>
            ) : (
              products.map((product) => (
                <tr key={product.id}>
                  <td>
                    <Link href={`/products/${product.id}`}>{product.id}</Link>
                  </td>
                  <td>{product.name || product.sku}</td>
                  <td>{product.brand || "-"}</td>
                  <td>{product.sku}</td>
                  <td>{product.ean || "-"}</td>
                  <td>{formatCurrency(product.default_price)}</td>
                  <td>{product.variant_count}</td>
                  <td>
                    <span className="pill">{product.status}</span>
                  </td>
                  <td>{product.product_type}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

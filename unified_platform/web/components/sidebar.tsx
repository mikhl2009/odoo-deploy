"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/products", label: "PIM" },
  { href: "/inventory/stock", label: "Inventory" },
  { href: "/receiving", label: "Receiving" }
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">UE</div>
        <div>
          <p className="brand-title">Unified ERP</p>
          <p className="brand-subtitle">Tobacco Ops</p>
        </div>
      </div>
      <nav>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={pathname === item.href ? "nav-item active" : "nav-item"}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}

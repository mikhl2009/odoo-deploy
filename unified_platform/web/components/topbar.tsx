"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ThemeToggle } from "./theme-toggle";

export function Topbar() {
  const [q, setQ] = useState("");
  const router = useRouter();

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!q.trim()) {
      return;
    }
    router.push(`/products?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <header className="topbar">
      <form onSubmit={onSubmit} className="search-wrap">
        <input
          className="search-input"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Search products, lots, shipments..."
        />
      </form>
      <ThemeToggle />
    </header>
  );
}

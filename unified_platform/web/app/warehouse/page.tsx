"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PendingOrder {
    id: number;
    order_number: string;
    channel_type: string;
    status: string;
    line_count?: number;
    total: number;
}

interface ActivityEntry {
    order_id?: number;
    tracking: string;
    carrier?: string;
    packed_by?: string;
    printed_at?: string;
}

interface PrintState {
    status: "idle" | "printing" | "done" | "error";
    tracking?: string;
    shipment_id?: string;
    error?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function OrderQueue({
    orders,
    onSelect,
}: {
    orders: PendingOrder[];
    onSelect: (id: number) => void;
}) {
    if (!orders.length) {
        return (
            <p className="text-center text-gray-500 py-8">Inga väntande ordrar</p>
        );
    }
    return (
        <ul className="divide-y divide-gray-200">
            {orders.map((o) => (
                <li
                    key={o.id}
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 active:bg-gray-100"
                    onClick={() => onSelect(o.id)}
                >
                    <div>
                        <p className="font-semibold text-gray-800">{o.order_number}</p>
                        <p className="text-sm text-gray-500">
                            {o.channel_type.toUpperCase()} · {o.line_count ?? "?"} rader ·{" "}
                            {o.total.toLocaleString("sv-SE")} kr
                        </p>
                    </div>
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full">
                        {o.status}
                    </span>
                </li>
            ))}
        </ul>
    );
}

function QRScanner({
    onScan,
    disabled,
}: {
    onScan: (orderId: number) => void;
    disabled: boolean;
}) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [value, setValue] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const match = value.trim().match(/^OID:(\d+)$/);
        if (match) {
            onScan(parseInt(match[1], 10));
            setValue("");
        }
    };

    return (
        <form onSubmit={handleSubmit} className="flex gap-2 mt-4">
            <input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Skanna QR (OID:12345) eller ange manuellt"
                disabled={disabled}
                className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                autoFocus
            />
            <button
                type="submit"
                disabled={disabled || !value.trim()}
                className="bg-blue-600 text-white px-5 py-3 rounded-lg font-semibold disabled:opacity-50"
            >
                Skriv ut
            </button>
        </form>
    );
}

function PrintStatus({ state }: { state: PrintState }) {
    if (state.status === "idle") return null;

    if (state.status === "printing") {
        return (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700 text-center animate-pulse">
                Skriver ut…
            </div>
        );
    }

    if (state.status === "done") {
        return (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-center">
                <p className="text-lg font-bold">Etikett klar ✓</p>
                {state.tracking && (
                    <p className="text-sm mt-1">Tracking: {state.tracking}</p>
                )}
            </div>
        );
    }

    return (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-center">
            <p className="font-semibold">Fel vid utskrift</p>
            <p className="text-sm mt-1">{state.error}</p>
        </div>
    );
}

function ActivityLog({ entries }: { entries: ActivityEntry[] }) {
    if (!entries.length) return null;
    return (
        <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                Senaste utskrifter
            </h3>
            <ul className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                {entries.slice(0, 20).map((e, i) => (
                    <li key={i} className="flex items-center justify-between px-4 py-3 text-sm">
                        <span className="text-gray-700 font-medium">
                            Order {e.order_id ?? "—"}
                        </span>
                        <span className="text-gray-500">{e.tracking}</span>
                        <span className="text-gray-400 text-xs">
                            {e.packed_by ?? ""}
                        </span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function WarehousePage() {
    const [orders, setOrders] = useState<PendingOrder[]>([]);
    const [activity, setActivity] = useState<ActivityEntry[]>([]);
    const [printState, setPrintState] = useState<PrintState>({ status: "idle" });
    const [printerId] = useState(
        typeof window !== "undefined"
            ? (localStorage.getItem("nshift_printer_id") ?? "")
            : ""
    );
    const [packedBy] = useState(
        typeof window !== "undefined"
            ? (localStorage.getItem("packed_by") ?? "lagerarbetare")
            : "lagerarbetare"
    );

    const wsRef = useRef<WebSocket | null>(null);

    // Fetch pending orders
    const fetchOrders = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/sales/orders?status=confirmed&limit=50`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
            });
            if (res.ok) {
                const data = await res.json();
                setOrders(Array.isArray(data) ? data : data.orders ?? []);
            }
        } catch {
            // silent — WS refresh will retry
        }
    }, []);

    // Fetch activity log
    const fetchActivity = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/nshift/history`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
            });
            if (res.ok) {
                const data = await res.json();
                setActivity(Array.isArray(data) ? data : []);
            }
        } catch {
            // silent
        }
    }, []);

    // WebSocket
    useEffect(() => {
        const wsUrl =
            API_BASE.replace(/^http/, "ws") + "/api/v1/ws/warehouse";
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                if (msg.event === "label_printed") {
                    setPrintState({
                        status: "done",
                        tracking: msg.tracking,
                        shipment_id: msg.shipment_id,
                    });
                    setActivity((prev) => [
                        { order_id: msg.order_id, tracking: msg.tracking, packed_by: packedBy },
                        ...prev,
                    ]);
                    fetchOrders();
                } else if (msg.event === "order_ready") {
                    fetchOrders();
                }
            } catch {
                // ignore
            }
        };

        ws.onerror = () => ws.close();
        ws.onclose = () => {
            // Attempt reconnect after 5s
            setTimeout(() => {
                if (wsRef.current === ws) wsRef.current = null;
            }, 5000);
        };

        return () => ws.close();
    }, [packedBy, fetchOrders]);

    useEffect(() => {
        fetchOrders();
        fetchActivity();
    }, [fetchOrders, fetchActivity]);

    // Print handler — called from QRScanner or OrderQueue click
    const handlePrint = useCallback(
        async (orderId: number) => {
            setPrintState({ status: "printing" });
            try {
                const res = await fetch(`${API_BASE}/api/v1/nshift/ship/${orderId}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
                    },
                    body: JSON.stringify({ printer_id: printerId, packed_by: packedBy }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail ?? "Okänt fel");
                setPrintState({
                    status: "done",
                    tracking: data.tracking_number,
                    shipment_id: data.shipment_id,
                });
                setActivity((prev) => [
                    {
                        order_id: orderId,
                        tracking: data.tracking_number ?? "",
                        packed_by: packedBy,
                    },
                    ...prev,
                ]);
                fetchOrders();
            } catch (err: unknown) {
                setPrintState({
                    status: "error",
                    error: err instanceof Error ? err.message : String(err),
                });
            }
        },
        [printerId, packedBy, fetchOrders]
    );

    // Auto-clear done/error status after 6 seconds
    useEffect(() => {
        if (printState.status === "done" || printState.status === "error") {
            const t = setTimeout(() => setPrintState({ status: "idle" }), 6000);
            return () => clearTimeout(t);
        }
    }, [printState.status]);

    return (
        <div className="min-h-screen bg-gray-50 p-4 max-w-lg mx-auto">
            <header className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Lagerportal</h1>
                <p className="text-sm text-gray-500">Snushallen i Norden AB</p>
            </header>

            <section className="bg-white rounded-xl shadow-sm p-4">
                <h2 className="font-semibold text-gray-700 mb-2">
                    Väntande ordrar ({orders.length})
                </h2>
                <OrderQueue orders={orders} onSelect={handlePrint} />
            </section>

            <section className="bg-white rounded-xl shadow-sm p-4 mt-4">
                <h2 className="font-semibold text-gray-700 mb-1">Skanna etikett</h2>
                <QRScanner
                    onScan={handlePrint}
                    disabled={printState.status === "printing"}
                />
                <PrintStatus state={printState} />
            </section>

            <ActivityLog entries={activity} />
        </div>
    );
}

"use client";

import { useEffect, useState } from "react";

type WSStatusProps = {
  path: string;
};

export function WSStatus({ path }: WSStatusProps) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8080";
    const wsBase = base.replace("http://", "ws://").replace("https://", "wss://");
    const socket = new WebSocket(`${wsBase}${path}`);

    socket.onopen = () => {
      setConnected(true);
      socket.send("ping");
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    return () => socket.close();
  }, [path]);

  return (
    <span className={connected ? "ws connected" : "ws disconnected"}>
      {connected ? "Live" : "Offline"}
    </span>
  );
}

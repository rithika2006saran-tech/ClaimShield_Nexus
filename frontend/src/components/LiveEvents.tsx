import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

export function LiveEvents() {
  const [eventMsg, setEventMsg] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.port === "5173" ? "localhost:8000" : window.location.host;
      ws = new WebSocket(`${protocol}//${host}/api/ws`);
      
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "review_submitted") {
            setEventMsg(`Case ${data.case_id} status changed to ${data.status}`);
          } else if (data.type === "weights_updated") {
            setEventMsg(`Prioritization weights were updated globally`);
          }
          // Clear message after 5 seconds
          setTimeout(() => setEventMsg(null), 5000);
        } catch (err) {}
      };

      ws.onclose = () => {
        setTimeout(connect, 3000); // reconnect on drop
      };
    };
    
    connect();
    return () => ws?.close();
  }, []);

  if (!eventMsg) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md shadow-lg animate-in slide-in-from-bottom-5">
      <Activity className="h-4 w-4 animate-pulse" />
      <span className="text-sm font-medium">{eventMsg}</span>
    </div>
  );
}

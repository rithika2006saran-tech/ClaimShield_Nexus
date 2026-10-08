import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Search, Loader2 } from "lucide-react";
import { post } from "@/lib/api";

export function GlobalSearch() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ cases: any[]; entities: any[] }>({ cases: [], entities: [] });
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults({ cases: [], entities: [] });
      setOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const [casesRes, entitiesRes] = await Promise.all([
          post("/brain/search", { query: q, index: "cases", mode: "hybrid", size: 4 }),
          post("/brain/search", { query: q, index: "entities", mode: "hybrid", size: 3 })
        ]);
        setResults({ cases: casesRes.hits || [], entities: entitiesRes.hits || [] });
        setOpen(true);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div ref={wrapperRef} className="relative flex-1 max-w-xl mx-4 my-2 z-50">
      <div className="relative flex items-center">
        <Search className="absolute left-2.5 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Global Search (Elasticsearch) - find cases, providers..."
          className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => { if (q.length >= 2) setOpen(true); }}
        />
        {loading && <Loader2 className="absolute right-2.5 h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {open && (results.cases.length > 0 || results.entities.length > 0) && (
        <div className="absolute top-full mt-1 w-full rounded-md border border-border bg-card p-2 shadow-lg">
          {results.entities.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 text-xs font-semibold text-muted-foreground uppercase px-2">Providers</div>
              {results.entities.map((h: any) => (
                <Link key={h.id} to={`/provider/${h.id}`} onClick={() => setOpen(false)} className="block rounded-md px-2 py-1.5 hover:bg-accent text-sm">
                  <span className="font-semibold text-sky-400">{h.id}</span>
                  <span className="ml-2 text-muted-foreground">{h.doc.name || h.doc.specialty}</span>
                </Link>
              ))}
            </div>
          )}
          {results.cases.length > 0 && (
            <div>
              <div className="mb-1 text-xs font-semibold text-muted-foreground uppercase px-2">Cases</div>
              {results.cases.map((h: any) => (
                <Link key={h.id} to={`/case/${h.id}`} onClick={() => setOpen(false)} className="block rounded-md px-2 py-1.5 hover:bg-accent text-sm">
                  <span className="font-semibold text-sky-400">{h.id}</span>
                  <div className="text-xs text-muted-foreground truncate">{h.doc.summary?.slice(0, 80) || h.doc.specialty}...</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

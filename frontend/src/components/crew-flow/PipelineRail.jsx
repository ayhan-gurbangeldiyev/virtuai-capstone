import {
  Radar, Compass, Pencil, ShieldCheck, Image, Video, Send, AlertTriangle,
  Clock, Type,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* Pipeline rail — haber 7-node VEYA kart 4-node, n8n dokunuşlu CSS-only canvas.
   Port noktaları + connector renkleri index.css `.crew-*` sınıflarında. */

const NODE_ICONS = {
  // haber pipeline
  trend_scout: Radar,
  strategist: Compass,
  writer: Pencil,
  gate: ShieldCheck,
  visual: Image,
  video: Video,
  publish: Send,
  // SÖZLÜK/SENCE? kart pipeline
  saat: Clock,
  icerik: Type,
  card_gate: ShieldCheck,
  render: Image,
};

const PORT_COLORS = {
  success: "rgba(52,211,153,.55)",
  failed: "rgba(244,63,94,.6)",
  skipped: "#2c2c33",
  running: "rgba(168,85,247,.7)",
  pending: "#3f3f46",
};

function fmtDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return "—";
  const sec = Math.round(n / 1000);
  if (sec < 60) return `${sec} sn`;
  return `${Math.floor(sec / 60)} dk ${sec % 60} sn`;
}

function nodeBorder(state, isSelected) {
  if (isSelected) return "border-purple-500/90 ring-[3px] ring-purple-500/15 scale-[1.04]";
  switch (state) {
    case "success": return "border-emerald-400/45";
    case "failed": return "border-rose-500/55";
    case "skipped": return "border-dashed border-[#2c2c33] opacity-55";
    case "running": return "border-purple-500";
    default: return "border-zinc-600/60";
  }
}

function nodeIconColor(state) {
  switch (state) {
    case "success": return "text-emerald-400";
    case "failed": return "text-rose-400";
    case "running": return "text-purple-400";
    case "skipped": return "text-zinc-500";
    default: return "text-zinc-500";
  }
}

function connClass(nextState) {
  switch (nextState) {
    case "success": return "crew-conn crew-conn--success";
    case "skipped": return "crew-conn crew-conn--skipped";
    case "running": return "crew-conn crew-conn--running";
    case "failed": return "crew-conn crew-conn--failed";
    default: return "crew-conn";
  }
}

function nodeSubline(node) {
  if (node?.state === "skipped") return "atlandı";
  if (node?.key === "publish" && node?.publish) {
    const p = node.publish;
    return `${p.published_count ?? 0}/${p.total_count ?? 0} ${p.state_label || ""}`.trim();
  }
  if (node?.state === "pending") return "bekliyor";
  return fmtDuration(node?.derived_duration_ms);
}

export default function PipelineRail({ nodes, selectedKey, onSelect, trust }) {
  const list = Array.isArray(nodes) ? nodes : [];
  if (list.length === 0) {
    return (
      <div className="crew-canvas rounded-2xl bg-card/80 border border-border/40 p-6 text-xs text-muted-foreground">
        Pipeline verisi yok.
      </div>
    );
  }
  return (
    <div className="crew-canvas rounded-2xl bg-card/80 border border-border/40 px-5 py-5 overflow-x-auto">
      <div className="flex flex-row items-stretch min-w-max">
        {list.map((node, i) => {
          const Icon = NODE_ICONS[node?.key] || Radar;
          const isSelected = node?.key === selectedKey;
          const showWriterWarn = node?.key === "writer" && !!trust?.opening_similarity;
          return (
            <div key={node?.key || i} className="flex flex-row items-stretch">
              {i > 0 && <div className={connClass(node?.state)} />}
              <button
                type="button"
                onClick={() => onSelect?.(node?.key)}
                style={{ "--crew-port": PORT_COLORS[node?.state] || PORT_COLORS.pending }}
                className={cn(
                  "crew-node bg-[#141318] border-2 rounded-[10px] text-center px-1 py-2 relative cursor-pointer transition min-w-[88px]",
                  i === 0 && "crew-node--first",
                  i === list.length - 1 && "crew-node--last",
                  node?.state === "running" && "crew-pulse",
                  nodeBorder(node?.state, isSelected),
                  !isSelected && "hover:-translate-y-px hover:border-purple-500/50"
                )}
              >
                {showWriterWarn && (
                  <span className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-amber-500/20 border border-amber-500/50 flex items-center justify-center">
                    <AlertTriangle className="h-2.5 w-2.5 text-amber-400" />
                  </span>
                )}
                <Icon className={cn("h-4 w-4 mx-auto", nodeIconColor(node?.state))} />
                <p className="text-[10px] text-foreground/85 mt-1 leading-tight">
                  {node?.label || node?.key || "—"}
                </p>
                <p className="text-[8px] font-mono text-muted-foreground mt-0.5">
                  {nodeSubline(node)}
                </p>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

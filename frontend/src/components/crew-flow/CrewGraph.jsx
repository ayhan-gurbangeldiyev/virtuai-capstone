import { useMemo, useCallback } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position, BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import {
  Radar, Compass, Pencil, ShieldCheck, Image as ImageIcon, Video, Send,
  Clock, Type, Hash,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* Crew Akışı — n8n-tarzı node-graph (react-flow). Düz "ray" yerine crew'in postu
   hazırlarken izlediği gerçek akış: node kartları + renkli kenarlar + dallanma
   (publish → platform fan-out), dot-grid arka plan + minimap. Read-only: sürükleme
   yok, sadece pan/zoom + node tıkla→DetailPanel. */

const NODE_ICONS = {
  trend_scout: Radar, strategist: Compass, writer: Pencil, gate: ShieldCheck,
  visual: ImageIcon, video: Video, publish: Send,
  saat: Clock, icerik: Type, card_gate: ShieldCheck, render: ImageIcon,
  platform: Hash, empty: Radar,
};
const STATE_COLOR = {
  success: "#34d399", failed: "#f43f5e", running: "#a855f7",
  skipped: "#52525b", pending: "#3f3f46",
};

function fmtDur(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return "";
  const s = Math.round(n / 1000);
  return s < 60 ? `${s} sn` : `${Math.floor(s / 60)} dk ${s % 60} sn`;
}

function platState(d) {
  const ps = d?.postiz_state;
  if (ps === "PUBLISHED") return "success";
  if (ps === "ERROR") return "failed";
  if (ps || ["approved", "auto_scheduled"].includes(d?.status)) return "success";
  if (["pending", "pending_review"].includes(d?.status)) return "running";
  return "pending";
}

function sublineFor(node) {
  if (node?.state === "skipped") return "atlandı";
  if (node?.state === "pending") return "bekliyor";
  if (node?.key === "publish" && node?.publish) {
    const p = node.publish;
    return `${p.published_count ?? 0}/${p.total_count ?? 0} ${p.state_label || ""}`.trim();
  }
  return fmtDur(node?.derived_duration_ms) || node?.state || "";
}

/* Custom node — ikon + başlık + alt-bilgi/süre, durum rengi kenar. */
function N8nNode({ data, selected }) {
  const Icon = NODE_ICONS[data.iconKey] || Radar;
  const col = STATE_COLOR[data.state] || STATE_COLOR.pending;
  return (
    <div
      className={cn("crew-rf-node", selected && "crew-rf-node--sel", data.state === "running" && "crew-pulse")}
      style={{ borderColor: selected ? "#a855f7" : col }}
    >
      <Handle type="target" position={Position.Left} className="crew-rf-handle" />
      <div className="crew-rf-head">
        <Icon size={14} style={{ color: col }} />
        <span className="crew-rf-title">{data.label}</span>
      </div>
      <div className="crew-rf-sub">{data.sub}</div>
      <Handle type="source" position={Position.Right} className="crew-rf-handle" />
    </div>
  );
}
const nodeTypes = { n8n: N8nNode };

const NODE_W = 156;
const NODE_H = 56;

function layout(nodes, edges) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 26, ranksep: 64, marginx: 16, marginy: 16 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } };
  });
}

/* flow yanıtını react-flow nodes+edges'e çevir. */
function buildGraph(nodes, drafts, run) {
  const list = Array.isArray(nodes) ? nodes : [];
  const rf = [];
  const edges = [];

  // Boş run (aday yok) → tek "Aday Yok" node'u + neden.
  const isEmptyNews = run?.run_kind !== "cards"
    && list.every((n) => n?.state === "skipped" || n?.state === "pending")
    && (!Array.isArray(drafts) || drafts.length === 0);
  if (isEmptyNews && (run?.gate_breakdown || run?.reason)) {
    rf.push({
      id: "empty", type: "n8n", draggable: false,
      data: { iconKey: "empty", key: "empty", label: "Aday Yok",
              state: "skipped", sub: run?.reason || "taze AI haberi yok" },
      position: { x: 0, y: 0 },
    });
    return { nodes: rf, edges };
  }

  list.forEach((node, i) => {
    rf.push({
      id: node.key, type: "n8n", draggable: false,
      data: { iconKey: node.key, key: node.key, label: node.label || node.key,
              state: node.state, sub: sublineFor(node) },
      position: { x: 0, y: 0 },
    });
    if (i > 0) {
      const prev = list[i - 1];
      const skipped = node.state === "skipped";
      edges.push({
        id: `${prev.key}-${node.key}`, source: prev.key, target: node.key,
        animated: node.state === "running",
        label: skipped ? "atlandı" : undefined,
        style: { stroke: STATE_COLOR[node.state] || "#3f3f46", strokeWidth: 2,
                 strokeDasharray: skipped ? "5 4" : undefined },
        labelStyle: { fill: "#a1a1aa", fontSize: 9 },
      });
    }
  });

  // publish → platform fan-out (gerçek dallanma)
  const hasPublish = list.some((n) => n.key === "publish");
  if (hasPublish && Array.isArray(drafts) && drafts.length) {
    drafts.forEach((d) => {
      const st = platState(d);
      const pid = `pf_${d.platform}_${d.id}`;
      rf.push({
        id: pid, type: "n8n", draggable: false,
        data: { iconKey: "platform", key: "platform", label: d.platform,
                state: st, sub: d.postiz_state || d.status || "" },
        position: { x: 0, y: 0 },
      });
      edges.push({
        id: `pub-${pid}`, source: "publish", target: pid,
        style: { stroke: STATE_COLOR[st] || "#3f3f46", strokeWidth: 2 },
      });
    });
  }
  return { nodes: layout(rf, edges), edges };
}

export default function CrewGraph({ nodes, drafts, run, selectedKey, onSelect }) {
  const { nodes: rfNodes, edges } = useMemo(
    () => buildGraph(nodes, drafts, run),
    [nodes, drafts, run]
  );
  const styledNodes = useMemo(
    () => rfNodes.map((n) => ({ ...n, selected: n.id === selectedKey })),
    [rfNodes, selectedKey]
  );
  const onNodeClick = useCallback((_e, node) => {
    // platform fan-out node'ları seçilince publish detayını göster
    onSelect?.(node?.id?.startsWith("pf_") ? "publish" : node?.id);
  }, [onSelect]);

  if (!rfNodes.length) {
    return (
      <div className="crew-canvas rounded-2xl bg-card/80 border border-border/40 p-6 text-xs text-muted-foreground">
        Pipeline verisi yok.
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-border/40 overflow-hidden" style={{ height: 340 }}>
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesReconnectable={false}
        elementsSelectable
        fitView
        fitViewOptions={{ padding: 0.18 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={1.6}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#2a2a31" />
        <MiniMap pannable zoomable
                 nodeColor={(n) => STATE_COLOR[n.data?.state] || "#52525b"}
                 nodeStrokeColor={(n) => STATE_COLOR[n.data?.state] || "#52525b"}
                 nodeStrokeWidth={3} nodeBorderRadius={3}
                 maskColor="rgba(20,19,24,.35)"
                 style={{ background: "#141318", width: 132, height: 88 }} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronRight, ChevronDown, Dna, GitBranch } from "lucide-react";
import { cn } from "@/lib/utils";

export default function EvolveTree({ chain, onNodeClick, activeId }) {
  const { t } = useTranslation();
  
  const buildTree = (items) => {
    const map = {};
    const roots = [];
    items.forEach(item => { map[item.id] = { ...item, children: [] }; });
    items.forEach(item => {
      if (item.parent_generation_id && map[item.parent_generation_id]) {
        map[item.parent_generation_id].children.push(map[item.id]);
      } else {
        roots.push(map[item.id]);
      }
    });
    return roots;
  };
  
  const tree = buildTree(chain || []);
  
  const TreeNode = ({ node, depth = 0 }) => {
    const [expanded, setExpanded] = useState(true);
    const hasChildren = node.children.length > 0;
    const isActive = node.id === activeId;
    
    return (
      <div>
        <button
          onClick={() => onNodeClick?.(node.id)}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all text-sm",
            isActive 
              ? "bg-violet-500/20 text-violet-300 border border-violet-500/30" 
              : "text-white/60 hover:text-white/80 hover:bg-white/5"
          )}
          style={{ paddingLeft: `${depth * 20 + 12}px` }}
        >
          {hasChildren && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
              className="shrink-0"
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
          )}
          {!hasChildren && <span className="w-3" />}
          
          {depth === 0 ? (
            <GitBranch className="w-3.5 h-3.5 text-white/40 shrink-0" />
          ) : (
            <Dna className="w-3.5 h-3.5 text-violet-400 shrink-0" />
          )}
          
          <span className="truncate flex-1">
            {depth === 0 ? (node.topic?.substring(0, 40) || t('evolve.original')) : t('evolve.round', { round: node.evolution_depth })}
          </span>
          
          {node.children.length > 0 && (
            <span className="text-[10px] text-white/30 shrink-0">
              {node.children.length} dal
            </span>
          )}
        </button>
        
        {expanded && hasChildren && (
          <div className="relative">
            <div className="absolute left-[22px] top-0 bottom-0 w-px bg-white/10" style={{ marginLeft: `${depth * 20}px` }} />
            {node.children.map(child => (
              <TreeNode key={child.id} node={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };
  
  if (!chain || chain.length === 0) return null;
  
  return (
    <div className="space-y-0.5">
      {tree.map(root => (
        <TreeNode key={root.id} node={root} />
      ))}
    </div>
  );
}

"use client";

import React, { useEffect, useRef, useState } from "react";

export interface GraphNode {
  id: string;
  label: string;
  type: "decision" | "person" | "date" | "source" | "outcome";
  info?: string;
  icon?: string;
}

interface PhysicsNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface DecisionGraphProps {
  nodes: GraphNode[];
  decisionTitle: string;
  className?: string;
}

export default function DecisionGraph({
  nodes,
  decisionTitle,
  className = "",
}: DecisionGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // States
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<number>(0.95);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);

  // Physics Simulation Coordinates
  const physicsNodesRef = useRef<PhysicsNode[]>([]);
  const activeDragIdRef = useRef<string | null>(null);
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [renderTrigger, setRenderTrigger] = useState(0);

  // Synchronize incoming nodes to physics simulator
  useEffect(() => {
    if (nodes.length === 0) {
      physicsNodesRef.current = [];
      return;
    }

    const width = containerRef.current?.clientWidth || 400;
    const height = containerRef.current?.clientHeight || 350;
    const cx = width / 2;
    const cy = height / 2;

    const centerNode = nodes.find((n) => n.type === "decision") || nodes[0];

    physicsNodesRef.current = nodes.map((node) => {
      const existing = physicsNodesRef.current.find((n) => n.id === node.id);
      if (existing) {
        return { ...node, x: existing.x, y: existing.y, vx: existing.vx, vy: existing.vy };
      }

      if (node.id === centerNode.id) {
        return { ...node, x: cx, y: cy, vx: 0, vy: 0 };
      } else {
        const angle = Math.random() * 2 * Math.PI;
        const dist = 80 + Math.random() * 40;
        return {
          ...node,
          x: cx + Math.cos(angle) * dist,
          y: cy + Math.sin(angle) * dist,
          vx: 0,
          vy: 0,
        };
      }
    });
  }, [nodes]);

  // Main physics loop (Coulomb repulsion + Hooke spring attraction)
  useEffect(() => {
    let animFrame: number;

    const runFrame = () => {
      const pNodes = physicsNodesRef.current;
      if (pNodes.length === 0) {
        animFrame = requestAnimationFrame(runFrame);
        return;
      }

      const width = containerRef.current?.clientWidth || 400;
      const height = containerRef.current?.clientHeight || 350;
      const cx = width / 2;
      const cy = height / 2;

      const repelConstant = 1500;
      const springConstant = 0.04;
      const springLength = 110;
      const centerPull = 0.008;
      const friction = 0.85;

      const centerNode = pNodes.find((n) => n.type === "decision") || pNodes[0];

      // 1. Coulomb repulsion
      for (let i = 0; i < pNodes.length; i++) {
        for (let j = i + 1; j < pNodes.length; j++) {
          const n1 = pNodes[i];
          const n2 = pNodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;

          if (dist < 200) {
            const force = repelConstant / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            n1.vx -= fx;
            n1.vy -= fy;
            n2.vx += fx;
            n2.vy += fy;
          }
        }
      }

      // 2. Spring connection attraction
      pNodes.forEach((node) => {
        if (node.id === centerNode.id) return;
        const dx = node.x - centerNode.x;
        const dy = node.y - centerNode.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        const delta = dist - springLength;
        const force = delta * springConstant;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        node.vx -= fx;
        node.vy -= fy;
        centerNode.vx += fx;
        centerNode.vy += fy;
      });

      // 3. Gravity center pull
      pNodes.forEach((node) => {
        const dx = cx - node.x;
        const dy = cy - node.y;
        node.vx += dx * centerPull;
        node.vy += dy * centerPull;
      });

      // 4. Update coordinates
      pNodes.forEach((node) => {
        if (node.id === activeDragIdRef.current) {
          node.vx = 0;
          node.vy = 0;
          return;
        }

        node.x += node.vx;
        node.y += node.vy;
        node.vx *= friction;
        node.vy *= friction;

        // Keep inside canvas bounds
        node.x = Math.max(30, Math.min(width - 30, node.x));
        node.y = Math.max(30, Math.min(height - 30, node.y));
      });

      setRenderTrigger((prev) => prev + 1);
      animFrame = requestAnimationFrame(runFrame);
    };

    animFrame = requestAnimationFrame(runFrame);
    return () => cancelAnimationFrame(animFrame);
  }, []);

  // Mouse wheel Zoom handler
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = 0.05;
    const direction = e.deltaY < 0 ? 1 : -1;
    setZoom((prev) => Math.max(0.4, Math.min(2.0, prev + direction * zoomFactor)));
  };

  // Background Drag Pan handler
  const handleMouseDown = (e: React.MouseEvent) => {
    const isNode = (e.target as HTMLElement).closest(".physics-node");
    if (!isNode && containerRef.current) {
      setIsPanning(true);
      panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStartRef.current.x,
        y: e.clientY - panStartRef.current.y,
      });
    } else if (activeDragIdRef.current && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      // Adjust mouse coordinate relative to active zoom and pan
      const mouseX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseY = (e.clientY - rect.top - pan.y) / zoom;

      const dragNode = physicsNodesRef.current.find((n) => n.id === activeDragIdRef.current);
      if (dragNode) {
        dragNode.x = mouseX;
        dragNode.y = mouseY;
      }
    }
  };

  const handleMouseUpOrLeave = () => {
    activeDragIdRef.current = null;
    setIsPanning(false);
  };

  const resetViewport = () => {
    setZoom(0.95);
    setPan({ x: 0, y: 0 });
  };

  const pNodes = physicsNodesRef.current;
  const centerNode = pNodes.find((n) => n.type === "decision") || pNodes[0];
  const satelliteNodes = pNodes.filter((n) => n.id !== centerNode?.id);

  // Active hover/selection ID
  const activeFocusId = selectedNodeId || hoveredNodeId;

  // Node connection masking helper (for fade/dimming unconnected links)
  const isNodeConnected = (nodeId: string) => {
    if (!activeFocusId) return true;
    if (nodeId === activeFocusId) return true;
    if (activeFocusId === centerNode?.id) return true; // center connects to all
    if (nodeId === centerNode?.id) return true; // center connects to active
    return false;
  };

  // Classy type color coding
  const getNodeColor = (type: GraphNode["type"]) => {
    switch (type) {
      case "decision": return "bg-indigo-600 border-indigo-400 text-indigo-100";
      case "person": return "bg-emerald-600/90 border-emerald-400 text-emerald-100";
      case "source": return "bg-cyan-600/90 border-cyan-400 text-cyan-100";
      case "date": return "bg-amber-600/90 border-amber-400 text-amber-100";
      case "outcome": return "bg-rose-600/90 border-rose-400 text-rose-100";
      default: return "bg-zinc-600 border-zinc-400 text-zinc-100";
    }
  };

  const activeNodeInfo = nodes.find((n) => n.id === activeFocusId);

  return (
    <div
      ref={containerRef}
      className={`flex flex-col h-full bg-[var(--bg)] border border-[var(--border)] rounded-xl select-none relative overflow-hidden theme-transition ${className}`}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUpOrLeave}
      onMouseLeave={handleMouseUpOrLeave}
    >
      {/* Top Header Controls */}
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between shrink-0 bg-[var(--surface)] theme-transition z-20">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-[var(--accent)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
          </svg>
          <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--text-primary)] font-mono">Memory decision graph</span>
        </div>
        <button
          onClick={resetViewport}
          className="text-[9px] font-mono px-2 py-0.5 border border-[var(--border)] hover:bg-[var(--surface-hover)] rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all"
        >
          RESET
        </button>
      </div>

      {/* Physics Graph Area */}
      <div className="flex-1 relative bg-[var(--bg)] theme-transition min-h-[300px]">
        {/* Transform Group */}
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
          className="absolute inset-0 origin-center"
        >
          {/* SVG Spring Connectors */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
            {centerNode &&
              satelliteNodes.map((node) => {
                const isHovered = hoveredNodeId === node.id || hoveredNodeId === centerNode.id;
                const isSelected = selectedNodeId === node.id || selectedNodeId === centerNode.id;
                const isActive = isHovered || isSelected;
                const pathId = `path-${node.id}`;

                // Calculate connection opacity based on focus masking
                const isMasked = activeFocusId !== null && !isNodeConnected(node.id);
                const strokeOpacity = isMasked ? 0.04 : isActive ? 0.7 : 0.25;

                return (
                  <g key={node.id} className="transition-opacity duration-300" style={{ opacity: strokeOpacity }}>
                    {/* SVG Path used for particle animateMotion */}
                    <path
                      id={pathId}
                      d={`M ${node.x} ${node.y} L ${centerNode.x} ${centerNode.y}`}
                      stroke={isActive ? "var(--accent)" : "var(--text-muted)"}
                      strokeWidth={isActive ? "1.5" : "0.75"}
                      strokeDasharray={node.type === "outcome" ? "3 3" : "none"}
                      fill="none"
                    />

                    {/* Classy Flow Particle moving along spring lines */}
                    {!isMasked && (
                      <circle r="1.5" fill="var(--accent)">
                        <animateMotion dur="2.5s" repeatCount="indefinite">
                          <mpath href={`#${pathId}`} />
                        </animateMotion>
                      </circle>
                    )}
                  </g>
                );
              })}
          </svg>

          {/* Absolute physics nodes */}
          <div className="absolute inset-0 z-10 pointer-events-none">
            {pNodes.map((node) => {
              const isCenter = node.type === "decision";
              const isHovered = hoveredNodeId === node.id;
              const isSelected = selectedNodeId === node.id;
              
              // Fade out unconnected nodes when another node is hovered/selected
              const isDimmed = activeFocusId !== null && !isNodeConnected(node.id);
              const themeColorClass = getNodeColor(node.type);

              return (
                <div
                  key={node.id}
                  className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-grab active:cursor-grabbing flex items-center justify-center physics-node"
                  style={{
                    left: node.x,
                    top: node.y,
                    transform: `translate(-50%, -50%) scale(${isHovered || isSelected ? 1.15 : 1})`,
                    opacity: isDimmed ? 0.2 : 1,
                    transition: "opacity 0.3s ease",
                  }}
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    activeDragIdRef.current = node.id;
                  }}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedNodeId(selectedNodeId === node.id ? null : node.id);
                  }}
                >
                  {/* Clean dot badge */}
                  <div
                    className={`flex items-center justify-center rounded-full transition-all border ${
                      isCenter
                        ? "w-8 h-8 ring-2 ring-indigo-500/20"
                        : "w-4 h-4"
                    } ${themeColorClass} shadow-md`}
                  >
                    <span className="text-[10px] font-bold">
                      {node.icon || node.label.charAt(0)}
                    </span>
                  </div>

                  {/* Clean Floating Obsidian Tooltip label */}
                  {(isHovered || isSelected) && (
                    <div className="absolute top-7 bg-[var(--surface)] border border-[var(--border)] text-[9px] font-mono text-[var(--text-primary)] px-2 py-0.5 rounded shadow-lg whitespace-nowrap z-30 theme-transition">
                      {node.label}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Info Context Drawer */}
      <div className="p-4 border-t border-[var(--border)] bg-[var(--surface)] text-[11px] leading-relaxed z-20 theme-transition">
        {activeNodeInfo ? (
          <div>
            <span className="font-mono text-[var(--text-muted)] uppercase text-[9px] tracking-wider block mb-0.5">
              {activeNodeInfo.type} Context
            </span>
            <span className="font-bold text-[var(--text-primary)] block text-xs">{activeNodeInfo.label}</span>
            <p className="text-[var(--text-muted)] mt-1">{activeNodeInfo.info || "No context mappings present."}</p>
          </div>
        ) : (
          <div className="flex items-center justify-between text-[9px] font-mono text-[var(--text-muted)] uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-indigo-500 animate-pulse" />
              Scroll to zoom • drag empty space to pan
            </span>
            <span className="text-[8px] border border-[var(--border)] px-1 rounded">
              ZOOM: {Math.round(zoom * 100)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

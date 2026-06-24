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

function getNodeIconSVG(node: GraphNode) {
  const label = (node.label || "").toLowerCase();
  const type = node.type;
  const icon = (node.icon || "").toLowerCase();
  const info = (node.info || "").toLowerCase();

  // 1. React
  if (label.includes("react") || icon.includes("⚛️")) {
    return (
      <svg viewBox="0 0 24 24" className="w-6 h-6 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(0)" />
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(60)" />
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(120)" />
        <circle cx="12" cy="12" r="2" fill="currentColor" />
      </svg>
    );
  }

  // 2. Vue
  if (label.includes("vue") || icon.includes("💚")) {
    return (
      <svg viewBox="0 0 24 24" className="w-6 h-6 transition-transform hover:scale-110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 22L24 1.5H18.5L12 13L5.5 1.5H0L12 22Z" fill="#41B883" />
        <path d="M12 13L18.5 1.5H14L12 5L10 1.5H5.5L12 13Z" fill="#35495E" />
      </svg>
    );
  }

  // 3. Slack
  if (label.includes("slack") || icon.includes("💬") || icon.includes("slack")) {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5 transition-transform hover:scale-110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="6" cy="6" r="2" fill="#36C5F0" />
        <rect x="4" y="9" width="4" height="8" rx="2" fill="#36C5F0" />
        <circle cx="18" cy="6" r="2" fill="#2EB67D" />
        <rect x="9" y="4" width="8" height="4" rx="2" fill="#2EB67D" />
        <circle cx="18" cy="18" r="2" fill="#ECB22E" />
        <rect x="16" y="7" width="4" height="8" rx="2" fill="#ECB22E" />
        <circle cx="6" cy="18" r="2" fill="#E01E5A" />
        <rect x="7" y="16" width="8" height="4" rx="2" fill="#E01E5A" />
      </svg>
    );
  }

  // 4. Google Drive
  if (label.includes("drive") || label.includes("google drive") || icon.includes("📄") || info.includes("drive") || info.includes("workspace")) {
    return (
      <svg viewBox="0 0 100 100" className="w-5 h-5 transition-transform hover:scale-110">
        <path d="M 33 20 L 2 73.6 L 17 100 L 48 46.4 Z" fill="#FFD043" />
        <path d="M 48 46.4 L 17 100 L 83 100 L 98 73.6 Z" fill="#1EA758" />
        <path d="M 33 20 L 48 46.4 L 98 73.6 L 67 20 Z" fill="#167EE6" />
      </svg>
    );
  }

  // 5. Jira
  if (label.includes("jira") || icon.includes("🔧") || info.includes("jira")) {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5 transition-transform hover:scale-110" fill="currentColor">
        <path d="M12.5 13.5l4.5-4.5 4.5 4.5-4.5 4.5z" fill="#0052CC" />
        <path d="M4.5 13.5l4.5-4.5 4.5 4.5-4.5 4.5z" fill="#0052CC" opacity="0.8" />
        <path d="M8.5 5.5l4.5-4.5 4.5 4.5-4.5 4.5z" fill="#0052CC" opacity="0.6" />
      </svg>
    );
  }

  // 6. Gmail / Email
  if (label.includes("gmail") || label.includes("email") || label.includes("mail") || icon.includes("✉️") || icon.includes("envelope")) {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
        <polyline points="22,6 12,13 2,6" />
      </svg>
    );
  }

  // 7. Calendar / Date
  if (type === "date" || icon.includes("📅") || label.includes("calendar") || label.includes("date")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    );
  }

  // 8. Person
  if (type === "person" || icon.includes("👤") || icon.includes("👥")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    );
  }

  // 9. Outcome
  if (type === "outcome") {
    const isSuccess = icon.includes("✅") || icon.includes("success") || label.toLowerCase().includes("scale") || label.toLowerCase().includes("hire") || label.toLowerCase().includes("hiring") || label.toLowerCase().includes("success");
    const isError = icon.includes("❌") || icon.includes("error") || label.toLowerCase().includes("write-off") || label.toLowerCase().includes("fail") || label.toLowerCase().includes("failed") || label.toLowerCase().includes("terminate");

    if (isSuccess) {
      return (
        <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    }
    if (isError) {
      return (
        <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      );
    }
    // Warning by default
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    );
  }

  // Fallback to text icon or first character
  return <span className="text-[10px] font-bold select-none">{node.icon || node.label.charAt(0)}</span>;
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

  // Classy type color coding (Glassmorphism inspired translucent styling)
  const getNodeColor = (type: GraphNode["type"]) => {
    switch (type) {
      case "decision": return "bg-indigo-500/10 border-indigo-500/40 text-indigo-500 dark:text-indigo-400";
      case "person": return "bg-emerald-500/10 border-emerald-500/40 text-emerald-500 dark:text-emerald-400";
      case "source": return "bg-cyan-500/10 border-cyan-500/40 text-cyan-500 dark:text-cyan-400";
      case "date": return "bg-amber-500/10 border-amber-500/40 text-amber-500 dark:text-amber-400";
      case "outcome": return "bg-rose-500/10 border-rose-500/40 text-rose-500 dark:text-rose-400";
      default: return "bg-zinc-500/10 border-zinc-500/40 text-zinc-500 dark:text-zinc-400";
    }
  };

  const activeNodeInfo = nodes.find((n) => n.id === activeFocusId);

  return (
    <div
      ref={containerRef}
      className={`flex flex-col h-full bg-[rgb(var(--bg))] select-none relative overflow-hidden theme-transition ${className}`}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUpOrLeave}
      onMouseLeave={handleMouseUpOrLeave}
    >
      {/* Top Header Controls */}
      <div className="px-4 py-3 border-b border-[rgb(var(--border))]/40 flex items-center justify-between shrink-0 bg-[rgb(var(--surface))]/90 backdrop-blur-md z-20">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-[rgb(var(--accent))]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
          </svg>
          <span className="text-[10px] font-bold tracking-wider uppercase text-[rgb(var(--text-primary))]">Memory decision graph</span>
        </div>
        <button
          onClick={resetViewport}
          className="text-[9px] font-mono px-2.5 py-1 border border-[rgb(var(--border))]/80 hover:bg-[rgb(var(--surface-hover))]/80 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all shadow-sm"
        >
          RESET
        </button>
      </div>

      {/* Physics Graph Area */}
      <div className="flex-1 relative bg-[rgb(var(--bg))] theme-transition min-h-[300px]">
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
                      stroke={isActive ? "rgb(var(--accent))" : "rgb(var(--text-muted))"}
                      strokeWidth={isActive ? "1.5" : "0.75"}
                      strokeDasharray={node.type === "outcome" ? "3 3" : "none"}
                      fill="none"
                    />

                    {/* Classy Flow Particle moving along spring lines */}
                    {!isMasked && (
                      <circle r="1.5" fill="rgb(var(--accent))">
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
                        ? "w-12 h-12 ring-4 ring-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.25)]"
                        : "w-9 h-9 shadow-sm"
                    } ${themeColorClass} shadow-md overflow-hidden`}
                  >
                    {getNodeIconSVG(node)}
                  </div>

                  {/* Clean Floating Obsidian Tooltip label */}
                  {(isHovered || isSelected) && (
                    <div className="absolute top-8 bg-[rgb(var(--surface))] border border-[rgb(var(--border))]/80 text-[9.5px] font-mono text-[rgb(var(--text-primary))] px-2.5 py-1 rounded-lg shadow-xl whitespace-nowrap z-30 transition-all font-semibold">
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
      <div className="p-4 border-t border-[rgb(var(--border))]/40 bg-[rgb(var(--surface))]/90 backdrop-blur-md text-[11.5px] leading-relaxed z-20 theme-transition shadow-lg">
        {activeNodeInfo ? (
          <div className="animate-[fadeIn_0.15s_ease-out]">
            <span className="font-mono text-[rgb(var(--text-muted))] uppercase text-[9px] tracking-wider block mb-0.5 font-bold">
              {activeNodeInfo.type} Context
            </span>
            <span className="font-bold text-[rgb(var(--text-primary))] block text-xs">{activeNodeInfo.label}</span>
            <p className="text-[rgb(var(--text-muted))] mt-1 leading-normal">{activeNodeInfo.info || "No context mappings present."}</p>
          </div>
        ) : (
          <div className="flex items-center justify-between text-[9.5px] font-mono text-[rgb(var(--text-muted))] uppercase tracking-wider font-semibold">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
              Scroll to zoom • drag empty space to pan
            </span>
            <span className="text-[8.5px] border border-[rgb(var(--border))]/80 px-2 py-0.5 rounded-md font-bold">
              ZOOM: {Math.round(zoom * 100)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

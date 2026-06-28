"use client";

import React, { useEffect, useRef, useState } from "react";

export interface GraphNode {
  id: string;
  label: string;
  type: "decision" | "person" | "date" | "source" | "outcome";
  info?: string;
  icon?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
}

interface PhysicsNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface DecisionGraphProps {
  nodes: GraphNode[];
  edges?: GraphEdge[];
  decisionTitle: string;
  className?: string;
}

function getNodeIconSVG(node: GraphNode) {
  const label = (node.label || "").toLowerCase();
  const type = node.type;
  const icon = (node.icon || "").toLowerCase();
  const info = (node.info || "").toLowerCase();

  // React
  if (label.includes("react") || icon.includes("⚛️")) {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(0)" />
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(60)" />
        <ellipse rx="10" ry="4.5" transform="translate(12 12) rotate(120)" />
        <circle cx="12" cy="12" r="2" fill="currentColor" />
      </svg>
    );
  }

  // Vue
  if (label.includes("vue") || icon.includes("💚")) {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5 transition-transform hover:scale-110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 22L24 1.5H18.5L12 13L5.5 1.5H0L12 22Z" fill="#41B883" />
        <path d="M12 13L18.5 1.5H14L12 5L10 1.5H5.5L12 13Z" fill="#35495E" />
      </svg>
    );
  }

  // Slack
  if (label.includes("slack") || icon.includes("💬") || icon.includes("slack")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
        <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
        <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/>
        <path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.315A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.522 2.523h-6.315z" fill="#ECB22E"/>
      </svg>
    );
  }

  // Google Drive
  if (label.includes("drive") || label.includes("google drive") || icon.includes("📄") || info.includes("drive") || info.includes("workspace")) {
    return (
      <svg viewBox="0 0 87.3 78" className="w-4 h-4 transition-transform hover:scale-110">
        <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066DA"/>
        <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-20.4 35.3c-.8 1.4-1.2 2.95-1.2 4.5h27.5z" fill="#00AC47"/>
        <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.5l5.85 13.95z" fill="#EA4335"/>
        <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832D"/>
        <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684FC"/>
        <path d="m73.4 26.5-10.1-17.5c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 23.5h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#FFBA00"/>
      </svg>
    );
  }

  // Jira
  if (label.includes("jira") || icon.includes("🔧") || info.includes("jira")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110">
        <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z" fill="#0052CC"/>
        <path d="M17.294 5.757H5.723a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z" fill="#0065FF"/>
        <path d="M23.013 0H11.455a5.215 5.215 0 0 0-5.215 5.215h2.129v2.057a5.215 5.215 0 0 0 5.215 5.215V1.001A1.001 1.001 0 0 0 12.636 0z" fill="#4C9AFF"/>
      </svg>
    );
  }

  // Gmail / Email
  if (label.includes("gmail") || label.includes("email") || label.includes("mail") || icon.includes("✉️") || icon.includes("envelope")) {
    return (
      <svg viewBox="52 42 88 66" className="w-4 h-4 transition-transform hover:scale-110">
        <path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>
        <path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/>
        <path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2L120 48"/>
        <path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92z"/>
        <path fill="#c5221f" d="M52 59l20 15V48l-20 11"/>
      </svg>
    );
  }

  // Zoom
  if (label.includes("zoom") || icon.includes("📹") || info.includes("zoom") || info.includes("meeting")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none">
        <rect width="24" height="24" rx="6" fill="#2D8CFF"/>
        <path d="M4 9.333C4 8.597 4.597 8 5.333 8H13.334C14.07 8 14.667 8.597 14.667 9.333v5.334C14.667 15.403 14.07 16 13.334 16H5.333C4.597 16 4 15.403 4 14.667V9.333z" fill="white"/>
        <path d="M15.667 10.4L19.333 8.267A.5.5 0 0 1 20 8.7v6.6a.5.5 0 0 1-.667.433L15.667 13.6V10.4z" fill="white"/>
      </svg>
    );
  }

  // Calendar / Date
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

  // Person
  if (type === "person" || icon.includes("👤") || icon.includes("👥")) {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    );
  }

  // Outcome
  if (type === "outcome") {
    const isSuccess = icon.includes("✅") || icon.includes("success") || label.toLowerCase().includes("scale") || label.toLowerCase().includes("hire") || label.toLowerCase().includes("success");
    const isError = icon.includes("❌") || icon.includes("error") || label.toLowerCase().includes("write-off") || label.toLowerCase().includes("fail") || label.toLowerCase().includes("terminate");

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

  // Decision (default)
  if (type === "decision") {
    return (
      <svg viewBox="0 0 24 24" className="w-4 h-4 transition-transform hover:scale-110" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    );
  }

  // Fallback to text icon or first character
  return <span className="text-[10px] font-bold select-none">{node.icon || node.label.charAt(0)}</span>;
}

export default function DecisionGraph({
  nodes,
  edges: edgesProp,
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
  // Stable random durations for edge particle animations — computed once per edge set
  const edgeDurationsRef = useRef<Map<string, number>>(new Map());
  const [renderTrigger, setRenderTrigger] = useState(0);

  // Build edges: if edgesProp provided, use them; otherwise fallback to star topology
  const computedEdges: GraphEdge[] = React.useMemo(() => {
    if (edgesProp && edgesProp.length > 0) return edgesProp;
    // Fallback: star topology from first decision node to all others
    const center = nodes.find((n) => n.type === "decision") || nodes[0];
    if (!center) return [];
    return nodes
      .filter((n) => n.id !== center.id)
      .map((n) => ({ source: center.id, target: n.id }));
  }, [nodes, edgesProp]);

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

    physicsNodesRef.current = nodes.map((node, idx) => {
      const existing = physicsNodesRef.current.find((n) => n.id === node.id);
      if (existing) {
        return { ...node, x: existing.x, y: existing.y, vx: existing.vx, vy: existing.vy };
      }

      // New nodes: spread around canvas center
      const angle = (idx / nodes.length) * 2 * Math.PI + Math.random() * 0.5;
      const dist = 60 + Math.random() * 80;
      return {
        ...node,
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
      };
    });
  }, [nodes]);

  // Main physics loop (Coulomb repulsion + Hooke spring along edges)
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

      const repelConstant = 2000;
      const springConstant = 0.035;
      const springLength = 120;
      const centerPull = 0.006;
      const friction = 0.82;

      // 1. Coulomb repulsion between ALL nodes
      for (let i = 0; i < pNodes.length; i++) {
        for (let j = i + 1; j < pNodes.length; j++) {
          const n1 = pNodes[i];
          const n2 = pNodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          // Soften and cap minimum distance to prevent huge repelling force at close range
          const dist = Math.max(30, Math.sqrt(dx * dx + dy * dy));

          if (dist < 250) {
            const force = repelConstant / (dist * dist + 400); // 400 softening factor
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            n1.vx -= fx;
            n1.vy -= fy;
            n2.vx += fx;
            n2.vy += fy;
          }
        }
      }

      // 2. Spring attraction along edges
      computedEdges.forEach((edge) => {
        const srcNode = pNodes.find((n) => n.id === edge.source);
        const tgtNode = pNodes.find((n) => n.id === edge.target);
        if (!srcNode || !tgtNode) return;

        const dx = tgtNode.x - srcNode.x;
        const dy = tgtNode.y - srcNode.y;
        const dist = Math.max(30, Math.sqrt(dx * dx + dy * dy));

        const delta = dist - springLength;
        const force = delta * springConstant;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        srcNode.vx += fx;
        srcNode.vy += fy;
        tgtNode.vx -= fx;
        tgtNode.vy -= fy;
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

        // Apply friction
        node.vx *= friction;
        node.vy *= friction;

        // Cap maximum velocity to prevent massive explosions
        const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
        const maxSpeed = 8;
        if (speed > maxSpeed) {
          node.vx = (node.vx / speed) * maxSpeed;
          node.vy = (node.vy / speed) * maxSpeed;
        }

        // Apply a threshold below which velocity is rounded to 0 (prevents shaking)
        const threshold = 0.05;
        if (Math.abs(node.vx) > threshold || Math.abs(node.vy) > threshold) {
          node.x += node.vx;
          node.y += node.vy;
        } else {
          node.vx = 0;
          node.vy = 0;
        }

        // Keep inside canvas bounds - disabled for Obsidian-style infinite canvas
        // node.x = Math.max(40, Math.min(width - 40, node.x));
        // node.y = Math.max(40, Math.min(height - 40, node.y));
      });

      setRenderTrigger((prev) => prev + 1);
      animFrame = requestAnimationFrame(runFrame);
    };

    animFrame = requestAnimationFrame(runFrame);
    return () => cancelAnimationFrame(animFrame);
  }, [computedEdges]);

  // Mouse wheel Zoom handler (Smooth zoom-to-mouse pointer)
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = 0.08;
    const direction = e.deltaY < 0 ? 1 : -1;

    setZoom((prevZoom) => {
      const factor = 1 + direction * zoomFactor;
      const newZoom = Math.max(0.05, Math.min(15.0, prevZoom * factor));

      setPan((prevPan) => {
        const dx = mouseX - prevPan.x;
        const dy = mouseY - prevPan.y;
        return {
          x: mouseX - dx * (newZoom / prevZoom),
          y: mouseY - dy * (newZoom / prevZoom),
        };
      });

      return newZoom;
    });
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

  // RESET = fit-to-view: frame the whole node cluster in the viewport.
  // (Previously just snapped to a fixed zoom/pan, which did nothing visible
  // once the physics sim had spread nodes out — so it read as "not working".)
  const resetViewport = () => {
    const container = containerRef.current;
    const pNodes = physicsNodesRef.current;
    if (!container || pNodes.length === 0) {
      setZoom(0.95);
      setPan({ x: 0, y: 0 });
      return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Bounding box of all nodes in world coordinates
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of pNodes) {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x > maxX) maxX = n.x;
      if (n.y > maxY) maxY = n.y;
    }

    const padding = 80; // px of breathing room around the cluster
    const bboxW = Math.max(maxX - minX, 1);
    const bboxH = Math.max(maxY - minY, 1);

    // Zoom to fit, capped so a tiny/single-node graph doesn't over-zoom
    const fitZoom = Math.min(
      (width - padding * 2) / bboxW,
      (height - padding * 2) / bboxH
    );
    const newZoom = Math.max(0.2, Math.min(1.4, fitZoom));

    // Center the bbox center in the viewport: screen = pan + world * zoom
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    setZoom(newZoom);
    setPan({
      x: width / 2 - centerX * newZoom,
      y: height / 2 - centerY * newZoom,
    });
  };

  const pNodes = physicsNodesRef.current;

  // Active hover/selection ID
  const activeFocusId = selectedNodeId || hoveredNodeId;

  // Node connection masking helper
  const isNodeConnected = (nodeId: string) => {
    if (!activeFocusId) return true;
    if (nodeId === activeFocusId) return true;
    // Check if nodeId has a direct edge with activeFocusId
    return computedEdges.some(
      (e) =>
        (e.source === activeFocusId && e.target === nodeId) ||
        (e.target === activeFocusId && e.source === nodeId)
    );
  };

  // Classy type color coding
  const getNodeColor = (type: GraphNode["type"]) => {
    switch (type) {
      case "decision": return "bg-indigo-500/20 border-indigo-500/50 text-indigo-400 backdrop-blur-sm";
      case "person": return "bg-emerald-500/20 border-emerald-500/50 text-emerald-400 backdrop-blur-sm";
      case "source": return "bg-cyan-500/20 border-cyan-500/50 text-cyan-400 backdrop-blur-sm";
      case "date": return "bg-amber-500/20 border-amber-500/50 text-amber-400 backdrop-blur-sm";
      case "outcome": return "bg-rose-500/20 border-rose-500/50 text-rose-400 backdrop-blur-sm";
      default: return "bg-zinc-500/20 border-zinc-500/50 text-zinc-400 backdrop-blur-sm";
    }
  };

  const activeNodeInfo = nodes.find((n) => n.id === activeFocusId);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full bg-[rgb(var(--bg))] select-none overflow-hidden theme-transition ${className}`}
      style={{
        backgroundImage: "radial-gradient(rgba(128, 128, 128, 0.15) 1.2px, transparent 1.2px)",
        backgroundPosition: `${pan.x}px ${pan.y}px`,
        backgroundSize: `${24 * zoom}px ${24 * zoom}px`,
      }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUpOrLeave}
      onMouseLeave={handleMouseUpOrLeave}
    >
      {/* 1. FLOATING CONTROL PILL (Top Right) */}
      <div className="absolute top-3 right-3 flex items-center gap-2 z-20 bg-[rgb(var(--surface))]/70 backdrop-blur-md border border-[rgb(var(--border))]/50 px-2.5 py-1.5 rounded-xl shadow-lg transition-all">
        <button
          onClick={resetViewport}
          className="text-[9px] font-sans font-bold px-2 py-1 hover:bg-[rgb(var(--surface-hover))]/80 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all"
        >
          RESET
        </button>
        <span className="text-[10px] text-[rgb(var(--border))]/70">|</span>
        <span className="text-[9px] font-mono font-bold text-[rgb(var(--text-muted))] select-none min-w-[32px] text-center">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      {/* 2. FLOATING CONTEXT CARD (Bottom Left) */}
      <div className="absolute bottom-3 left-3 right-3 md:right-auto md:max-w-[280px] z-20 bg-[rgb(var(--surface))]/80 backdrop-blur-md border border-[rgb(var(--border))]/50 p-3 rounded-2xl shadow-xl transition-all duration-300 pointer-events-auto">
        {activeNodeInfo ? (
          <div className="animate-[fadeIn_0.15s_ease-out]">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${
                activeNodeInfo.type === "decision" ? "bg-indigo-500" :
                activeNodeInfo.type === "person" ? "bg-emerald-500" :
                activeNodeInfo.type === "source" ? "bg-cyan-500" :
                activeNodeInfo.type === "date" ? "bg-amber-500" : "bg-rose-500"
              }`} />
              <span className="font-mono text-[rgb(var(--text-muted))] uppercase text-[8px] tracking-wider font-bold">
                {activeNodeInfo.type} Context
              </span>
            </div>
            <span className="font-bold text-[rgb(var(--text-primary))] block text-xs leading-snug">{activeNodeInfo.label}</span>
            <p className="text-[rgb(var(--text-muted))] mt-1 leading-normal text-[10px]">{activeNodeInfo.info || "No context mappings present."}</p>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-[9px] font-sans text-[rgb(var(--text-muted))] font-medium select-none">
            <span className="relative flex h-1.5 w-1.5 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-60" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-indigo-500" />
            </span>
            <span>Scroll to zoom · drag canvas · click nodes</span>
          </div>
        )}
      </div>

      {/* 3. GRAPH CANVAS AREA */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: "0 0",
        }}
        className="absolute inset-0 origin-top-left pointer-events-none"
      >
        {/* SVG Edge Connectors */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
          {computedEdges.map((edge, edgeIdx) => {
            const srcNode = pNodes.find((n) => n.id === edge.source);
            const tgtNode = pNodes.find((n) => n.id === edge.target);
            if (!srcNode || !tgtNode) return null;

            const isSourceHovered = hoveredNodeId === edge.source;
            const isTargetHovered = hoveredNodeId === edge.target;
            const isSourceSelected = selectedNodeId === edge.source;
            const isTargetSelected = selectedNodeId === edge.target;

            const isActive = isSourceHovered || isTargetHovered || isSourceSelected || isTargetSelected;
            const pathId = `edge-${edgeIdx}`;

            const isMasked = activeFocusId !== null && !isNodeConnected(edge.source) && !isNodeConnected(edge.target);
            const strokeOpacity = isMasked ? 0.03 : isActive ? 0.8 : 0.25;

            return (
              <g key={pathId} className="transition-opacity duration-300" style={{ opacity: strokeOpacity }}>
                <path
                  id={pathId}
                  d={`M ${srcNode.x} ${srcNode.y} L ${tgtNode.x} ${tgtNode.y}`}
                  stroke={isActive ? "rgb(var(--accent))" : "rgb(var(--text-muted))"}
                  strokeWidth={isActive ? "1.5" : "0.75"}
                  fill="none"
                />
                {/* Flow Particle */}
                {!isMasked && (
                  <circle r="1.5" fill="rgb(var(--accent))">
                    <animateMotion
                      dur={`${(() => {
                        if (!edgeDurationsRef.current.has(pathId)) {
                          edgeDurationsRef.current.set(pathId, 2.5 + Math.random() * 1.5);
                        }
                        return edgeDurationsRef.current.get(pathId);
                      })()}s`}
                      repeatCount="indefinite"
                    >
                      <mpath href={`#${pathId}`} />
                    </animateMotion>
                  </circle>
                )}
              </g>
            );
          })}
        </svg>

        {/* Physics Nodes */}
        <div className="absolute inset-0 z-10 pointer-events-none">
          {pNodes.map((node) => {
            const isCenter = node.type === "decision";
            const isHovered = hoveredNodeId === node.id;
            const isSelected = selectedNodeId === node.id;

            const isDimmed = activeFocusId !== null && !isNodeConnected(node.id);
            const themeColorClass = getNodeColor(node.type);

            return (
              <div
                key={node.id}
                className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-grab active:cursor-grabbing flex flex-col items-center justify-center physics-node group"
                style={{
                  left: node.x,
                  top: node.y,
                  transform: `translate(-50%, -50%) scale(${isHovered || isSelected ? 1.12 : 1})`,
                  opacity: isDimmed ? 0.15 : 1,
                  transition: "opacity 0.3s ease, transform 0.2s ease",
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
                {/* Node circle */}
                <div
                  className={`flex items-center justify-center rounded-full transition-all border ${
                    isCenter
                      ? "w-9 h-9 ring-4 ring-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.35)]"
                      : "w-6 h-6 shadow-md"
                  } ${themeColorClass} border-[rgb(var(--border))]/30 overflow-hidden`}
                >
                  {getNodeIconSVG(node)}
                </div>

                {/* Obsidian-style Canvas Label (Permanently visible) */}
                <div
                  className={`mt-1.5 text-[8.5px] font-sans font-medium tracking-wide whitespace-nowrap select-none transition-all ${
                    isHovered || isSelected
                      ? "text-[rgb(var(--text-primary))] font-bold scale-105"
                      : "text-[rgb(var(--text-muted))]/80"
                  }`}
                  style={{
                    textShadow: isHovered || isSelected ? "0 1px 4px rgba(0,0,0,0.5)" : "none",
                  }}
                >
                  {node.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

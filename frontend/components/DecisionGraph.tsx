"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

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
  mass: number;   // inertia — scales with connectivity (degree)
  radius: number; // physical radius used for collision + hit-testing
}

interface DecisionGraphProps {
  nodes: GraphNode[];
  edges?: GraphEdge[];
  decisionTitle: string;
  className?: string;
  onNodeClick?: (nodeId: string) => void;
}

// Helpers for CSS variables parsing
const parseCSSVar = (varName: string, fallback: string) => {
  if (typeof window === "undefined") return fallback;
  const val = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  if (!val) return fallback;
  if (/^\d+\s+\d+\s+\d+$/.test(val)) {
    return `rgb(${val.split(/\s+/).join(",")})`;
  }
  if (/^\d+,\s*\d+,\s*\d+$/.test(val)) {
    return `rgb(${val})`;
  }
  return val;
};

const getThemeColors = () => {
  const bg = parseCSSVar("--bg", "#080808");
  const text = parseCSSVar("--text-primary", "#ececec");
  const muted = parseCSSVar("--text-muted", "#9ca3af");
  const border = parseCSSVar("--border", "#372850");
  const accent = parseCSSVar("--accent", "#7c3aed");
  const accentMuted = accent.replace(")", ", 0.2)").replace("rgb", "rgba");

  return { bg, text, muted, border, accent, accentMuted };
};

// Node Emojis Mapping
function getNodeIconEmoji(node: GraphNode) {
  const label = (node.label || "").toLowerCase();
  const type = node.type;
  const icon = (node.icon || "").toLowerCase();
  const info = (node.info || "").toLowerCase();

  if (label.includes("react") || icon.includes("⚛️")) return "⚛️";
  if (label.includes("vue") || icon.includes("💚")) return "💚";
  if (label.includes("slack") || icon.includes("💬") || icon.includes("slack")) return "💬";
  if (label.includes("drive") || label.includes("google drive") || icon.includes("📄") || info.includes("drive") || info.includes("workspace")) return "📄";
  if (label.includes("jira") || icon.includes("🔧") || info.includes("jira")) return "🔧";
  if (label.includes("gmail") || label.includes("email") || label.includes("mail") || icon.includes("✉️") || icon.includes("envelope")) return "✉️";
  if (label.includes("zoom") || icon.includes("📹") || info.includes("zoom") || info.includes("meeting")) return "📹";
  if (type === "date" || icon.includes("📅") || label.includes("calendar") || label.includes("date")) return "📅";
  if (type === "person" || icon.includes("👤") || icon.includes("👥")) return "👤";
  
  if (type === "outcome") {
    const isSuccess = icon.includes("✅") || icon.includes("success") || label.toLowerCase().includes("scale") || label.toLowerCase().includes("hire") || label.toLowerCase().includes("success");
    const isError = icon.includes("❌") || icon.includes("error") || label.toLowerCase().includes("write-off") || label.toLowerCase().includes("fail") || label.toLowerCase().includes("terminate");
    if (isSuccess) return "✅";
    if (isError) return "❌";
    return "⚠️";
  }

  if (type === "decision") return "💡";

  return node.icon || node.label.charAt(0).toUpperCase();
}

const DEFAULT_SETTINGS = {
  showLabels: "all",
  showIcons: false,
  showGrid: false,
  nodeRadius: 4.5,
  linkOpacity: 0.22,
  particleSpeed: 0,
  charge: 1200,
  linkDistance: 90,
  linkStrength: 0.04,
  gravity: 0.012,
  collision: 1.0,
  friction: 0.85,
};

export default function DecisionGraph({
  nodes,
  edges: edgesProp,
  decisionTitle,
  className = "",
  onNodeClick,
}: DecisionGraphProps) {
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // States for UI
  const [zoom, setZoomState] = useState(0.95);
  const [pan, setPanState] = useState({ x: 0, y: 0 });
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Custom Settings
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS });

  // State update helpers (updating both ref and state to avoid frame lag)
  const zoomRef = useRef(zoom);
  const setZoom = (newZoom: number) => {
    zoomRef.current = newZoom;
    setZoomState(newZoom);
  };

  const panRef = useRef(pan);
  const setPan = (newPan: { x: number; y: number }) => {
    panRef.current = newPan;
    setPanState(newPan);
  };

  const settingsRef = useRef(settings);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  // The rAF draw loop only restarts on [computedEdges, nodeDegrees] — reading
  // selectedNodeId/hoveredNodeId state directly inside it meant hover/selection
  // highlighting only ever reflected whatever those were the last time the loop
  // itself restarted, not live changes. Refs are always current regardless.
  const selectedNodeIdRef = useRef(selectedNodeId);
  useEffect(() => {
    selectedNodeIdRef.current = selectedNodeId;
  }, [selectedNodeId]);

  const hoveredNodeIdRef = useRef(hoveredNodeId);
  useEffect(() => {
    hoveredNodeIdRef.current = hoveredNodeId;
  }, [hoveredNodeId]);

  // Load settings from localStorage when client mounts or user changes
  useEffect(() => {
    if (typeof window !== "undefined") {
      const settingsKey = user ? `kairos-graph-settings-${user.uid}` : "kairos-graph-settings-default";
      const saved = localStorage.getItem(settingsKey);

      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setSettings({
            ...DEFAULT_SETTINGS,
            ...parsed,
          });
        } catch (err) {
          console.warn("Failed to parse saved graph settings:", err);
          setSettings({ ...DEFAULT_SETTINGS });
        }
      } else {
        setSettings({ ...DEFAULT_SETTINGS });
      }
      alphaRef.current = 1.0; // reheat simulation to apply new forces
    }
  }, [user]);

  const updateSetting = (key: string, value: any) => {
    setSettings((prev) => {
      const updated = { ...prev, [key]: value };
      if (typeof window !== "undefined") {
        const settingsKey = user ? `kairos-graph-settings-${user.uid}` : "kairos-graph-settings-default";
        localStorage.setItem(settingsKey, JSON.stringify(updated));
      }
      return updated;
    });
    alphaRef.current = 1.0; // reheat simulation on adjustment
  };

  const resetSettings = () => {
    setSettings({ ...DEFAULT_SETTINGS });
    if (typeof window !== "undefined") {
      const settingsKey = user ? `kairos-graph-settings-${user.uid}` : "kairos-graph-settings-default";
      localStorage.setItem(settingsKey, JSON.stringify(DEFAULT_SETTINGS));
    }
    alphaRef.current = 1.0;
  };

  // Theme observer
  const themeRef = useRef({
    bg: "#080808",
    text: "#ececec",
    muted: "#9ca3af",
    border: "#372850",
    accent: "#7c3aed",
    accentMuted: "rgba(124, 58, 237, 0.2)"
  });

  useEffect(() => {
    const updateTheme = () => {
      themeRef.current = getThemeColors();
    };
    updateTheme();
    
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => observer.disconnect();
  }, []);

  // Physics Simulation Coordinates
  const physicsNodesRef = useRef<PhysicsNode[]>([]);
  const alphaRef = useRef(1.0); // simulation cooling parameter
  const draggedNodeRef = useRef<PhysicsNode | null>(null);
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0 });

  // Build edges: fallback to star topology if not provided
  const computedEdges: GraphEdge[] = React.useMemo(() => {
    if (edgesProp && edgesProp.length > 0) return edgesProp;
    const center = nodes.find((n) => n.type === "decision") || nodes[0];
    if (!center) return [];
    return nodes
      .filter((n) => n.id !== center.id)
      .map((n) => ({ source: center.id, target: n.id }));
  }, [nodes, edgesProp]);

  // Compute node degrees (for size scaling)
  const nodeDegrees = React.useMemo(() => {
    const degrees = new Map<string, number>();
    nodes.forEach((node) => degrees.set(node.id, 0));
    computedEdges.forEach((edge) => {
      degrees.set(edge.source, (degrees.get(edge.source) || 0) + 1);
      degrees.set(edge.target, (degrees.get(edge.target) || 0) + 1);
    });
    return degrees;
  }, [nodes, computedEdges]);

  // Sync nodes to simulation
  useEffect(() => {
    if (nodes.length === 0) {
      physicsNodesRef.current = [];
      return;
    }

    const width = containerRef.current?.clientWidth || 400;
    const height = containerRef.current?.clientHeight || 350;
    const cx = width / 2;
    const cy = height / 2;

    const baseRadius = settingsRef.current.nodeRadius;

    physicsNodesRef.current = nodes.map((node, idx) => {
      const degree = nodeDegrees.get(node.id) || 0;
      // Heavier, larger nodes for well-connected hubs (Obsidian-style)
      const radius = baseRadius + Math.sqrt(degree) * 1.5;
      const mass = 1 + degree * 0.6;

      const existing = physicsNodesRef.current.find((n) => n.id === node.id);
      if (existing) {
        return { ...node, x: existing.x, y: existing.y, vx: existing.vx, vy: existing.vy, mass, radius };
      }

      // Seed new nodes on a golden-angle spiral so they don't stack on one axis
      const angle = idx * 2.399963229728653 + Math.random() * 0.4;
      const dist = 40 + Math.sqrt(idx) * 22 + Math.random() * 30;
      return {
        ...node,
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
        mass,
        radius,
      };
    });

    alphaRef.current = 1.0; // reheat
  }, [nodes, nodeDegrees]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Measure synchronously on mount — dimensions start at 0×0 and the
    // observer's first delivery lands a frame later, which painted the canvas
    // as a blank/shrunken flash every time this component remounted (e.g.
    // switching dashboard tabs). Seed the real size immediately instead.
    setDimensions({
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
        alphaRef.current = 1.0; // reheat simulation on resize
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Run Physics forces
  const runPhysics = (width: number, height: number) => {
    const pNodes = physicsNodesRef.current;
    if (pNodes.length === 0) return;

    const cx = width / 2;
    const cy = height / 2;

    const charge = settingsRef.current.charge;
    const strength = settingsRef.current.linkStrength;
    const distance = settingsRef.current.linkDistance;
    const gravity = settingsRef.current.gravity;
    const collision = settingsRef.current.collision ?? 1.0;
    const damping = settingsRef.current.friction ?? 0.85;
    const alpha = alphaRef.current;

    // Fast id → node lookup (avoids O(E·N) find() over the edge list) and
    // refresh each node's collision radius from the live size slider.
    const baseRadius = settingsRef.current.nodeRadius;
    const byId = new Map<string, PhysicsNode>();
    for (const n of pNodes) {
      const degree = nodeDegrees.get(n.id) || 0;
      n.radius = baseRadius + Math.sqrt(degree) * 1.5;
      byId.set(n.id, n);
    }

    // 1. Mass-weighted Coulomb repulsion between every pair of nodes.
    //    Heavier (better-connected) nodes are shoved around less, so hubs
    //    stay put while leaf nodes fan out around them.
    for (let i = 0; i < pNodes.length; i++) {
      const n1 = pNodes[i];
      for (let j = i + 1; j < pNodes.length; j++) {
        const n2 = pNodes[j];
        let dx = n2.x - n1.x;
        let dy = n2.y - n1.y;
        let distSq = dx * dx + dy * dy;
        // Jitter apart coincident nodes so the direction is well-defined
        if (distSq < 0.01) {
          dx = (Math.random() - 0.5) * 0.5;
          dy = (Math.random() - 0.5) * 0.5;
          distSq = dx * dx + dy * dy;
        }
        const dist = Math.sqrt(distSq);

        if (dist < 480) {
          const force = charge / (distSq + 150);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          n1.vx -= fx / n1.mass;
          n1.vy -= fy / n1.mass;
          n2.vx += fx / n2.mass;
          n2.vy += fy / n2.mass;
        }

        // 2. Hard collision resolution — nodes are solid bodies and never
        //    overlap. Overlap is split by inverse mass (Obsidian-like). A
        //    node being dragged is treated as immovable so it tracks the
        //    cursor exactly and just shoves its neighbours aside.
        if (collision > 0) {
          const minDist = (n1.radius + n2.radius) * 1.6 + 4;
          if (dist < minDist) {
            const overlap = (minDist - dist) * collision;
            const ux = dx / dist;
            const uy = dy / dist;
            const draggedId = draggedNodeRef.current?.id;
            const n1Fixed = n1.id === draggedId;
            const n2Fixed = n2.id === draggedId;
            if (n1Fixed && n2Fixed) {
              // both pinned — nothing to do
            } else if (n1Fixed) {
              n2.x += ux * overlap;
              n2.y += uy * overlap;
            } else if (n2Fixed) {
              n1.x -= ux * overlap;
              n1.y -= uy * overlap;
            } else {
              const invSum = 1 / (n1.mass + n2.mass);
              const push1 = overlap * 0.5 * (n2.mass * invSum);
              const push2 = overlap * 0.5 * (n1.mass * invSum);
              n1.x -= ux * push1;
              n1.y -= uy * push1;
              n2.x += ux * push2;
              n2.y += uy * push2;
            }
          }
        }
      }
    }

    // 3. Link force along connected edges (Spring). Rest length grows with
    //    the two node radii so big hubs don't swallow their neighbours.
    computedEdges.forEach((edge) => {
      const src = byId.get(edge.source);
      const tgt = byId.get(edge.target);
      if (!src || !tgt) return;

      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.1;

      const restLength = distance + src.radius + tgt.radius;
      const force = (dist - restLength) * strength;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      src.vx += fx / src.mass;
      src.vy += fy / src.mass;
      tgt.vx -= fx / tgt.mass;
      tgt.vy -= fy / tgt.mass;
    });

    // 4. Gravity force (pull to center)
    pNodes.forEach((node) => {
      const dx = cx - node.x;
      const dy = cy - node.y;
      node.vx += dx * gravity;
      node.vy += dy * gravity;
    });

    // 5. Update coordinates & apply damping
    pNodes.forEach((node) => {
      if (node.id === draggedNodeRef.current?.id) {
        node.vx = 0;
        node.vy = 0;
        return;
      }

      node.vx *= damping;
      node.vy *= damping;

      const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
      const maxSpeed = 12;
      if (speed > maxSpeed) {
        node.vx = (node.vx / speed) * maxSpeed;
        node.vy = (node.vy / speed) * maxSpeed;
      }

      node.x += node.vx * alpha;
      node.y += node.vy * alpha;
    });
  };

  // Node Color Hex Mapping
  const getNodeColorHex = (type: GraphNode["type"]) => {
    const isLight = themeRef.current.bg === "rgb(249,249,249)" || themeRef.current.bg === "#f9f9f9";
    if (isLight) {
      switch (type) {
        case "decision": return "#4f46e5"; // indigo-600
        case "person": return "#059669"; // emerald-600
        case "source": return "#0891b2"; // cyan-600
        case "date": return "#d97706"; // amber-600
        case "outcome": return "#e11d48"; // rose-600
        default: return "#475569"; // slate-600
      }
    } else {
      switch (type) {
        case "decision": return "#818cf8"; // indigo-400
        case "person": return "#34d399"; // emerald-400
        case "source": return "#22d3ee"; // cyan-400
        case "date": return "#fbbf24"; // amber-400
        case "outcome": return "#fb7185"; // rose-400
        default: return "#94a3b8"; // slate-400
      }
    }
  };

  // Dynamic Drawing Loop
  const draw = (canvas: HTMLCanvasElement, width: number, height: number) => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const theme = themeRef.current;
    const currentSettings = settingsRef.current;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    ctx.save();
    ctx.scale(dpr, dpr);

    const zoom = zoomRef.current;
    const pan = panRef.current;
    const pNodes = physicsNodesRef.current;

    // Fast id → node lookup shared by the link + node passes
    const byId = new Map<string, PhysicsNode>();
    for (const n of pNodes) byId.set(n.id, n);

    // 1. Draw Grid Background (if enabled)
    if (currentSettings.showGrid) {
      const spacing = 28 * zoom;
      const startX = pan.x % spacing;
      const startY = pan.y % spacing;
      ctx.beginPath();
      for (let x = startX; x < width; x += spacing) {
        for (let y = startY; y < height; y += spacing) {
          ctx.arc(x, y, 1.0 * Math.min(zoom, 1.4), 0, 2 * Math.PI);
        }
      }
      ctx.fillStyle = theme.border === "rgb(229,229,229)" || theme.border === "#e5e5e5" 
        ? "rgba(0, 0, 0, 0.05)" 
        : "rgba(255, 255, 255, 0.06)";
      ctx.fill();
    }

    const activeFocusId = selectedNodeIdRef.current || hoveredNodeIdRef.current;
    const isFocusActive = activeFocusId !== null;

    // Precompute the direct neighbours of the focused node once per frame
    const focusNeighbors = new Set<string>();
    if (isFocusActive) {
      for (const e of computedEdges) {
        if (e.source === activeFocusId) focusNeighbors.add(e.target);
        else if (e.target === activeFocusId) focusNeighbors.add(e.source);
      }
    }

    // Connectivity masking helper
    const isNodeConnected = (nodeId: string) => {
      if (!isFocusActive) return true;
      if (nodeId === activeFocusId) return true;
      return focusNeighbors.has(nodeId);
    };

    // 2. Draw Connections (Links)
    computedEdges.forEach((edge, edgeIdx) => {
      const src = byId.get(edge.source);
      const tgt = byId.get(edge.target);
      if (!src || !tgt) return;

      const sx = src.x * zoom + pan.x;
      const sy = src.y * zoom + pan.y;
      const tx = tgt.x * zoom + pan.x;
      const ty = tgt.y * zoom + pan.y;

      const isSourceActive = activeFocusId === edge.source;
      const isTargetActive = activeFocusId === edge.target;
      const isActiveLink = isSourceActive || isTargetActive;

      let opacity = currentSettings.linkOpacity;
      if (isFocusActive) {
        opacity = isActiveLink ? Math.min(opacity * 2.2, 0.85) : 0.03;
      }

      ctx.strokeStyle = isActiveLink ? theme.accent : theme.muted;
      ctx.lineWidth = isActiveLink ? 1.6 : 0.75;
      ctx.globalAlpha = opacity;

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();

      // Flow particle along link
      if (currentSettings.particleSpeed > 0 && (!isFocusActive || isActiveLink)) {
        ctx.globalAlpha = isActiveLink ? 0.9 : opacity * 0.6;
        const speed = currentSettings.particleSpeed;
        const time = performance.now() * 0.0008 * speed;
        const edgeOffset = (edgeIdx * 0.19) % 1.0;
        const t = (time + edgeOffset) % 1.0;

        const px = sx + (tx - sx) * t;
        const py = sy + (ty - sy) * t;

        ctx.fillStyle = theme.accent;
        ctx.beginPath();
        ctx.arc(px, py, 2.0, 0, 2 * Math.PI);
        ctx.fill();
      }
    });

    ctx.globalAlpha = 1.0;

    // 3. Draw Nodes
    pNodes.forEach((node) => {
      const nx = node.x * zoom + pan.x;
      const ny = node.y * zoom + pan.y;

      const radius = node.radius;

      const isHovered = hoveredNodeIdRef.current === node.id;
      const isSelected = selectedNodeIdRef.current === node.id;
      const isFocused = isHovered || isSelected;

      let opacity = 1.0;
      if (isFocusActive && !isNodeConnected(node.id)) {
        opacity = 0.12;
      }

      ctx.globalAlpha = opacity;
      const color = getNodeColorHex(node.type);

      ctx.save();
      
      // Shadow glow for focused node
      if (isFocused) {
        ctx.shadowColor = color;
        ctx.shadowBlur = 12;
      }

      // Border stroke
      if (isFocused) {
        ctx.strokeStyle = theme.text;
        ctx.lineWidth = 1.8;
      } else {
        ctx.strokeStyle = theme.border;
        ctx.lineWidth = 0.9;
      }

      // Draw dot
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(nx, ny, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      // Show Logo Emojis inside nodes (if enabled)
      if (currentSettings.showIcons) {
        const emoji = getNodeIconEmoji(node);
        ctx.fillStyle = "#ffffff";
        ctx.font = `bold ${Math.max(8, radius * 0.95)}px system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(emoji, nx, ny);
      }

      // 4. Draw Labels
      const labelSetting = currentSettings.showLabels;
      let shouldDrawLabel = false;
      if (labelSetting === "all") {
        shouldDrawLabel = zoom > 0.48 || isFocused;
      } else if (labelSetting === "hover") {
        shouldDrawLabel = isFocused;
      }

      if (shouldDrawLabel) {
        ctx.font = `500 ${isFocused ? 9.5 : 8.5}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        const textY = ny + radius + 4.5;

        // Draw shadow stroke background to make text readable over lines
        ctx.strokeStyle = theme.bg;
        ctx.lineWidth = 3.5;
        ctx.lineJoin = "round";
        ctx.strokeText(node.label, nx, textY);

        ctx.fillStyle = isFocused ? theme.text : theme.muted;
        ctx.fillText(node.label, nx, textY);
      }

      ctx.globalAlpha = 1.0;
    });

    ctx.restore();
  };

  // Set up game loop
  useEffect(() => {
    let animFrameId: number;

    const tick = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) {
        animFrameId = requestAnimationFrame(tick);
        return;
      }

      const width = container.clientWidth;
      const height = container.clientHeight;

      if (alphaRef.current > 0.005) {
        runPhysics(width, height);
        alphaRef.current *= 0.985;
      } else {
        alphaRef.current = 0;
      }

      draw(canvas, width, height);

      animFrameId = requestAnimationFrame(tick);
    };

    animFrameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrameId);
  }, [computedEdges, nodeDegrees]);

  // Zoom wheel event handler (attaches directly to bypass passive listener limits)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();

      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = 0.08;
      const direction = e.deltaY < 0 ? 1 : -1;

      const prevZoom = zoomRef.current;
      const factor = 1 + direction * zoomFactor;
      const newZoom = Math.max(0.08, Math.min(10.0, prevZoom * factor));

      const worldX = (mouseX - panRef.current.x) / prevZoom;
      const worldY = (mouseY - panRef.current.y) / prevZoom;

      setPan({
        x: mouseX - worldX * newZoom,
        y: mouseY - worldY * newZoom,
      });
      setZoom(newZoom);
      alphaRef.current = 1.0; // reheat simulation
    };

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", handleWheel);
    };
  }, []);

  // Touch handlers (mobile) — single-finger drag/pan + tap-select, two-finger
  // pinch-zoom. Attached natively so we can preventDefault the page scroll.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let pinchStartDist = 0;
    let pinchStartZoom = 1;
    let touchMoved = false;
    let touchStartX = 0;
    let touchStartY = 0;
    let lastTouchCount = 0;

    const localPoint = (t: Touch) => {
      const rect = canvas.getBoundingClientRect();
      return { x: t.clientX - rect.left, y: t.clientY - rect.top };
    };

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        e.preventDefault();
        touchMoved = false;
        lastTouchCount = 1;
        const { x: screenX, y: screenY } = localPoint(e.touches[0]);
        touchStartX = screenX;
        touchStartY = screenY;
        const worldX = (screenX - panRef.current.x) / zoomRef.current;
        const worldY = (screenY - panRef.current.y) / zoomRef.current;

        const node = physicsNodesRef.current.find((n) => {
          const d = Math.sqrt((n.x - worldX) ** 2 + (n.y - worldY) ** 2);
          return d <= n.radius + 14;
        });

        if (node) {
          draggedNodeRef.current = node;
          node.vx = 0;
          node.vy = 0;
          alphaRef.current = 1.0;
        } else {
          isPanningRef.current = true;
          panStartRef.current = {
            x: e.touches[0].clientX - panRef.current.x,
            y: e.touches[0].clientY - panRef.current.y,
          };
        }
      } else if (e.touches.length === 2) {
        e.preventDefault();
        draggedNodeRef.current = null;
        isPanningRef.current = false;
        lastTouchCount = 2;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        pinchStartDist = Math.sqrt(dx * dx + dy * dy) || 1;
        pinchStartZoom = zoomRef.current;
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 2 && pinchStartDist > 0) {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        const prevZoom = zoomRef.current;
        const newZoom = Math.max(0.08, Math.min(10.0, pinchStartZoom * (dist / pinchStartDist)));
        const worldX = (midX - panRef.current.x) / prevZoom;
        const worldY = (midY - panRef.current.y) / prevZoom;
        setPan({ x: midX - worldX * newZoom, y: midY - worldY * newZoom });
        setZoom(newZoom);
        alphaRef.current = 1.0;
        return;
      }

      if (e.touches.length !== 1) return;
      e.preventDefault();
      const { x: screenX, y: screenY } = localPoint(e.touches[0]);
      // A gesture that started as a 2-finger pinch and dropped to 1 finger
      // has a stale/zero touchStartX/Y (only ever set in onTouchStart's
      // single-touch branch) — reset it here so the very next move doesn't
      // spuriously read as a large jump and swallow a tap-to-select.
      if (lastTouchCount !== 1) {
        touchStartX = screenX;
        touchStartY = screenY;
      }
      lastTouchCount = 1;
      if (Math.abs(screenX - touchStartX) > 4 || Math.abs(screenY - touchStartY) > 4) {
        touchMoved = true;
      }

      if (draggedNodeRef.current) {
        draggedNodeRef.current.x = (screenX - panRef.current.x) / zoomRef.current;
        draggedNodeRef.current.y = (screenY - panRef.current.y) / zoomRef.current;
        draggedNodeRef.current.vx = 0;
        draggedNodeRef.current.vy = 0;
        alphaRef.current = 1.0;
      } else if (isPanningRef.current) {
        setPan({
          x: e.touches[0].clientX - panStartRef.current.x,
          y: e.touches[0].clientY - panStartRef.current.y,
        });
      }
    };

    const onTouchEnd = (e: TouchEvent) => {
      // A tap (no drag) on a node selects it; on empty space clears selection.
      if (!touchMoved && e.touches.length === 0) {
        const dragged = draggedNodeRef.current;
        if (dragged) {
          setSelectedNodeId((prev) => (prev === dragged.id ? null : dragged.id));
          setHoveredNodeId(dragged.id);
          if (onNodeClick) onNodeClick(dragged.id);
        } else if (isPanningRef.current) {
          setSelectedNodeId(null);
          setHoveredNodeId(null);
        }
      }
      if (e.touches.length === 0) {
        draggedNodeRef.current = null;
        isPanningRef.current = false;
        lastTouchCount = 0;
        pinchStartDist = 0;
      }
    };

    canvas.addEventListener("touchstart", onTouchStart, { passive: false });
    canvas.addEventListener("touchmove", onTouchMove, { passive: false });
    canvas.addEventListener("touchend", onTouchEnd);
    canvas.addEventListener("touchcancel", onTouchEnd);
    return () => {
      canvas.removeEventListener("touchstart", onTouchStart);
      canvas.removeEventListener("touchmove", onTouchMove);
      canvas.removeEventListener("touchend", onTouchEnd);
      canvas.removeEventListener("touchcancel", onTouchEnd);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onNodeClick]);

  // Mouse handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;

    const worldX = (screenX - panRef.current.x) / zoomRef.current;
    const worldY = (screenY - panRef.current.y) / zoomRef.current;

    // Check if clicked a node
    const clickedNode = physicsNodesRef.current.find((node) => {
      const dist = Math.sqrt((node.x - worldX) ** 2 + (node.y - worldY) ** 2);
      return dist <= node.radius + 10;
    });

    if (clickedNode) {
      draggedNodeRef.current = clickedNode;
      setSelectedNodeId(clickedNode.id === selectedNodeId ? null : clickedNode.id);
      
      clickedNode.vx = 0;
      clickedNode.vy = 0;
      alphaRef.current = 1.0;

      if (onNodeClick) {
        onNodeClick(clickedNode.id);
      }
    } else {
      isPanningRef.current = true;
      panStartRef.current = { x: e.clientX - panRef.current.x, y: e.clientY - panRef.current.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;

    const worldX = (screenX - panRef.current.x) / zoomRef.current;
    const worldY = (screenY - panRef.current.y) / zoomRef.current;

    if (isPanningRef.current) {
      setPan({
        x: e.clientX - panStartRef.current.x,
        y: e.clientY - panStartRef.current.y,
      });
      return;
    }

    if (draggedNodeRef.current) {
      draggedNodeRef.current.x = worldX;
      draggedNodeRef.current.y = worldY;
      draggedNodeRef.current.vx = 0;
      draggedNodeRef.current.vy = 0;
      alphaRef.current = 1.0;
      return;
    }

    // Hover detection
    const hovered = physicsNodesRef.current.find((node) => {
      const dist = Math.sqrt((node.x - worldX) ** 2 + (node.y - worldY) ** 2);
      return dist <= node.radius + 10;
    });

    if (hovered?.id !== hoveredNodeId) {
      setHoveredNodeId(hovered ? hovered.id : null);
      alphaRef.current = 1.0; // reheat to update highlight frame
    }
  };

  const handleMouseUp = () => {
    draggedNodeRef.current = null;
    isPanningRef.current = false;
  };

  // Frame cluster viewport helper
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

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of pNodes) {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x > maxX) maxX = n.x;
      if (n.y > maxY) maxY = n.y;
    }

    const padding = 90;
    const bboxW = Math.max(maxX - minX, 1);
    const bboxH = Math.max(maxY - minY, 1);

    const fitZoom = Math.min(
      (width - padding * 2) / bboxW,
      (height - padding * 2) / bboxH
    );
    const newZoom = Math.max(0.18, Math.min(1.3, fitZoom));

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    setZoom(newZoom);
    setPan({
      x: width / 2 - centerX * newZoom,
      y: height / 2 - centerY * newZoom,
    });
    
    alphaRef.current = 1.0;
  };

  const activeFocusId = selectedNodeId || hoveredNodeId;
  const activeNodeInfo = nodes.find((n) => n.id === activeFocusId);

  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  const canvasWidth = dimensions.width * dpr;
  const canvasHeight = dimensions.height * dpr;

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full bg-[rgb(var(--bg))] select-none overflow-hidden theme-transition ${className}`}
    >
      {/* HTML5 Retina-ready Drawing Surface */}
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className="cursor-grab active:cursor-grabbing"
      />

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
        <span className="text-[10px] text-[rgb(var(--border))]/70">|</span>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`p-1 hover:bg-[rgb(var(--surface-hover))]/80 rounded-lg transition-all ${
            showSettings ? "text-[rgb(var(--accent))]" : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
          }`}
          title="Graph Settings"
        >
          <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>

      {/* 2. FLOATING SETTINGS MENU (Top Right, under Pill) */}
      {showSettings && (
        <div className="absolute top-14 right-3 w-[min(18rem,calc(100%-24px))] max-h-[calc(100%-70px)] overflow-y-auto z-20 bg-[rgb(var(--surface))]/85 backdrop-blur-lg border border-[rgb(var(--border))]/55 p-4 rounded-2xl shadow-2xl transition-all duration-300 animate-in fade-in slide-in-from-top-4 font-sans">
          <div className="flex items-center justify-between mb-3 border-b border-[rgb(var(--border))]/40 pb-2">
            <span className="text-xs font-bold tracking-wider uppercase text-[rgb(var(--text-primary))]">
              Graph Settings
            </span>
            <button
              onClick={() => setShowSettings(false)}
              className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-all text-xs"
            >
              Close
            </button>
          </div>

          <div className="space-y-4 text-left">
            {/* Display Settings */}
            <div>
              <span className="text-[10px] font-bold text-[rgb(var(--accent))] uppercase tracking-widest block mb-2 font-mono">
                Display
              </span>
              <div className="space-y-2.5">
                <label className="flex items-center justify-between text-xs text-[rgb(var(--text-muted))] cursor-pointer">
                  <span>Show Labels</span>
                  <select
                    value={settings.showLabels}
                    onChange={(e) => updateSetting("showLabels", e.target.value)}
                    className="bg-[rgb(var(--bg))]/55 border border-[rgb(var(--border))]/45 text-[10px] text-[rgb(var(--text-primary))] rounded px-1.5 py-0.5 outline-none font-sans font-medium"
                  >
                    <option value="all">All Nodes</option>
                    <option value="hover">Hover / Select</option>
                    <option value="none">None</option>
                  </select>
                </label>

                <label className="flex items-center justify-between text-xs text-[rgb(var(--text-muted))] cursor-pointer">
                  <span>Show Logo Icons</span>
                  <input
                    type="checkbox"
                    checked={settings.showIcons}
                    onChange={(e) => updateSetting("showIcons", e.target.checked)}
                    className="accent-[rgb(var(--accent))] cursor-pointer text-xs"
                  />
                </label>

                <label className="flex items-center justify-between text-xs text-[rgb(var(--text-muted))] cursor-pointer">
                  <span>Grid Background</span>
                  <input
                    type="checkbox"
                    checked={settings.showGrid}
                    onChange={(e) => updateSetting("showGrid", e.target.checked)}
                    className="accent-[rgb(var(--accent))] cursor-pointer"
                  />
                </label>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Base Node Size</span>
                    <span className="font-mono">{settings.nodeRadius}px</span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="10"
                    step="0.5"
                    value={settings.nodeRadius}
                    onChange={(e) => updateSetting("nodeRadius", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Link Opacity</span>
                    <span className="font-mono">{Math.round(settings.linkOpacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="0.8"
                    step="0.05"
                    value={settings.linkOpacity}
                    onChange={(e) => updateSetting("linkOpacity", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Flow Particle Speed</span>
                    <span className="font-mono">{settings.particleSpeed === 0 ? "Off" : `${settings.particleSpeed}x`}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="4"
                    step="0.5"
                    value={settings.particleSpeed}
                    onChange={(e) => updateSetting("particleSpeed", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>
              </div>
            </div>

            {/* Physics Forces */}
            <div className="border-t border-[rgb(var(--border))]/40 pt-3">
              <span className="text-[10px] font-bold text-[rgb(var(--accent))] uppercase tracking-widest block mb-2 font-mono">
                Physics Forces
              </span>
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Repulsion (Charge)</span>
                    <span className="font-mono">{settings.charge}</span>
                  </div>
                  <input
                    type="range"
                    min="200"
                    max="3000"
                    step="100"
                    value={settings.charge}
                    onChange={(e) => updateSetting("charge", parseInt(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Link Distance</span>
                    <span className="font-mono">{settings.linkDistance}px</span>
                  </div>
                  <input
                    type="range"
                    min="40"
                    max="200"
                    step="5"
                    value={settings.linkDistance}
                    onChange={(e) => updateSetting("linkDistance", parseInt(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Link Strength</span>
                    <span className="font-mono">{Math.round(settings.linkStrength * 1000) / 10}</span>
                  </div>
                  <input
                    type="range"
                    min="0.005"
                    max="0.15"
                    step="0.005"
                    value={settings.linkStrength}
                    onChange={(e) => updateSetting("linkStrength", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Center Gravity</span>
                    <span className="font-mono">{Math.round(settings.gravity * 1000) / 10}</span>
                  </div>
                  <input
                    type="range"
                    min="0.001"
                    max="0.06"
                    step="0.002"
                    value={settings.gravity}
                    onChange={(e) => updateSetting("gravity", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Collision</span>
                    <span className="font-mono">{settings.collision === 0 ? "Off" : `${Math.round(settings.collision * 100)}%`}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={settings.collision}
                    onChange={(e) => updateSetting("collision", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-[rgb(var(--text-muted))]">
                    <span>Friction</span>
                    <span className="font-mono">{Math.round((1 - settings.friction) * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.6"
                    max="0.97"
                    step="0.01"
                    value={settings.friction}
                    onChange={(e) => updateSetting("friction", parseFloat(e.target.value))}
                    className="w-full h-1 bg-[rgb(var(--bg))] rounded-lg appearance-none cursor-pointer accent-[rgb(var(--accent))]"
                  />
                </div>
              </div>
            </div>
            
            {/* Reset Button */}
            <button
              onClick={resetSettings}
              className="w-full py-1.5 mt-2 bg-[rgb(var(--surface-hover))]/65 border border-[rgb(var(--border))]/40 hover:bg-[rgb(var(--surface-hover))] text-[10px] font-sans font-bold text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] rounded-xl transition-all"
            >
              RESET TO DEFAULTS
            </button>
          </div>
        </div>
      )}

      {/* 3. FLOATING CONTEXT CARD (Bottom Left) */}
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
    </div>
  );
}

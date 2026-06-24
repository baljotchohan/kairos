"use client";

import React, { useId } from "react";

interface KairosLogoProps {
  className?: string;
  size?: number | string;
}

export default function KairosLogo({ className = "", size = "100%" }: KairosLogoProps) {
  const uid = useId().replace(/:/g, "");

  // Node positions carefully mapped to the reference "K" image:
  // Left vertical stem: top (28,14) → middle/junction (28,50) → bottom (28,86)
  // Junction connects right to hub (50,50)
  // Upper arm: hub (50,50) → mid-upper (66,32) → top-right (82,14)
  // Lower arm: hub (50,50) → mid-lower (66,68) → bottom-right (82,86)
  const nodes = [
    { cx: 28, cy: 14 },  // stem top
    { cx: 28, cy: 50 },  // stem middle (junction)
    { cx: 28, cy: 86 },  // stem bottom
    { cx: 50, cy: 50 },  // hub center
    { cx: 66, cy: 32 },  // upper arm mid
    { cx: 82, cy: 14 },  // upper arm tip
    { cx: 66, cy: 68 },  // lower arm mid
    { cx: 82, cy: 86 },  // lower arm tip
  ];

  const edges: [number, number][] = [
    [0, 1], // stem top → junction
    [1, 2], // junction → stem bottom
    [1, 3], // junction → hub
    [3, 4], // hub → upper mid
    [4, 5], // upper mid → upper tip
    [3, 6], // hub → lower mid
    [6, 7], // lower mid → lower tip
  ];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`${className} select-none`}
    >
      <defs>
        {/* 3D sphere gradient — highlight top-left */}
        <radialGradient id={`${uid}-node`} cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#d8b4fe" />
          <stop offset="40%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#7e22ce" />
        </radialGradient>

        {/* Subtle inner highlight for depth */}
        <radialGradient id={`${uid}-shine`} cx="40%" cy="30%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>

        {/* Edge gradient */}
        <linearGradient id={`${uid}-edge`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#c084fc" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>

        {/* Soft drop shadow */}
        <filter id={`${uid}-shadow`} x="-25%" y="-25%" width="150%" height="150%">
          <feDropShadow dx="1" dy="2" stdDeviation="2" floodColor="#4c1d95" floodOpacity="0.35" />
        </filter>
      </defs>

      {/* Connecting edges — drawn first so nodes sit on top */}
      <g stroke={`url(#${uid}-edge)`} strokeWidth="4" strokeLinecap="round" opacity="0.85">
        {edges.map(([a, b], i) => (
          <line
            key={i}
            x1={nodes[a].cx}
            y1={nodes[a].cy}
            x2={nodes[b].cx}
            y2={nodes[b].cy}
          />
        ))}
      </g>

      {/* Nodes — spherical circles with 3D shading */}
      <g filter={`url(#${uid}-shadow)`}>
        {nodes.map((n, i) => (
          <g key={i}>
            {/* Base sphere */}
            <circle cx={n.cx} cy={n.cy} r="8.5" fill={`url(#${uid}-node)`} />
            {/* Specular highlight overlay */}
            <circle cx={n.cx} cy={n.cy} r="8.5" fill={`url(#${uid}-shine)`} />
          </g>
        ))}
      </g>
    </svg>
  );
}

"use client";

import React, { useId } from "react";

interface KairosLogoProps {
  className?: string;
  size?: number | string;
  showText?: boolean;
}

export default function KairosLogo({ className = "", size = "100%", showText = false }: KairosLogoProps) {
  const uid = useId().replace(/:/g, "");

  // Node positions for the "K" constellation matching icon.svg exactly:
  const nodes = [
    { cx: 28, cy: 18 },  // 0: stem top
    { cx: 28, cy: 50 },  // 1: stem middle (junction)
    { cx: 28, cy: 82 },  // 2: stem bottom
    { cx: 48, cy: 50 },  // 3: intermediate hub (horizontal connectivity rod!)
    { cx: 63, cy: 35 },  // 4: upper arm mid
    { cx: 78, cy: 18 },  // 5: upper arm tip
    { cx: 63, cy: 65 },  // 6: lower arm mid
    { cx: 78, cy: 82 },  // 7: lower arm tip
  ];

  const edges: [number, number][] = [
    [0, 1], // stem top → junction
    [1, 2], // junction → stem bottom
    [1, 3], // junction → intermediate hub (horizontal connectivity rod!)
    [3, 4], // intermediate hub → upper arm mid
    [4, 5], // upper arm mid → upper arm tip
    [3, 6], // intermediate hub → lower arm mid
    [6, 7], // lower arm mid → lower arm tip
  ];

  // Widen viewBox when showing the full wordmark
  const viewBox = showText ? "0 0 280 100" : "0 0 100 100";

  // Parse size to calculate proportional width when showText is true
  const parsedSize = typeof size === "number" ? size : parseFloat(size);
  const heightVal = isNaN(parsedSize) ? size : parsedSize;
  const widthVal = showText 
    ? (isNaN(parsedSize) ? "auto" : parsedSize * 2.8)
    : size;

  return (
    <svg
      width={widthVal}
      height={heightVal}
      viewBox={viewBox}
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
      <g stroke={`url(#${uid}-edge)`} strokeWidth="2.5" strokeLinecap="round" opacity="0.85">
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
            <circle cx={n.cx} cy={n.cy} r="5" fill={`url(#${uid}-node)`} />
            {/* Specular highlight overlay */}
            <circle cx={n.cx} cy={n.cy} r="5" fill={`url(#${uid}-shine)`} />
          </g>
        ))}
      </g>

      {/* AIROS wordmark text — the K constellation acts as the 'K' */}
      {showText && (
        <text
          x="94"
          y="52"
          fill="currentColor"
          fontFamily="'Alice', serif"
          fontSize="38"
          fontWeight="bold"
          letterSpacing="0.2em"
          dominantBaseline="middle"
        >
          AIROS
        </text>
      )}
    </svg>
  );
}

"use client";

interface ConnectionStatusProps {
  isConnected: boolean;
  className?: string;
}

export default function ConnectionStatus({
  isConnected,
  className = "",
}: ConnectionStatusProps) {
  return (
    <div
      className={`flex items-center gap-1.5 text-xs font-medium ${className}`}
    >
      <span
        className={`relative flex h-2 w-2`}
      >
        {isConnected && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
        )}
        <span
          className={`relative inline-flex rounded-full h-2 w-2 ${
            isConnected ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
      </span>
      <span
        className={`${
          isConnected ? "text-emerald-500" : "text-red-400"
        } transition-colors duration-300`}
      >
        {isConnected ? "Connected" : "Reconnecting…"}
      </span>
    </div>
  );
}

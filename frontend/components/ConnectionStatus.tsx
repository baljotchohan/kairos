"use client";

interface ConnectionStatusProps {
  isConnected: boolean;
  exhausted?: boolean;
  onRetry?: () => void;
  className?: string;
}

export default function ConnectionStatus({
  isConnected,
  exhausted = false,
  onRetry,
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
            isConnected ? "bg-emerald-500" : exhausted ? "bg-amber-500" : "bg-red-500"
          }`}
        />
      </span>
      <span
        className={`${
          isConnected ? "text-emerald-500" : exhausted ? "text-amber-400" : "text-red-400"
        } transition-colors duration-300`}
      >
        {isConnected ? "Connected" : exhausted ? "Connection lost" : "Reconnecting…"}
      </span>
      {!isConnected && exhausted && onRetry && (
        <button
          onClick={onRetry}
          className="ml-1 text-[11px] font-semibold text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

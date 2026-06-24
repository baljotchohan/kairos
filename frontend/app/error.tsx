"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("KAIROS client error:", error);
  }, [error]);

  return (
    <div className="flex h-full w-full items-center justify-center bg-[#171717] text-[#ececec] p-6">
      <div className="max-w-sm w-full rounded-2xl border border-[#2c2c2e] bg-[#212121] p-6 text-center flex flex-col gap-4 animate-pop-in">
        <div className="mx-auto w-11 h-11 rounded-full bg-rose-500/15 text-rose-400 flex items-center justify-center text-xl">
          !
        </div>
        <div className="space-y-1.5">
          <h2 className="text-base font-bold tracking-tight">Something went wrong</h2>
          <p className="text-xs text-[#b4b4b4] leading-relaxed">
            KAIROS hit an unexpected error while loading. Your data is safe — try
            reloading the console.
          </p>
        </div>
        <button
          onClick={reset}
          className="w-full py-2.5 px-4 bg-[#7c3aed] hover:opacity-90 rounded-xl text-xs font-semibold transition-all active:scale-95"
        >
          Reload KAIROS
        </button>
        {error?.digest && (
          <p className="text-[9px] font-mono text-[#6b6b6b]">ref: {error.digest}</p>
        )}
      </div>
    </div>
  );
}

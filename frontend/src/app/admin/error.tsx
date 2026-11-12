"use client";
import { ErrorState } from "@/components/ui";
export default function AdminError({ reset }: { reset: () => void }) {
  return (
    <div className="container page-shell">
      <ErrorState
        message="The administrator workspace is temporarily unavailable. Check that the API is healthy, then try again."
        retry={reset}
      />
    </div>
  );
}

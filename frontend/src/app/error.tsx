"use client";
import { ErrorState } from "@/components/ui";
export default function PageError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="container page-shell">
      <ErrorState
        message="We couldn’t reach the service. Check that the application is running, then try again."
        retry={reset}
      />
    </div>
  );
}

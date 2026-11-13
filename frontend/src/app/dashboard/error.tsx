"use client";
import { ErrorState } from "@/components/ui";
export default function Error({ reset }: { reset: () => void }) {
  return (
    <ErrorState
      message="Your workspace could not be loaded. Please retry or sign in again."
      retry={reset}
    />
  );
}

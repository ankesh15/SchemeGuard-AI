import { LoadingState } from "@/components/ui";
export default function Loading() {
  return (
    <div className="container page-shell">
      <LoadingState message="Getting things ready…" />
    </div>
  );
}

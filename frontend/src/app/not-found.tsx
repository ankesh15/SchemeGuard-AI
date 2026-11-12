import { ActionLink } from "@/components/ui";
export default function NotFound() {
  return (
    <div className="container page-shell empty-state">
      <h1>This page couldn’t be found.</h1>
      <p>The scheme or page may not exist.</p>
      <ActionLink href="/schemes">Explore schemes</ActionLink>
    </div>
  );
}

import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, PageHeader } from "../components";

export function NotFoundPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="404"
        title="Page not found"
        description="That page does not exist or may have moved."
      />
      <Card tone="muted" className="state">
        <span className="state__icon" aria-hidden="true">
          <ArrowLeft size={22} />
        </span>
        <h2 className="state__title">Return Home</h2>
        <p className="state__description">
          Your local documents and study history have not been changed.
        </p>
        <Link className="button button--primary state__action" to="/">
          Go Home
        </Link>
      </Card>
    </div>
  );
}

export default NotFoundPage;

export function FreshnessBadge({ freshness }) {
  const map = {
    fresh: { label: "Fresh", cls: "badge-good" },
    aging: { label: "Aging", cls: "badge-warn" },
    stale: { label: "Stale", cls: "badge-bad" },
    missing: { label: "No evidence", cls: "badge-bad" },
  };
  const m = map[freshness] || { label: freshness, cls: "badge-neutral" };
  return <span className={`badge ${m.cls}`}>{m.label}</span>;
}

export function StatusBadge({ status }) {
  const map = {
    planned: { label: "Planned", cls: "badge-neutral" },
    in_progress: { label: "In progress", cls: "badge-warn" },
    completed: { label: "Completed", cls: "badge-good" },
  };
  const m = map[status] || { label: status, cls: "badge-neutral" };
  return <span className={`badge ${m.cls}`}>{m.label}</span>;
}

export function FlagBadge({ children, tone = "bad" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

const SOURCE_LABEL = {
  automated_scan: "an automated scan",
  third_party_audit: "a third-party audit",
  manual_attestation: "a manual attestation",
};

export function sourceLabel(source) {
  return SOURCE_LABEL[source] || source;
}

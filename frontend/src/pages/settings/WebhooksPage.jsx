import { useEffect, useState } from "react";
import Card from "../../components/Card";
import ErrorBanner from "../../components/ErrorBanner";
import {
  createWebhookSubscription,
  deleteWebhookSubscription,
  listWebhookDeliveries,
  listWebhookSubscriptions,
} from "../../services/webhooksApi";
import { extractErrorMessage } from "../../utils/apiError";

const EVENT_TYPES = [
  { value: "lead.created", label: "Lead created" },
  { value: "lead.stage_changed", label: "Lead stage changed" },
  { value: "conversation.human_handoff", label: "Conversation escalated to human" },
  { value: "appointment.booked", label: "Appointment booked" },
  { value: "appointment.cancelled", label: "Appointment cancelled" },
];

export default function WebhooksPage() {
  const [subscriptions, setSubscriptions] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [revealedSecret, setRevealedSecret] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reload = () =>
    Promise.all([listWebhookSubscriptions(), listWebhookDeliveries()]).then(([subs, dels]) => {
      setSubscriptions(subs);
      setDeliveries(dels);
    });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const toggleEvent = (value) => {
    setSelectedEvents((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await createWebhookSubscription({ url, event_types: selectedEvents });
      setRevealedSecret(created.secret);
      setUrl("");
      setSelectedEvents([]);
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this webhook subscription?")) return;
    await deleteWebhookSubscription(id);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>Webhooks</h1>
      <p className="page-subtitle">
        Notify your own systems (CRM, Zapier, Slack) when things happen on your account — a new lead, an
        appointment, or an escalation to a human.
      </p>

      {revealedSecret && (
        <Card className="api-key-reveal">
          <p>
            <strong>Copy this signing secret now — it won't be shown again.</strong>
          </p>
          <code className="api-key-value">{revealedSecret}</code>
          <p className="text-muted">
            Every delivery includes an <code>X-Ectama-Signature: sha256=...</code> header — an HMAC-SHA256 of the
            raw request body using this secret. Verify it before trusting a payload.
          </p>
          <button className="btn btn-ghost" onClick={() => setRevealedSecret(null)}>
            Done, I've copied it
          </button>
        </Card>
      )}

      <Card title="Add a webhook endpoint">
        <ErrorBanner message={error} />
        <form onSubmit={handleCreate} className="knowledge-form">
          <div className="form-field">
            <label className="form-label">Endpoint URL</label>
            <input
              type="url"
              required
              placeholder="https://your-system.example.com/webhooks/ectama"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label">Events (leave none selected for all events)</label>
            {EVENT_TYPES.map((event) => (
              <label key={event.value} style={{ display: "block" }}>
                <input
                  type="checkbox"
                  checked={selectedEvents.includes(event.value)}
                  onChange={() => toggleEvent(event.value)}
                />{" "}
                {event.label}
              </label>
            ))}
          </div>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Creating…" : "Add Webhook"}
          </button>
        </form>
      </Card>

      <Card title="Your webhooks">
        {subscriptions.length === 0 ? (
          <p>No webhooks configured yet.</p>
        ) : (
          <ul className="entity-list">
            {subscriptions.map((sub) => (
              <li key={sub.id}>
                <div>
                  <strong>{sub.url}</strong>
                  <span className={`badge badge-${sub.is_active ? "active" : "disabled"}`}>
                    {sub.is_active ? "active" : "disabled"}
                  </span>
                  <div className="text-muted">
                    {sub.event_types.length === 0 ? "All events" : sub.event_types.join(", ")}
                  </div>
                </div>
                <button className="btn btn-ghost" onClick={() => handleDelete(sub.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Recent deliveries">
        {deliveries.length === 0 ? (
          <p>No deliveries yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Response</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((d) => (
                  <tr key={d.id}>
                    <td>{d.event_type}</td>
                    <td>
                      <span className={`badge badge-${d.status}`}>{d.status}</span>
                    </td>
                    <td>{d.attempt_count}</td>
                    <td>{d.response_status_code ?? "—"}</td>
                    <td>{new Date(d.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

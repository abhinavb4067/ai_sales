import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { listAgents } from "../../services/agentsApi";
import { createIntegration, deleteIntegration, listIntegrations } from "../../services/integrationsApi";
import { API_BASE_URL } from "../../services/apiClient";

const EMPTY_FORM = {
  agent: "",
  external_account_id: "",
  access_token: "",
  app_secret: "",
  verify_token: "",
};

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  const reload = () => Promise.all([listIntegrations(), listAgents()]).then(([i, a]) => {
    setIntegrations(i);
    setAgents(a);
  });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleChange = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createIntegration({
        agent: form.agent,
        provider: "whatsapp",
        external_account_id: form.external_account_id,
        credentials: {
          access_token: form.access_token,
          app_secret: form.app_secret,
          verify_token: form.verify_token,
        },
      });
      setForm(EMPTY_FORM);
      await reload();
    } catch (err) {
      setError(err.response?.data?.error?.message || "Could not create integration.");
    }
  };

  const handleDelete = async (id) => {
    await deleteIntegration(id);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>Integrations</h1>
      <p className="page-subtitle">Connect an agent to an external channel. WhatsApp Cloud API is supported today.</p>

      <Card title="Connect WhatsApp">
        <form className="agent-form" onSubmit={handleCreate}>
          {error && <div className="form-error">{error}</div>}
          <div className="form-field">
            <label className="form-label">Agent</label>
            <select value={form.agent} onChange={handleChange("agent")} required>
              <option value="">Select an agent…</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">WhatsApp phone_number_id</label>
            <input value={form.external_account_id} onChange={handleChange("external_account_id")} required />
          </div>
          <div className="form-field">
            <label className="form-label">Access token</label>
            <input value={form.access_token} onChange={handleChange("access_token")} required />
          </div>
          <div className="form-field">
            <label className="form-label">App secret</label>
            <input value={form.app_secret} onChange={handleChange("app_secret")} required />
          </div>
          <div className="form-field">
            <label className="form-label">Verify token</label>
            <input value={form.verify_token} onChange={handleChange("verify_token")} required />
            <span className="text-muted">Choose any string — you'll enter this same value in the Meta webhook setup.</span>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">Connect</button>
          </div>
        </form>
      </Card>

      <Card>
        {integrations.length === 0 ? (
          <p>No integrations connected yet.</p>
        ) : (
          <ul className="entity-list">
            {integrations.map((i) => (
              <li key={i.id}>
                <div>
                  <strong>{i.provider}</strong> — {i.external_account_id}
                  <span className={`badge badge-${i.status === "active" ? "active" : "disabled"}`}>{i.status}</span>
                  <div className="text-muted">Webhook URL: {API_BASE_URL.replace(/\/api\/v1\/?$/, "")}{i.webhook_url_path}</div>
                </div>
                <button className="btn btn-ghost" onClick={() => handleDelete(i.id)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

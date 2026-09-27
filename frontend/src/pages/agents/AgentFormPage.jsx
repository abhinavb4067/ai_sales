import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Button from "../../components/Button";
import Card from "../../components/Card";
import ErrorBanner from "../../components/ErrorBanner";
import FormField from "../../components/FormField";
import { createAgent, deleteAgent, getAgent, updateAgent } from "../../services/agentsApi";
import { API_BASE_URL } from "../../services/apiClient";
import { extractErrorMessage } from "../../utils/apiError";

const AGENT_TYPES = ["sales", "support", "combined"];
const GOALS = ["sales", "customer_support", "sales_and_support", "lead_generation", "information"];
const TONES = ["professional", "friendly", "casual", "formal"];
const STATUSES = ["draft", "active", "disabled"];

const DEFAULT_FORM = {
  name: "",
  description: "",
  agent_type: "combined",
  primary_goal: "sales_and_support",
  tone: "professional",
  language: "en",
  status: "draft",
  system_prompt: "",
  greeting: "",
  model: "gpt-4o-mini",
  temperature: 0.4,
  max_tokens: 800,
};

function buildEmbedSnippet(widgetId) {
  const siteOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
  return (
    `<script\n` +
    `  src="${siteOrigin}/static/widget/widget.js"\n` +
    `  data-widget-id="${widgetId}"\n` +
    `  data-api-base="${siteOrigin}/api/v1"\n` +
    `  async\n` +
    `></script>`
  );
}

export default function AgentFormPage() {
  const { id } = useParams();
  const isEditing = Boolean(id) && id !== "new";
  const navigate = useNavigate();

  const [form, setForm] = useState(DEFAULT_FORM);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEditing);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isEditing) {
      getAgent(id)
        .then((agent) => setForm({ ...DEFAULT_FORM, ...agent }))
        .finally(() => setLoading(false));
    }
  }, [id, isEditing]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm({ ...form, [name]: name === "temperature" || name === "max_tokens" ? Number(value) : value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isEditing) {
        await updateAgent(id, form);
      } else {
        const created = await createAgent(form);
        navigate(`/agents/${created.id}`);
        return;
      }
      navigate("/agents");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Delete this agent? This cannot be undone.")) return;
    await deleteAgent(id);
    navigate("/agents");
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>{isEditing ? "Configure Agent" : "New Agent"}</h1>
      <form onSubmit={handleSubmit} className="agent-form">
        <ErrorBanner message={error} />

        <Card title="Identity">
          <FormField label="Agent name">
            <input name="name" required value={form.name} onChange={handleChange} />
          </FormField>
          <FormField label="Business / product description">
            <textarea name="description" rows={3} value={form.description} onChange={handleChange} />
          </FormField>
          <FormField label="Status">
            <select name="status" value={form.status} onChange={handleChange}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FormField>
        </Card>

        <Card title="Goals & Behavior">
          <FormField label="Agent type">
            <select name="agent_type" value={form.agent_type} onChange={handleChange}>
              {AGENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Primary goal">
            <select name="primary_goal" value={form.primary_goal} onChange={handleChange}>
              {GOALS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Tone">
            <select name="tone" value={form.tone} onChange={handleChange}>
              {TONES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Language (ISO code, e.g. en, hi, ar)">
            <input name="language" value={form.language} onChange={handleChange} />
          </FormField>
        </Card>

        <Card title="Personality & Instructions">
          <FormField label="Greeting message">
            <textarea name="greeting" rows={2} value={form.greeting} onChange={handleChange} />
          </FormField>
          <FormField label="Custom instructions (rendered as agent configuration — cannot override platform safety rules)">
            <textarea name="system_prompt" rows={4} value={form.system_prompt} onChange={handleChange} />
          </FormField>
        </Card>

        <Card title="Model Settings">
          <FormField label="Model">
            <input name="model" value={form.model} onChange={handleChange} />
          </FormField>
          <FormField label="Temperature (0–2)">
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              name="temperature"
              value={form.temperature}
              onChange={handleChange}
            />
          </FormField>
          <FormField label="Max response tokens">
            <input
              type="number"
              min="1"
              max="4000"
              name="max_tokens"
              value={form.max_tokens}
              onChange={handleChange}
            />
          </FormField>
        </Card>

        {isEditing && form.public_widget_id && (
          <Card title="Embed on your website">
            <p className="text-muted">
              Paste this snippet before <code>&lt;/body&gt;</code> on your site to add a live chat bubble powered by
              this agent. No API key is exposed — the widget ID is a public identifier.
            </p>
            <pre className="embed-snippet">{buildEmbedSnippet(form.public_widget_id)}</pre>
          </Card>
        )}

        <div className="form-actions">
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : "Save Agent"}
          </Button>
          {isEditing && (
            <Button type="button" variant="danger" onClick={handleDelete}>
              Delete Agent
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import Card from "../../components/Card";
import { listAgents } from "../../services/agentsApi";
import {
  completeWhatsAppEmbeddedSignup,
  createIntegration,
  deleteIntegration,
  listIntegrations,
} from "../../services/integrationsApi";
import { API_BASE_URL } from "../../services/apiClient";

const META_APP_ID = import.meta.env.VITE_WHATSAPP_META_APP_ID;
const META_CONFIG_ID = import.meta.env.VITE_WHATSAPP_META_CONFIG_ID;

function loadFacebookSdk(appId) {
  return new Promise((resolve) => {
    if (window.FB) {
      resolve(window.FB);
      return;
    }
    window.fbAsyncInit = function () {
      window.FB.init({ appId, version: "v19.0" });
      resolve(window.FB);
    };
    const script = document.createElement("script");
    script.src = "https://connect.facebook.net/en_US/sdk.js";
    script.async = true;
    document.body.appendChild(script);
  });
}

/** Embedded Signup hands back the WABA/phone number via a postMessage
 * event (not FB.login's own callback) — this listens for exactly that,
 * per Meta's documented flow, and ignores anything else on the page. */
function waitForEmbeddedSignupDetails() {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      window.removeEventListener("message", handler);
      reject(new Error("Timed out waiting for WhatsApp to confirm the connection."));
    }, 60000);

    function handler(event) {
      if (!event.origin.endsWith("facebook.com")) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === "WA_EMBEDDED_SIGNUP" && data.event === "FINISH") {
          clearTimeout(timeout);
          window.removeEventListener("message", handler);
          resolve(data.data);
        }
      } catch {
        // Not a JSON message we understand — ignore, keep listening.
      }
    }
    window.addEventListener("message", handler);
  });
}

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
  const [signupAgent, setSignupAgent] = useState("");
  const [signupBusy, setSignupBusy] = useState(false);
  const signupCode = useRef(null);

  const reload = () => Promise.all([listIntegrations(), listAgents()]).then(([i, a]) => {
    setIntegrations(i);
    setAgents(a);
  });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleChange = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleEmbeddedSignup = async () => {
    if (!signupAgent) {
      setError("Choose which agent should handle this WhatsApp number first.");
      return;
    }
    setError("");
    setSignupBusy(true);
    try {
      const FB = await loadFacebookSdk(META_APP_ID);
      const detailsPromise = waitForEmbeddedSignupDetails();
      FB.login(
        (response) => {
          signupCode.current = response?.authResponse?.code || null;
        },
        {
          config_id: META_CONFIG_ID,
          response_type: "code",
          override_default_response_type: true,
        }
      );
      const details = await detailsPromise;
      if (!signupCode.current) throw new Error("Facebook login did not return an authorization code.");

      await completeWhatsAppEmbeddedSignup({
        agentId: signupAgent,
        code: signupCode.current,
        wabaId: details.waba_id,
        phoneNumberId: details.phone_number_id,
      });
      await reload();
    } catch (err) {
      setError(err.message || err.response?.data?.detail || "Could not complete the WhatsApp connection.");
    } finally {
      setSignupBusy(false);
      signupCode.current = null;
    }
  };

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

      {META_APP_ID && META_CONFIG_ID && (
        <Card title="Connect WhatsApp with Facebook">
          <p className="text-muted">
            Connect your own WhatsApp Business number in a few clicks — no technical setup required.
          </p>
          {error && <div className="form-error">{error}</div>}
          <div className="form-field">
            <label className="form-label">Agent to handle this number</label>
            <select value={signupAgent} onChange={(e) => setSignupAgent(e.target.value)}>
              <option value="">Select an agent…</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <button type="button" className="btn btn-primary" onClick={handleEmbeddedSignup} disabled={signupBusy}>
            {signupBusy ? "Connecting…" : "Connect with Facebook"}
          </button>
        </Card>
      )}

      <Card title="Connect WhatsApp manually">
        <p className="text-muted">
          Already have a WhatsApp Business API account? Paste its credentials directly.
        </p>
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

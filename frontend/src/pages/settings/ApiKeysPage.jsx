import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { createApiKey, listApiKeys, revokeApiKey } from "../../services/apiKeysApi";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState("");
  const [revealedKey, setRevealedKey] = useState(null);

  const reload = () => listApiKeys().then(setKeys);

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    const created = await createApiKey(newKeyName.trim());
    setRevealedKey(created.key);
    setNewKeyName("");
    await reload();
  };

  const handleRevoke = async (id) => {
    await revokeApiKey(id);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>API Keys</h1>
      <p className="page-subtitle">
        Use a key with the public Chat API (<code>Authorization: Bearer &lt;key&gt;</code>) to talk to your agents
        from your own backend or integrations.
      </p>

      {revealedKey && (
        <Card className="api-key-reveal">
          <p>
            <strong>Copy this key now — it won't be shown again.</strong>
          </p>
          <code className="api-key-value">{revealedKey}</code>
          <div>
            <button className="btn btn-ghost" onClick={() => setRevealedKey(null)}>
              Done, I've copied it
            </button>
          </div>
        </Card>
      )}

      <Card title="Create a new key">
        <form className="inline-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder="Key name (e.g. Zapier integration)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Generate key
          </button>
        </form>
      </Card>

      <Card>
        {keys.length === 0 ? (
          <p>No API keys yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Prefix</th>
                  <th>Status</th>
                  <th>Last used</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id}>
                    <td>{key.name}</td>
                    <td>
                      <code>{key.prefix}...</code>
                    </td>
                    <td>{key.status}</td>
                    <td>{key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}</td>
                    <td>{new Date(key.created_at).toLocaleDateString()}</td>
                    <td>
                      {key.status === "active" && (
                        <button className="btn btn-ghost" onClick={() => handleRevoke(key.id)}>
                          Revoke
                        </button>
                      )}
                    </td>
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

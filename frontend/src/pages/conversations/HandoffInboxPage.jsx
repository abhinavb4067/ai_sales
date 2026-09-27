import { useEffect, useState } from "react";
import Button from "../../components/Button";
import Card from "../../components/Card";
import { listConversations, resolveConversation, takeoverConversation } from "../../services/conversationsApi";

export default function HandoffInboxPage() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);

  const reload = () => listConversations({ status: "human_handoff" }).then(setConversations);

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleTakeover = async (id) => {
    await takeoverConversation(id);
    await reload();
  };

  const handleResolve = async (id) => {
    await resolveConversation(id);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>Human Handoff</h1>
      <p className="page-subtitle">Conversations that need a person to step in.</p>

      <Card>
        {conversations.length === 0 ? (
          <p>Nothing needs your attention right now.</p>
        ) : (
          <ul className="entity-list">
            {conversations.map((c) => (
              <li key={c.id}>
                <div>
                  <strong>Conversation #{c.id}</strong>
                  <span className="badge">{c.channel}</span>
                </div>
                <div className="card-actions-row">
                  <Button variant="secondary" onClick={() => handleTakeover(c.id)}>
                    Take over
                  </Button>
                  <Button variant="primary" onClick={() => handleResolve(c.id)}>
                    Resolve
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

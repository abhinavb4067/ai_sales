import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Card from "../../components/Card";
import { listAgents } from "../../services/agentsApi";

export default function AgentsListPage() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Agents</h1>
        <Link className="btn btn-primary" to="/agents/new">
          + New Agent
        </Link>
      </div>

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : (
        <div className="card-grid">
          {agents.map((agent) => (
            <Card key={agent.id} title={agent.name}>
              <p className="text-muted">{agent.description || "No description yet."}</p>
              <div className="tag-row">
                <span className="badge">{agent.agent_type}</span>
                <span className="badge">{agent.primary_goal}</span>
                <span className={`badge badge-${agent.status}`}>{agent.status}</span>
              </div>
              <div className="card-actions-row">
                <Link className="btn btn-secondary" to={`/agents/${agent.id}`}>
                  Configure
                </Link>
                <Link className="btn btn-primary" to={`/agents/${agent.id}/playground`}>
                  Test
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

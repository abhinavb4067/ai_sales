import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Card from "../../components/Card";
import { listAgents } from "../../services/agentsApi";
import { fetchCurrentBusiness } from "../../services/businessApi";

export default function DashboardPage() {
  const [business, setBusiness] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchCurrentBusiness(), listAgents()])
      .then(([biz, agentList]) => {
        setBusiness(biz);
        setAgents(agentList);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>{business?.name}</h1>
      <p className="page-subtitle">Welcome back. Here's a snapshot of your AI agents.</p>

      <div className="stat-row">
        <Card title="Agents">
          <div className="stat-number">{agents.length}</div>
        </Card>
        <Card title="Active Agents">
          <div className="stat-number">{agents.filter((a) => a.status === "active").length}</div>
        </Card>
      </div>

      <Card
        title="Your Agents"
        actions={
          <Link className="btn btn-primary" to="/agents/new">
            + New Agent
          </Link>
        }
      >
        {agents.length === 0 ? (
          <p>No agents yet. Create your first AI agent to get started.</p>
        ) : (
          <ul className="entity-list">
            {agents.map((agent) => (
              <li key={agent.id}>
                <Link to={`/agents/${agent.id}`}>{agent.name}</Link>
                <span className={`badge badge-${agent.status}`}>{agent.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

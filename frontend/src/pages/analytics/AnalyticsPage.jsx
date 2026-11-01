import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { fetchAnalyticsOverview } from "../../services/analyticsApi";

export default function AnalyticsPage() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalyticsOverview(30)
      .then(setOverview)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">Loading…</div>;
  if (!overview) return null;

  const usage = overview.usage_against_plan;

  return (
    <div className="page">
      <h1>Analytics</h1>
      <p className="page-subtitle">Last {overview.window_days} days across all your agents and channels.</p>

      <div className="stat-row">
        <Card title="Total Conversations">
          <div className="stat-number">{overview.total_conversations}</div>
        </Card>
        <Card title="Active Conversations">
          <div className="stat-number">{overview.active_conversations}</div>
        </Card>
        <Card title="Awaiting Human">
          <div className="stat-number">{overview.human_handoff_conversations}</div>
        </Card>
        <Card title="Leads Captured">
          <div className="stat-number">{overview.leads_captured_last_window}</div>
        </Card>
        <Card title="Qualified Leads">
          <div className="stat-number">{overview.qualified_leads_last_window}</div>
        </Card>
        <Card title="Upcoming Appointments">
          <div className="stat-number">{overview.appointments_upcoming}</div>
        </Card>
        <Card title="Customer Satisfaction">
          <div className="stat-number">
            {overview.csat.satisfaction_rate != null ? `${Math.round(overview.csat.satisfaction_rate * 100)}%` : "—"}
          </div>
          <p className="text-muted">
            {overview.csat.thumbs_up} 👍 / {overview.csat.thumbs_down} 👎
          </p>
        </Card>
      </div>

      <Card title="Channel Breakdown">
        {Object.keys(overview.channel_breakdown).length === 0 ? (
          <p>No conversations in this window yet.</p>
        ) : (
          <ul className="entity-list">
            {Object.entries(overview.channel_breakdown).map(([channel, count]) => (
              <li key={channel}>
                <strong>{channel}</strong>
                <span className="badge">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="AI Usage">
        <p>
          {overview.ai_input_tokens_last_window.toLocaleString()} input tokens /{" "}
          {overview.ai_output_tokens_last_window.toLocaleString()} output tokens
        </p>
        {usage && (
          <p className="text-muted">
            Plan: {usage.plan} — {usage.messages_used}
            {usage.messages_limit != null ? ` / ${usage.messages_limit}` : ""} messages used this billing period.
          </p>
        )}
      </Card>
    </div>
  );
}

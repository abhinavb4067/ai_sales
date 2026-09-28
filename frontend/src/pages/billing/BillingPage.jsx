import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { changePlan, getSubscription, listPlans } from "../../services/billingApi";

export default function BillingPage() {
  const [subscription, setSubscription] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(null);

  const reload = () => Promise.all([getSubscription(), listPlans()]).then(([sub, planList]) => {
    setSubscription(sub);
    setPlans(planList);
  });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleSwitch = async (planCode) => {
    setSwitching(planCode);
    try {
      await changePlan(planCode);
      await reload();
    } finally {
      setSwitching(null);
    }
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  const limit = subscription.plan.max_messages_per_month;
  const used = subscription.messages_used_this_period;
  const usagePct = limit ? Math.min(100, Math.round((used / limit) * 100)) : null;

  return (
    <div className="page">
      <h1>Billing</h1>
      <p className="page-subtitle">Your subscription, plan limits, and current usage.</p>

      <Card title="Current plan">
        <div className="stat-row">
          <div>
            <div className="stat-number">{subscription.plan.name}</div>
            <span className={`badge badge-${subscription.status === "active" || subscription.status === "trial" ? "active" : "disabled"}`}>
              {subscription.status}
            </span>
          </div>
          <div>
            <div className="stat-number">
              {used}
              {limit ? ` / ${limit}` : ""}
            </div>
            <div className="text-muted">Messages used this period</div>
          </div>
        </div>
        {usagePct !== null && (
          <div className="usage-bar">
            <div className="usage-bar-fill" style={{ width: `${usagePct}%` }} />
          </div>
        )}
        {subscription.trial_ends_at && subscription.status === "trial" && (
          <p className="text-muted">Trial ends {new Date(subscription.trial_ends_at).toLocaleDateString()}</p>
        )}
      </Card>

      <Card title="Available plans">
        <div className="card-grid">
          {plans.map((plan) => (
            <Card key={plan.code} className={plan.code === subscription.plan.code ? "plan-current" : ""}>
              <h3>{plan.name}</h3>
              <p className="text-muted">{plan.description}</p>
              <p className="stat-number">
                ${plan.monthly_price}
                <span className="text-muted"> /mo</span>
              </p>
              <ul className="entity-list">
                <li>{plan.max_agents ?? "Unlimited"} agents</li>
                <li>{plan.max_messages_per_month ?? "Unlimited"} messages/mo</li>
                <li>{plan.max_knowledge_documents ?? "Unlimited"} knowledge docs</li>
              </ul>
              <button
                className="btn btn-primary"
                disabled={plan.code === subscription.plan.code || switching === plan.code}
                onClick={() => handleSwitch(plan.code)}
              >
                {plan.code === subscription.plan.code ? "Current plan" : switching === plan.code ? "Switching…" : "Switch to this plan"}
              </button>
            </Card>
          ))}
        </div>
      </Card>
    </div>
  );
}

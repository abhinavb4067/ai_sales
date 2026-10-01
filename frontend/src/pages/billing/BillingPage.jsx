import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { cancelSubscription, changePlan, getSubscription, listPlans } from "../../services/billingApi";

function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = resolve;
    script.onerror = () => reject(new Error("Could not load Razorpay checkout."));
    document.body.appendChild(script);
  });
}

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
      const result = await changePlan(planCode);

      // Manual provider activates instantly — nothing further to do.
      // A real gateway (Razorpay) only starts a checkout here; the
      // subscription itself updates later once its webhook fires.
      if (result.type === "checkout") {
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
          return;
        }
        if (result.client_data?.razorpay_subscription_id) {
          await loadRazorpayScript();
          const checkout = new window.Razorpay({
            key: result.client_data.key_id,
            subscription_id: result.client_data.razorpay_subscription_id,
            name: "Subscription",
            handler: () => reload(),
          });
          checkout.open();
        }
        return;
      }

      await reload();
    } finally {
      setSwitching(null);
    }
  };

  const handleCancel = async () => {
    await cancelSubscription();
    await reload();
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
        {!subscription.cancel_at_period_end && subscription.status !== "cancelled" && (
          <button className="btn btn-ghost" onClick={handleCancel}>
            Cancel subscription
          </button>
        )}
        {subscription.cancel_at_period_end && <p className="text-muted">Cancellation requested.</p>}
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

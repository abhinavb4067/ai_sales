import { useEffect, useState } from "react";
import Card from "../../components/Card";
import { changeLeadStage, listLeadStages, listLeads } from "../../services/leadsApi";

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [stages, setStages] = useState([]);
  const [loading, setLoading] = useState(true);

  const reload = () => Promise.all([listLeads(), listLeadStages()]).then(([l, s]) => {
    setLeads(l);
    setStages(s);
  });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleStageChange = async (leadId, stageId) => {
    await changeLeadStage(leadId, stageId);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>Leads</h1>
      <p className="page-subtitle">Captured by your AI agents during conversations.</p>

      <Card>
        {leads.length === 0 ? (
          <p>No leads captured yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Company</th>
                  <th>Score</th>
                  <th>Stage</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.name || "—"}</td>
                    <td>{lead.email || "—"}</td>
                    <td>{lead.company || "—"}</td>
                    <td>{lead.score}</td>
                    <td>
                      <select value={lead.stage} onChange={(e) => handleStageChange(lead.id, e.target.value)}>
                        {stages.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>{new Date(lead.created_at).toLocaleDateString()}</td>
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

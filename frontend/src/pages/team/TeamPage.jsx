import { useEffect, useState } from "react";
import Card from "../../components/Card";
import {
  acceptInvite,
  changeMemberRole,
  inviteMember,
  listMembers,
  listMyInvites,
  revokeMember,
} from "../../services/teamApi";

const ROLES = ["admin", "sales", "support", "viewer"];

export default function TeamPage() {
  const [members, setMembers] = useState([]);
  const [myInvites, setMyInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("sales");
  const [error, setError] = useState(null);

  const reload = () =>
    Promise.all([listMembers(), listMyInvites()]).then(([memberList, invites]) => {
      setMembers(memberList);
      setMyInvites(invites);
    });

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleInvite = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await inviteMember(email, role);
      setEmail("");
      await reload();
    } catch (err) {
      setError(err.response?.data?.error?.message || "Could not send invite.");
    }
  };

  const handleRevoke = async (id) => {
    await revokeMember(id);
    await reload();
  };

  const handleRoleChange = async (id, newRole) => {
    await changeMemberRole(id, newRole);
    await reload();
  };

  const handleAccept = async (id) => {
    await acceptInvite(id);
    await reload();
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1>Team</h1>
      <p className="page-subtitle">Invite teammates and manage who can access this business.</p>

      {myInvites.length > 0 && (
        <Card title="Invites waiting for you">
          <ul className="entity-list">
            {myInvites.map((invite) => (
              <li key={invite.id}>
                <div>
                  <strong>{invite.business_name}</strong>
                  <span className="badge">{invite.role}</span>
                </div>
                <button className="btn btn-primary" onClick={() => handleAccept(invite.id)}>
                  Accept
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Invite a team member">
        <form className="inline-form" onSubmit={handleInvite}>
          <input
            type="email"
            placeholder="teammate@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary">
            Send invite
          </button>
        </form>
        {error && <p className="form-error">{error}</p>}
        <p className="text-muted">The person must already have an account to be invited.</p>
      </Card>

      <Card>
        {members.length === 0 ? (
          <p>No team members yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>{member.user_name || "—"}</td>
                    <td>{member.user_email}</td>
                    <td>
                      {member.role === "owner" ? (
                        "owner"
                      ) : (
                        <select value={member.role} onChange={(e) => handleRoleChange(member.id, e.target.value)}>
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>{member.status}</td>
                    <td>
                      {member.role !== "owner" && member.status !== "revoked" && (
                        <button className="btn btn-ghost" onClick={() => handleRevoke(member.id)}>
                          Remove
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

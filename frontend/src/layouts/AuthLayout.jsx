import { Outlet } from "react-router-dom";

export default function AuthLayout() {
  return (
    <div className="auth-layout">
      <div className="auth-card">
        <h1 className="auth-brand">AI Sales &amp; Support Agent</h1>
        <Outlet />
      </div>
    </div>
  );
}

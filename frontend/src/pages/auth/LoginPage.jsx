import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../../components/Button";
import ErrorBanner from "../../components/ErrorBanner";
import FormField from "../../components/FormField";
import { useAuth } from "../../hooks/useAuth";
import { extractErrorMessage } from "../../utils/apiError";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-form">
      <h2>Log in</h2>
      <ErrorBanner message={error} />
      <FormField label="Email">
        <input type="email" name="email" required value={form.email} onChange={handleChange} />
      </FormField>
      <FormField label="Password">
        <input type="password" name="password" required value={form.password} onChange={handleChange} />
      </FormField>
      <Button type="submit" disabled={submitting}>
        {submitting ? "Logging in…" : "Log in"}
      </Button>
      <p className="auth-switch">
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </form>
  );
}

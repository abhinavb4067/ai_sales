import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../../components/Button";
import ErrorBanner from "../../components/ErrorBanner";
import FormField from "../../components/FormField";
import { useAuth } from "../../hooks/useAuth";
import { extractErrorMessage } from "../../utils/apiError";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", businessName: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-form">
      <h2>Create your account</h2>
      <ErrorBanner message={error} />
      <FormField label="Your name">
        <input name="name" required value={form.name} onChange={handleChange} />
      </FormField>
      <FormField label="Business name">
        <input name="businessName" required value={form.businessName} onChange={handleChange} />
      </FormField>
      <FormField label="Email">
        <input type="email" name="email" required value={form.email} onChange={handleChange} />
      </FormField>
      <FormField label="Password">
        <input type="password" name="password" required minLength={10} value={form.password} onChange={handleChange} />
      </FormField>
      <Button type="submit" disabled={submitting}>
        {submitting ? "Creating account…" : "Create account"}
      </Button>
      <p className="auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  );
}

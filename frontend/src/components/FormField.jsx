export default function FormField({ label, error, children }) {
  return (
    <label className="form-field">
      <span className="form-label">{label}</span>
      {children}
      {error && <span className="form-error">{error}</span>}
    </label>
  );
}

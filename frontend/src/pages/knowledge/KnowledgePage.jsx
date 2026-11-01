import { useEffect, useState } from "react";
import Button from "../../components/Button";
import Card from "../../components/Card";
import ErrorBanner from "../../components/ErrorBanner";
import FormField from "../../components/FormField";
import { createKnowledgeEntry, createKnowledgeFile, deleteKnowledgeEntry, listKnowledge } from "../../services/knowledgeApi";
import { extractErrorMessage } from "../../utils/apiError";

const EMPTY_TEXT_FORM = { title: "", content: "", source_type: "manual" };
const FILE_TYPES = [
  { value: "pdf", label: "PDF" },
  { value: "docx", label: "Word (.docx)" },
  { value: "txt", label: "Text file" },
  { value: "csv", label: "CSV" },
];

export default function KnowledgePage() {
  const [documents, setDocuments] = useState([]);
  const [mode, setMode] = useState("text"); // text | file | url | api
  const [textForm, setTextForm] = useState(EMPTY_TEXT_FORM);
  const [fileForm, setFileForm] = useState({ title: "", sourceType: "pdf", file: null });
  const [urlForm, setUrlForm] = useState({ title: "", source_url: "", max_pages: 20 });
  const [apiForm, setApiForm] = useState({ title: "", source_url: "", accept_header: "application/json" });
  const [dbForm, setDbForm] = useState({
    title: "", dialect: "postgresql", host: "", port: "5432", database: "", user: "", password: "", table: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const reload = () => listKnowledge().then(setDocuments);

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createKnowledgeEntry(textForm);
      setTextForm(EMPTY_TEXT_FORM);
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!fileForm.file) {
      setError("Please choose a file.");
      return;
    }
    setSubmitting(true);
    try {
      await createKnowledgeFile({ title: fileForm.title, sourceType: fileForm.sourceType, file: fileForm.file });
      setFileForm({ title: "", sourceType: "pdf", file: null });
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createKnowledgeEntry({
        title: urlForm.title,
        source_type: "url",
        source_url: urlForm.source_url,
        source_config: { max_pages: Number(urlForm.max_pages) || 20 },
      });
      setUrlForm({ title: "", source_url: "", max_pages: 20 });
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDbSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createKnowledgeEntry({
        title: dbForm.title,
        source_type: "database",
        database_credentials: {
          dialect: dbForm.dialect,
          host: dbForm.host,
          port: Number(dbForm.port) || undefined,
          database: dbForm.database,
          user: dbForm.user,
          password: dbForm.password,
          table: dbForm.table,
        },
      });
      setDbForm({ title: "", dialect: "postgresql", host: "", port: "5432", database: "", user: "", password: "", table: "" });
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleApiSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createKnowledgeEntry({
        title: apiForm.title,
        source_type: "api",
        source_url: apiForm.source_url,
        source_config: apiForm.accept_header ? { headers: { Accept: apiForm.accept_header } } : {},
      });
      setApiForm({ title: "", source_url: "", accept_header: "application/json" });
      await reload();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this knowledge entry?")) return;
    await deleteKnowledgeEntry(id);
    await reload();
  };

  return (
    <div className="page">
      <h1>Knowledge Base</h1>
      <p className="page-subtitle">
        Business information, FAQs, pricing, policies, and documents your agents will answer from.
      </p>

      <Card
        title="Add knowledge"
        actions={
          <div className="tab-row">
            <button className={`tab ${mode === "text" ? "active" : ""}`} onClick={() => setMode("text")} type="button">
              Text / FAQ
            </button>
            <button className={`tab ${mode === "file" ? "active" : ""}`} onClick={() => setMode("file")} type="button">
              File
            </button>
            <button className={`tab ${mode === "url" ? "active" : ""}`} onClick={() => setMode("url")} type="button">
              Website URL
            </button>
            <button className={`tab ${mode === "api" ? "active" : ""}`} onClick={() => setMode("api")} type="button">
              External API
            </button>
            <button className={`tab ${mode === "database" ? "active" : ""}`} onClick={() => setMode("database")} type="button">
              External Database
            </button>
          </div>
        }
      >
        <ErrorBanner message={error} />

        {mode === "text" && (
          <form onSubmit={handleTextSubmit} className="knowledge-form">
            <FormField label="Title">
              <input required value={textForm.title} onChange={(e) => setTextForm({ ...textForm, title: e.target.value })} />
            </FormField>
            <FormField label="Type">
              <select
                value={textForm.source_type}
                onChange={(e) => setTextForm({ ...textForm, source_type: e.target.value })}
              >
                <option value="manual">Manual entry</option>
                <option value="faq">FAQ</option>
              </select>
            </FormField>
            <FormField label="Content">
              <textarea
                rows={5}
                required
                placeholder="e.g. Our support hours are Mon-Fri 9am-6pm. Our starter plan costs $29/month..."
                value={textForm.content}
                onChange={(e) => setTextForm({ ...textForm, content: e.target.value })}
              />
            </FormField>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Add to Knowledge Base"}
            </Button>
          </form>
        )}

        {mode === "file" && (
          <form onSubmit={handleFileSubmit} className="knowledge-form">
            <FormField label="Title">
              <input required value={fileForm.title} onChange={(e) => setFileForm({ ...fileForm, title: e.target.value })} />
            </FormField>
            <FormField label="File type">
              <select value={fileForm.sourceType} onChange={(e) => setFileForm({ ...fileForm, sourceType: e.target.value })}>
                {FILE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="File (max 15MB)">
              <input type="file" required onChange={(e) => setFileForm({ ...fileForm, file: e.target.files[0] })} />
            </FormField>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Uploading…" : "Upload & Process"}
            </Button>
            <p className="text-muted">Processed in the background — status will show as "processing" until ready.</p>
          </form>
        )}

        {mode === "url" && (
          <form onSubmit={handleUrlSubmit} className="knowledge-form">
            <FormField label="Title">
              <input required value={urlForm.title} onChange={(e) => setUrlForm({ ...urlForm, title: e.target.value })} />
            </FormField>
            <FormField label="Website URL">
              <input
                type="url"
                required
                placeholder="https://example.com/faq"
                value={urlForm.source_url}
                onChange={(e) => setUrlForm({ ...urlForm, source_url: e.target.value })}
              />
            </FormField>
            <FormField label="Max pages to crawl (1-50)">
              <input
                type="number"
                min="1"
                max="50"
                value={urlForm.max_pages}
                onChange={(e) => setUrlForm({ ...urlForm, max_pages: e.target.value })}
              />
            </FormField>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Crawling…" : "Crawl & Process"}
            </Button>
            <p className="text-muted">
              Follows same-site links from this page, respecting robots.txt, up to the page limit above.
            </p>
          </form>
        )}

        {mode === "api" && (
          <form onSubmit={handleApiSubmit} className="knowledge-form">
            <FormField label="Title">
              <input required value={apiForm.title} onChange={(e) => setApiForm({ ...apiForm, title: e.target.value })} />
            </FormField>
            <FormField label="API endpoint URL (public, read-only, no secret key required)">
              <input
                type="url"
                required
                placeholder="https://api.example.com/products"
                value={apiForm.source_url}
                onChange={(e) => setApiForm({ ...apiForm, source_url: e.target.value })}
              />
            </FormField>
            <FormField label="Accept header">
              <input
                value={apiForm.accept_header}
                onChange={(e) => setApiForm({ ...apiForm, accept_header: e.target.value })}
              />
            </FormField>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Fetching…" : "Fetch & Process"}
            </Button>
            <p className="text-muted">
              Only public endpoints are supported today — internal/private network addresses are always blocked.
              Endpoints requiring a secret API key aren't supported yet.
            </p>
          </form>
        )}

        {mode === "database" && (
          <form onSubmit={handleDbSubmit} className="knowledge-form">
            <FormField label="Title">
              <input required value={dbForm.title} onChange={(e) => setDbForm({ ...dbForm, title: e.target.value })} />
            </FormField>
            <FormField label="Database type">
              <select value={dbForm.dialect} onChange={(e) => setDbForm({ ...dbForm, dialect: e.target.value })}>
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
              </select>
            </FormField>
            <FormField label="Host">
              <input required value={dbForm.host} onChange={(e) => setDbForm({ ...dbForm, host: e.target.value })} />
            </FormField>
            <FormField label="Port">
              <input value={dbForm.port} onChange={(e) => setDbForm({ ...dbForm, port: e.target.value })} />
            </FormField>
            <FormField label="Database name">
              <input required value={dbForm.database} onChange={(e) => setDbForm({ ...dbForm, database: e.target.value })} />
            </FormField>
            <FormField label="Read-only username">
              <input required value={dbForm.user} onChange={(e) => setDbForm({ ...dbForm, user: e.target.value })} />
            </FormField>
            <FormField label="Password">
              <input type="password" required value={dbForm.password} onChange={(e) => setDbForm({ ...dbForm, password: e.target.value })} />
            </FormField>
            <FormField label="Table name (single table, no joins/queries)">
              <input required value={dbForm.table} onChange={(e) => setDbForm({ ...dbForm, table: e.target.value })} />
            </FormField>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Connecting…" : "Connect & Process"}
            </Button>
            <p className="text-muted">
              Use a dedicated read-only database user — never your admin credentials. We only ever run a single
              read-only query against the one table you specify, nothing else.
            </p>
          </form>
        )}
      </Card>

      <Card title="Existing entries">
        {loading ? (
          <div className="page-loading">Loading…</div>
        ) : documents.length === 0 ? (
          <p>No knowledge entries yet.</p>
        ) : (
          <ul className="entity-list">
            {documents.map((doc) => (
              <li key={doc.id}>
                <div>
                  <strong>{doc.title}</strong>
                  <span className="badge">{doc.source_type}</span>
                  <span className={`badge badge-${doc.status}`}>{doc.status}</span>
                </div>
                <button className="btn btn-ghost" onClick={() => handleDelete(doc.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

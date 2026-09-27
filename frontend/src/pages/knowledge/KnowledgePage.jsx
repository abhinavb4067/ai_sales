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
  const [mode, setMode] = useState("text"); // text | file | url
  const [textForm, setTextForm] = useState(EMPTY_TEXT_FORM);
  const [fileForm, setFileForm] = useState({ title: "", sourceType: "pdf", file: null });
  const [urlForm, setUrlForm] = useState({ title: "", source_url: "" });
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
      await createKnowledgeEntry({ title: urlForm.title, source_type: "url", source_url: urlForm.source_url });
      setUrlForm({ title: "", source_url: "" });
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
            <Button type="submit" disabled={submitting}>
              {submitting ? "Fetching…" : "Fetch & Process"}
            </Button>
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

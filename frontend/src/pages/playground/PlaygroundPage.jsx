import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import Button from "../../components/Button";
import ErrorBanner from "../../components/ErrorBanner";
import { getAgent } from "../../services/agentsApi";
import { sendPlaygroundMessage } from "../../services/playgroundApi";
import { extractErrorMessage } from "../../utils/apiError";

export default function PlaygroundPage() {
  const { id } = useParams();
  const [agent, setAgent] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    getAgent(id).then((a) => {
      setAgent(a);
      if (a.greeting) {
        setMessages([{ sender_type: "ai", content: a.greeting }]);
      }
    });
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setError("");
    const userMessage = { sender_type: "customer", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);
    try {
      const response = await sendPlaygroundMessage({
        agentId: Number(id),
        conversationId,
        message: userMessage.content,
      });
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        { sender_type: "ai", content: response.message.content, toolCalls: response.message.tool_calls },
      ]);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  };

  if (!agent) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page playground-page">
      <h1>Test: {agent.name}</h1>
      <p className="page-subtitle">
        This uses the exact same AI pipeline your customers will talk to once deployed.
      </p>

      <div className="playground-chat">
        <div className="playground-messages">
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble chat-bubble-${m.sender_type}`}>
              <div className="chat-bubble-content">{m.content}</div>
              {m.toolCalls && m.toolCalls.length > 0 && (
                <div className="chat-tool-calls">
                  {m.toolCalls.map((tc, j) => (
                    <span key={j} className={`badge badge-tool-${tc.status}`}>
                      {tc.tool_name}: {tc.status}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <ErrorBanner message={error} />
        <form onSubmit={handleSend} className="playground-input-row">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message as a customer would…"
            disabled={sending}
          />
          <Button type="submit" disabled={sending || !input.trim()}>
            {sending ? "Sending…" : "Send"}
          </Button>
        </form>
      </div>
    </div>
  );
}

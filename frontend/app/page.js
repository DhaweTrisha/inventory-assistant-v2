"use client";

import { useEffect, useRef, useState } from "react";
import ResultChart from "../components/Chart";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [roles, setRoles] = useState({});
  const [role, setRole] = useState("Business Owner");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  // Load the roles and their suggested questions from the backend
  useEffect(() => {
    fetch(`${API}/roles`)
      .then((r) => r.json())
      .then(setRoles)
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function changeRole(newRole) {
    setRole(newRole);
    setMessages([]); // a new person is "logging in", start fresh
  }

  async function send(question) {
    const q = question.trim();
    if (!q || loading) return;

    // last few turns so the bot can handle follow-ups like "and for last month?"
    const history = messages.slice(-6).map((m) => ({
      role: m.from === "user" ? "user" : "assistant",
      content: m.text,
    }));

    setMessages((m) => [...m, { from: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, role, history }),
      });
      const data = await res.json();
      setMessages((m) => [...m, { from: "bot", text: data.answer, ...data }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { from: "bot", text: "Sorry, I couldn't reach the backend. Is it running on port 8000?" },
      ]);
    }
    setLoading(false);
  }

  async function confirmWrite(index, yes) {
    const msg = messages[index];
    if (!yes) {
      updateMessage(index, { needs_confirmation: false, text: msg.text + "\n\nOkay, I didn't change anything." });
      return;
    }
    try {
      const res = await fetch(`${API}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: msg.sql, role }),
      });
      const data = await res.json();
      updateMessage(index, { needs_confirmation: false, text: data.answer });
    } catch (e) {
      updateMessage(index, { needs_confirmation: false, text: "Something went wrong while saving." });
    }
  }

  function updateMessage(index, changes) {
    setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, ...changes } : msg)));
  }

  const suggestions = roles[role]?.suggested_questions || [];

  return (
    <main className="page">
      <header>
        <h1>Inventory & Procurement Assistant</h1>
        <label className="role-picker">
          I am the
          <select value={role} onChange={(e) => changeRole(e.target.value)}>
            {Object.keys(roles).length === 0 && <option>{role}</option>}
            {Object.keys(roles).map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
      </header>
      <p className="role-help">{roles[role]?.description}</p>

      <div className="suggestions">
        {suggestions.map((s) => (
          <button key={s} onClick={() => send(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="chat">
        {messages.length === 0 && (
          <div className="msg bot">
            Hi! Ask me anything about stock, purchase orders, vendors or payments. Try one of the
            suggestions above.
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.from} ${m.blocked ? "blocked" : ""}`}>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>

            {m.from === "bot" && <ResultChart chart={m.chart} />}

            {m.from === "bot" && m.rows && m.rows.length > 0 && (
              <details>
                <summary>Show data ({m.rows.length} rows)</summary>
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        {m.columns.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {m.rows.slice(0, 25).map((row, ri) => (
                        <tr key={ri}>
                          {m.columns.map((c) => (
                            <td key={c}>{String(row[c] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {m.from === "bot" && m.sql && (
              <details>
                <summary>Show SQL</summary>
                <pre>{m.sql}</pre>
              </details>
            )}

            {m.from === "bot" && m.needs_confirmation && (
              <div className="confirm">
                <button className="primary" onClick={() => confirmWrite(i, true)}>
                  Yes, apply this change
                </button>
                <button onClick={() => confirmWrite(i, false)}>Cancel</button>
              </div>
            )}
          </div>
        ))}

        {loading && <div className="msg bot typing">Looking that up...</div>}
        <div ref={bottomRef} />
      </div>

      <div className="composer">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask a question as the ${role}...`}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Ask
          </button>
        </form>
      </div>
    </main>
  );
}

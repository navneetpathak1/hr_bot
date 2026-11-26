import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { sendQuery } from "../api";

export default function Chat() {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");
    if (!storedToken) {
      navigate("/login");
      return;
    }
    setToken(storedToken);
    if (storedUser) setUser(JSON.parse(storedUser));
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: "user", text: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendQuery(input, token);
      const botMessage = {
        role: "bot",
        text: data.answer,
        citations: data.citations || [],
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: `Error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div>
        <h1>HR RAG Chat</h1>
        {user && <span>Logged in as: {user.username}</span>}
        <button onClick={handleLogout} style={{ marginLeft: "10px" }}>
          Logout
        </button>
      </div>

      <hr />

      <div
        id="chat-messages"
        style={{ minHeight: "300px", maxHeight: "500px", overflowY: "auto", border: "1px solid #ccc", padding: "10px" }}
      >
        {messages.length === 0 && <p>No messages yet. Ask a question!</p>}
        {messages.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: "12px" }}>
            <strong>{msg.role === "user" ? "You" : "Bot"}:</strong>
            <p style={{ margin: "4px 0" }}>{msg.text}</p>
            {msg.citations && msg.citations.length > 0 && (
              <div>
                <small>
                  <strong>Citations:</strong>{" "}
                  {msg.citations.map((c, i) => (
                    <span key={i}>[{i + 1}] {typeof c === "string" ? c : JSON.stringify(c)}{" "}</span>
                  ))}
                </small>
              </div>
            )}
          </div>
        ))}
        {loading && <p><em>Thinking...</em></p>}
      </div>

      <form onSubmit={handleSubmit} style={{ marginTop: "10px" }}>
        <input
          id="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask an HR question..."
          style={{ width: "80%" }}
          disabled={loading}
        />
        <button type="submit" disabled={loading} style={{ marginLeft: "8px" }}>
          Send
        </button>
      </form>
    </div>
  );
}

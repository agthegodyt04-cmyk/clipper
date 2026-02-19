import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getApiBase, resetApiBase, setApiBase } from "./lib/api";
import { EditorPage } from "./pages/EditorPage";
import { ProjectPage } from "./pages/ProjectPage";
import { VideoPage } from "./pages/VideoPage";
import "./App.css";

function App() {
  const [apiInput, setApiInput] = useState(getApiBase());
  const [apiActive, setApiActive] = useState(getApiBase());

  function applyApiBase() {
    if (!apiInput.trim()) {
      return;
    }
    setApiActive(setApiBase(apiInput));
  }

  function restoreApiBase() {
    const fallback = resetApiBase();
    setApiInput(fallback);
    setApiActive(fallback);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Clipper Local AI Ad Studio</h1>
        <p>Free local ad copy, image generation, brush edits, and video ads.</p>
        <div className="api-config">
          <label>
            API URL
            <input
              value={apiInput}
              onChange={(event) => setApiInput(event.target.value)}
              placeholder="https://example.trycloudflare.com"
            />
          </label>
          <button type="button" onClick={applyApiBase}>
            Use API
          </button>
          <button type="button" className="secondary" onClick={restoreApiBase}>
            Reset
          </button>
          <p className="api-current">Current API: {apiActive}</p>
        </div>
        <nav className="app-nav">
          <NavLink to="/" end>
            Project
          </NavLink>
          <NavLink to="/editor">Editor</NavLink>
          <NavLink to="/video">Video</NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ProjectPage />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/video" element={<VideoPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;

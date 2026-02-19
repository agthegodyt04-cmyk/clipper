import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getApiBase, resetApiBase, setApiBase } from "./lib/api";
import { PricingBlueprintPage } from "./pages/PricingBlueprintPage";
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
        <p>Simple flow: 1) Project 2) Generate 3) Brush edit 4) Video export.</p>
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
            1. Project
          </NavLink>
          <NavLink to="/editor">2. Editor</NavLink>
          <NavLink to="/video">3. Video</NavLink>
          <NavLink to="/pricing">4. Pricing</NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ProjectPage />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/video" element={<VideoPage />} />
          <Route path="/pricing" element={<PricingBlueprintPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;

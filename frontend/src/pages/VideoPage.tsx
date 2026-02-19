import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { assetUrl, generateStoryboard, generateT2V, listProjectAssets, listProjects, pollJob } from "../lib/api";
import { recordUsage } from "../lib/pricingBlueprint";
import type { Asset, PlatformTarget, Project, RenderMode } from "../types/api";

const CURRENT_PROJECT_KEY = "clipper_current_project_id";

export function VideoPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(localStorage.getItem(CURRENT_PROJECT_KEY) ?? "");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Step 5: generate storyboard video or text-to-video.");

  const [storyboardForm, setStoryboardForm] = useState({
    duration_sec: 15,
    platform: "9:16" as PlatformTarget,
    voice_id: "default",
    style_prompt: "clean product ad with bold headline moments",
    scene_count: 4,
    mode: "draft" as RenderMode,
  });

  const [t2vForm, setT2VForm] = useState({
    prompt: "A high-energy fitness ad featuring a smart bottle in motion",
    duration_sec: 8,
    platform: "9:16" as PlatformTarget,
    mode: "draft" as RenderMode,
  });

  useEffect(() => {
    void refreshProjects();
  }, []);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    localStorage.setItem(CURRENT_PROJECT_KEY, projectId);
    void refreshAssets(projectId);
  }, [projectId]);

  async function refreshProjects() {
    try {
      const result = await listProjects();
      setProjects(result.projects);
      if (!projectId && result.projects.length > 0) {
        setProjectId(result.projects[0].id);
      }
    } catch (error) {
      setStatus(`Failed to load projects: ${(error as Error).message}`);
    }
  }

  async function refreshAssets(targetProjectId: string) {
    try {
      const result = await listProjectAssets(targetProjectId);
      setAssets(result.assets);
    } catch (error) {
      setStatus(`Failed to load assets: ${(error as Error).message}`);
    }
  }

  async function runStoryboard() {
    if (!projectId) {
      setStatus("Select a project first.");
      return;
    }
    setBusy(true);
    setStatus("Queueing storyboard job...");
    try {
      const queued = await generateStoryboard({ project_id: projectId, ...storyboardForm });
      const result = await pollJob(queued.job_id, (job) =>
        setStatus(`Storyboard ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      if (result.job.status !== "done") {
        throw new Error(`Storyboard job ended as '${result.job.status}'.`);
      }
      recordUsage("video_jobs");
      setStatus(`Storyboard job finished: ${result.job.status}`);
      await refreshAssets(projectId);
    } catch (error) {
      setStatus(`Storyboard generation failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function runT2V() {
    if (!projectId) {
      setStatus("Select a project first.");
      return;
    }
    setBusy(true);
    setStatus("Queueing T2V job...");
    try {
      const queued = await generateT2V({ project_id: projectId, ...t2vForm });
      const result = await pollJob(queued.job_id, (job) =>
        setStatus(`T2V ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      if (result.job.status !== "done") {
        throw new Error(`T2V job ended as '${result.job.status}'.`);
      }
      recordUsage("t2v_jobs");
      const fallbackUsed = Boolean(result.job.result?.fallback_used);
      if (fallbackUsed) {
        setStatus("T2V ended in fallback storyboard mode (real video model unavailable/failed).");
      } else {
        setStatus("T2V job finished with local video model.");
      }
      await refreshAssets(projectId);
    } catch (error) {
      setStatus(`T2V generation failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  const videos = useMemo(() => assets.filter((asset) => asset.kind === "video"), [assets]);

  return (
    <div className="page-grid">
      <section className="panel">
        <h2>Step 5: Video Generation</h2>
        <p className="small-note">Start with Storyboard for reliable results, then try T2V.</p>

        <label>
          Active Project
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">Select project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>

        <div className="inline-actions">
          <button disabled={busy || !projectId} type="button" onClick={() => void refreshAssets(projectId)}>
            Refresh Assets
          </button>
          <button disabled={busy} type="button" onClick={() => void refreshProjects()}>
            Refresh Projects
          </button>
        </div>

        {!projectId ? (
          <p className="small-note">
            No project selected. Create one in <Link to="/">Project</Link> first.
          </p>
        ) : null}

        <div className="form-grid">
          <h3>Storyboard (recommended)</h3>
          <label>
            Style Prompt
            <textarea
              value={storyboardForm.style_prompt}
              onChange={(event) =>
                setStoryboardForm({ ...storyboardForm, style_prompt: event.target.value })
              }
            />
          </label>
          <label>
            Duration (sec)
            <input
              type="number"
              min={5}
              max={60}
              value={storyboardForm.duration_sec}
              onChange={(event) =>
                setStoryboardForm({ ...storyboardForm, duration_sec: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Scene Count
            <input
              type="number"
              min={2}
              max={10}
              value={storyboardForm.scene_count}
              onChange={(event) =>
                setStoryboardForm({ ...storyboardForm, scene_count: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Platform
            <select
              value={storyboardForm.platform}
              onChange={(event) =>
                setStoryboardForm({
                  ...storyboardForm,
                  platform: event.target.value as PlatformTarget,
                })
              }
            >
              <option value="9:16">9:16</option>
              <option value="4:5">4:5</option>
              <option value="1:1">1:1</option>
            </select>
          </label>
          <label>
            Quality
            <select
              value={storyboardForm.mode}
              onChange={(event) =>
                setStoryboardForm({ ...storyboardForm, mode: event.target.value as RenderMode })
              }
            >
              <option value="draft">Draft (faster)</option>
              <option value="hq">HQ (better quality)</option>
            </select>
          </label>
          <button disabled={busy} type="button" onClick={() => void runStoryboard()}>
            Generate Storyboard Video
          </button>
        </div>

        <div className="form-grid">
          <h3>Text-to-Video (experimental)</h3>
          <label>
            Prompt
            <textarea
              value={t2vForm.prompt}
              onChange={(event) => setT2VForm({ ...t2vForm, prompt: event.target.value })}
            />
          </label>
          <label>
            Duration (sec)
            <input
              type="number"
              min={4}
              max={20}
              value={t2vForm.duration_sec}
              onChange={(event) => setT2VForm({ ...t2vForm, duration_sec: Number(event.target.value) })}
            />
          </label>
          <label>
            Platform
            <select
              value={t2vForm.platform}
              onChange={(event) =>
                setT2VForm({ ...t2vForm, platform: event.target.value as PlatformTarget })
              }
            >
              <option value="9:16">9:16</option>
              <option value="4:5">4:5</option>
              <option value="1:1">1:1</option>
            </select>
          </label>
          <label>
            Quality
            <select
              value={t2vForm.mode}
              onChange={(event) => setT2VForm({ ...t2vForm, mode: event.target.value as RenderMode })}
            >
              <option value="draft">Draft (faster)</option>
              <option value="hq">HQ (better quality)</option>
            </select>
          </label>
          <button disabled={busy} type="button" onClick={() => void runT2V()}>
            Generate Text-to-Video
          </button>
        </div>
      </section>

      <section className="panel panel-wide">
        <h2>Rendered Videos</h2>
        <p className="status">{status}</p>
        {videos.length === 0 ? <p>No video assets yet.</p> : null}
        {videos.map((video) => (
          <article key={video.id} className="video-card">
            <p>
              <strong>{video.id}</strong>
            </p>
            <video controls src={assetUrl(video.id)} width={260} />
            <pre>{JSON.stringify(video.meta, null, 2)}</pre>
          </article>
        ))}
      </section>
    </div>
  );
}

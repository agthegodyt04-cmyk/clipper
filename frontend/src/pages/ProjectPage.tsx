import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createProject,
  generateCopy,
  generateImage,
  listProjectAssets,
  listProjects,
  pollJob,
} from "../lib/api";
import type { Asset, PlatformTarget, Project, RenderMode } from "../types/api";

const CURRENT_PROJECT_KEY = "clipper_current_project_id";

export function ProjectPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Create a project to start.");
  const [selectedProjectId, setSelectedProjectId] = useState<string>(() => localStorage.getItem(CURRENT_PROJECT_KEY) ?? "");

  const [projectForm, setProjectForm] = useState({
    name: "Launch Sprint",
    brand_name: "Northline",
    product: "Smart Bottle",
    audience: "busy gym beginners",
    offer: "30% launch offer",
    tone: "bold",
    platform_targets: ["9:16", "4:5", "1:1"] as PlatformTarget[],
  });

  const [copyForm, setCopyForm] = useState({
    goal: "more daily hydration",
    cta: "Shop now",
    count: 3,
    mode: "draft" as RenderMode,
  });

  const [imageForm, setImageForm] = useState({
    prompt: "Cinematic product ad photo of a smart bottle with sweat drops",
    negative_prompt: "blurry text, watermark",
    platform: "9:16" as PlatformTarget,
    mode: "draft" as RenderMode,
    seed: "",
  });

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  useEffect(() => {
    void refreshProjects();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }
    localStorage.setItem(CURRENT_PROJECT_KEY, selectedProjectId);
    void refreshAssets(selectedProjectId);
  }, [selectedProjectId]);

  async function refreshProjects() {
    try {
      const result = await listProjects();
      setProjects(result.projects);
      if (!selectedProjectId && result.projects.length > 0) {
        setSelectedProjectId(result.projects[0].id);
      }
    } catch (error) {
      setStatus(`Failed to load projects: ${(error as Error).message}`);
    }
  }

  async function refreshAssets(projectId: string) {
    try {
      const result = await listProjectAssets(projectId);
      setAssets(result.assets);
    } catch (error) {
      setStatus(`Failed to load assets: ${(error as Error).message}`);
    }
  }

  async function onCreateProject(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus("Creating project...");
    try {
      const result = await createProject(projectForm);
      setStatus(`Project created: ${result.project.name}`);
      await refreshProjects();
      setSelectedProjectId(result.project_id);
      await refreshAssets(result.project_id);
    } catch (error) {
      setStatus(`Create project failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onGenerateCopy() {
    if (!selectedProjectId) {
      setStatus("Select a project first.");
      return;
    }
    setBusy(true);
    setStatus("Queueing copy generation...");
    try {
      const queued = await generateCopy({
        project_id: selectedProjectId,
        ...copyForm,
      });
      const finished = await pollJob(queued.job_id, (job) =>
        setStatus(`Copy job ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      setStatus(`Copy job finished: ${finished.job.status}`);
      await refreshAssets(selectedProjectId);
    } catch (error) {
      setStatus(`Copy generation failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onGenerateImage() {
    if (!selectedProjectId) {
      setStatus("Select a project first.");
      return;
    }
    setBusy(true);
    setStatus("Queueing image generation...");
    try {
      const queued = await generateImage({
        project_id: selectedProjectId,
        prompt: imageForm.prompt,
        negative_prompt: imageForm.negative_prompt,
        platform: imageForm.platform,
        mode: imageForm.mode,
        seed: imageForm.seed ? Number(imageForm.seed) : undefined,
      });
      const finished = await pollJob(queued.job_id, (job) =>
        setStatus(`Image job ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      setStatus(`Image job finished: ${finished.job.status}`);
      await refreshAssets(selectedProjectId);
    } catch (error) {
      setStatus(`Image generation failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <h2>Project</h2>
        <form onSubmit={onCreateProject} className="form-grid">
          <label>
            Project Name
            <input
              value={projectForm.name}
              onChange={(event) => setProjectForm({ ...projectForm, name: event.target.value })}
            />
          </label>
          <label>
            Brand
            <input
              value={projectForm.brand_name}
              onChange={(event) => setProjectForm({ ...projectForm, brand_name: event.target.value })}
            />
          </label>
          <label>
            Product
            <input
              value={projectForm.product}
              onChange={(event) => setProjectForm({ ...projectForm, product: event.target.value })}
            />
          </label>
          <label>
            Audience
            <input
              value={projectForm.audience}
              onChange={(event) => setProjectForm({ ...projectForm, audience: event.target.value })}
            />
          </label>
          <label>
            Offer
            <input
              value={projectForm.offer}
              onChange={(event) => setProjectForm({ ...projectForm, offer: event.target.value })}
            />
          </label>
          <label>
            Tone
            <input
              value={projectForm.tone}
              onChange={(event) => setProjectForm({ ...projectForm, tone: event.target.value })}
            />
          </label>
          <button disabled={busy} type="submit">
            Create Project
          </button>
        </form>
        <label className="select-label">
          Active Project
          <select
            value={selectedProjectId}
            onChange={(event) => setSelectedProjectId(event.target.value)}
            disabled={projects.length === 0}
          >
            <option value="">Select</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        {selectedProject ? (
          <p className="small-note">
            {selectedProject.brand_name} | {selectedProject.product} | tone: {selectedProject.tone}
          </p>
        ) : null}
      </section>

      <section className="panel">
        <h2>Copy + Image Jobs</h2>
        <div className="form-grid">
          <h3>Copy</h3>
          <label>
            Goal
            <input
              value={copyForm.goal}
              onChange={(event) => setCopyForm({ ...copyForm, goal: event.target.value })}
            />
          </label>
          <label>
            CTA
            <input
              value={copyForm.cta}
              onChange={(event) => setCopyForm({ ...copyForm, cta: event.target.value })}
            />
          </label>
          <label>
            Count
            <input
              type="number"
              min={1}
              max={10}
              value={copyForm.count}
              onChange={(event) => setCopyForm({ ...copyForm, count: Number(event.target.value) })}
            />
          </label>
          <label>
            Mode
            <select
              value={copyForm.mode}
              onChange={(event) => setCopyForm({ ...copyForm, mode: event.target.value as RenderMode })}
            >
              <option value="draft">Draft</option>
              <option value="hq">HQ</option>
            </select>
          </label>
          <button disabled={busy} type="button" onClick={() => void onGenerateCopy()}>
            Generate Copy
          </button>
        </div>

        <div className="form-grid">
          <h3>Image</h3>
          <label>
            Prompt
            <textarea
              value={imageForm.prompt}
              onChange={(event) => setImageForm({ ...imageForm, prompt: event.target.value })}
            />
          </label>
          <label>
            Negative Prompt
            <input
              value={imageForm.negative_prompt}
              onChange={(event) => setImageForm({ ...imageForm, negative_prompt: event.target.value })}
            />
          </label>
          <label>
            Platform
            <select
              value={imageForm.platform}
              onChange={(event) =>
                setImageForm({ ...imageForm, platform: event.target.value as PlatformTarget })
              }
            >
              <option value="9:16">9:16</option>
              <option value="4:5">4:5</option>
              <option value="1:1">1:1</option>
            </select>
          </label>
          <label>
            Mode
            <select
              value={imageForm.mode}
              onChange={(event) => setImageForm({ ...imageForm, mode: event.target.value as RenderMode })}
            >
              <option value="draft">Draft</option>
              <option value="hq">HQ</option>
            </select>
          </label>
          <label>
            Seed (optional)
            <input
              value={imageForm.seed}
              onChange={(event) => setImageForm({ ...imageForm, seed: event.target.value })}
            />
          </label>
          <button disabled={busy} type="button" onClick={() => void onGenerateImage()}>
            Generate Image
          </button>
        </div>
      </section>

      <section className="panel panel-wide">
        <h2>Project Assets</h2>
        <p className="status">{status}</p>
        {assets.length === 0 ? <p>No assets yet.</p> : null}
        <div className="asset-grid">
          {assets.map((asset) => (
            <article key={asset.id} className="asset-card">
              <p>
                <strong>{asset.kind}</strong>
              </p>
              <p className="small-note">id: {asset.id}</p>
              <p className="small-note">{asset.path.split(/[/\\]/).slice(-2).join("/")}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

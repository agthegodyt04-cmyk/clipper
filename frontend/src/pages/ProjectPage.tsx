import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  assetUrl,
  createProject,
  generateCopy,
  generateImage,
  getSystemCapabilities,
  improveImagePrompt,
  listProjectAssets,
  listProjects,
  pollJob,
} from "../lib/api";
import { recordUsage } from "../lib/pricingBlueprint";
import type { Asset, PlatformTarget, Project, RenderMode, SystemCapabilities } from "../types/api";

const CURRENT_PROJECT_KEY = "clipper_current_project_id";

export function ProjectPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Step 1: create a project.");
  const [capabilities, setCapabilities] = useState<SystemCapabilities | null>(null);
  const [capabilityError, setCapabilityError] = useState("");
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
  const imageAssets = useMemo(() => assets.filter((asset) => asset.kind === "image"), [assets]);
  const copyAssets = useMemo(() => assets.filter((asset) => asset.kind === "copy"), [assets]);

  useEffect(() => {
    void refreshProjects();
    void refreshCapabilities();
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

  async function refreshCapabilities() {
    try {
      const result = await getSystemCapabilities();
      setCapabilities(result);
      setCapabilityError("");
    } catch (error) {
      setCapabilityError((error as Error).message);
    }
  }

  async function onCreateProject(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus("Creating project...");
    try {
      const payload = {
        ...projectForm,
        name: projectForm.name.trim() || "My Campaign",
        brand_name: projectForm.brand_name.trim() || projectForm.name.trim() || "My Brand",
        offer: projectForm.offer.trim() || "launch offer",
        tone: projectForm.tone.trim() || "bold",
      };
      const result = await createProject(payload);
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
      if (finished.job.status !== "done") {
        throw new Error(`Copy job ended as '${finished.job.status}'.`);
      }
      recordUsage("copy_jobs");
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
      const prompt =
        imageForm.prompt.trim() ||
        `Cinematic product ad photo of ${selectedProject?.product ?? "the product"} with premium lighting`;
      const queued = await generateImage({
        project_id: selectedProjectId,
        prompt,
        negative_prompt: imageForm.negative_prompt,
        platform: imageForm.platform,
        mode: imageForm.mode,
        seed: imageForm.seed ? Number(imageForm.seed) : undefined,
      });
      const finished = await pollJob(queued.job_id, (job) =>
        setStatus(`Image job ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      if (finished.job.status !== "done") {
        throw new Error(`Image job ended as '${finished.job.status}'.`);
      }
      recordUsage("image_jobs");
      const imageAsset = finished.assets.find((asset) => asset.kind === "image");
      const engine = String(imageAsset?.meta?.engine ?? "unknown");
      if (engine === "pillow_fallback") {
        setStatus("Image finished with placeholder renderer. Real model failed. Check model setup.");
      } else {
        setStatus(`Image job finished (${engine}).`);
      }
      await refreshAssets(selectedProjectId);
    } catch (error) {
      setStatus(`Image generation failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onImproveImagePrompt() {
    if (!selectedProjectId) {
      setStatus("Select a project first.");
      return;
    }
    setBusy(true);
    setStatus("Improving prompt for better image quality...");
    try {
      const result = await improveImagePrompt({
        project_id: selectedProjectId,
        prompt: imageForm.prompt,
        platform: imageForm.platform,
        mode: imageForm.mode,
      });
      setImageForm((prev) => ({
        ...prev,
        prompt: result.prompt,
        negative_prompt: result.negative_prompt,
      }));
      setStatus("Prompt improved. Generate image again.");
    } catch (error) {
      setStatus(`Prompt improvement failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onQuickGenerate() {
    if (!selectedProjectId) {
      setStatus("Create/select a project first.");
      return;
    }
    setBusy(true);
    try {
      setStatus("Quick ad: generating copy (step 1/2)...");
      const copyJob = await generateCopy({
        project_id: selectedProjectId,
        ...copyForm,
      });
      const copyResult = await pollJob(copyJob.job_id, (job) =>
        setStatus(`Copy ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      if (copyResult.job.status !== "done") {
        throw new Error(`Copy job ended as '${copyResult.job.status}'.`);
      }
      recordUsage("copy_jobs");

      setStatus("Quick ad: generating image (step 2/2)...");
      const prompt =
        imageForm.prompt.trim() ||
        `Cinematic product ad photo of ${selectedProject?.product ?? "the product"} with premium lighting`;
      const imageJob = await generateImage({
        project_id: selectedProjectId,
        prompt,
        negative_prompt: imageForm.negative_prompt,
        platform: imageForm.platform,
        mode: imageForm.mode,
        seed: imageForm.seed ? Number(imageForm.seed) : undefined,
      });
      const imageResult = await pollJob(imageJob.job_id, (job) =>
        setStatus(`Image ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      if (imageResult.job.status !== "done") {
        throw new Error(`Image job ended as '${imageResult.job.status}'.`);
      }
      recordUsage("image_jobs");
      const imageAsset = imageResult.assets.find((asset) => asset.kind === "image");
      const engine = String(imageAsset?.meta?.engine ?? "unknown");

      if (engine === "pillow_fallback") {
        setStatus("Quick ad finished, but image used placeholder renderer. Fix model setup for real output.");
      } else {
        setStatus("Quick ad finished. You can now go to Editor or Video.");
      }
      await refreshAssets(selectedProjectId);
    } catch (error) {
      setStatus(`Quick ad failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <h2>Step 1: Project Setup</h2>
        <p className="small-note">Fill this once. We remember your active project automatically.</p>
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
            Save Project
          </button>
        </form>
        <label className="select-label">
          Active Project (auto-used in all tabs)
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
          <>
            <p className="small-note">
              {selectedProject.brand_name} | {selectedProject.product} | tone: {selectedProject.tone}
            </p>
            <p className="small-note">Project ID: {selectedProject.id}</p>
          </>
        ) : null}
      </section>

      <section className="panel">
        <h2>Step 2: Generate Ad Assets</h2>
        <p className="small-note">Draft uses fast SDXL Turbo. HQ uses max-quality SDXL Base.</p>
        {capabilities ? (
          <div className="status">
            <p className="small-note">
              System Status: {capabilities.gpu.available ? "GPU detected" : "CPU mode"} | draft model:{" "}
              {capabilities.defaults.draft_model} | HQ model: {capabilities.defaults.hq_model}
            </p>
            {!capabilities.models.image_hq_sdxl_base ? (
              <p className="small-note">
                HQ SDXL model missing. Download:
                `python scripts/download_real_models.py --model-path D:/AIModels --targets image_fast_sdxl_turbo image_hq_sdxl_base inpaint_hq_sdxl`
              </p>
            ) : null}
          </div>
        ) : capabilityError ? (
          <p className="small-note">System Status unavailable: {capabilityError}</p>
        ) : (
          <p className="small-note">Loading system status...</p>
        )}
        <div className="inline-actions">
          <button disabled={busy || !selectedProjectId} type="button" onClick={() => void onQuickGenerate()}>
            1-Click: Copy + Image
          </button>
          <button disabled={busy} type="button" onClick={() => void refreshCapabilities()}>
            Refresh System Status
          </button>
        </div>
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
              <option value="draft">Draft (Fast)</option>
              <option value="hq">HQ (Enhanced)</option>
            </select>
          </label>
          <button disabled={busy} type="button" onClick={() => void onGenerateCopy()}>
            Generate Copy Only
          </button>
        </div>

        <div className="form-grid">
          <h3>Image</h3>
          <label>
            Prompt
            <textarea
              value={imageForm.prompt}
              placeholder="Leave blank to auto-create from product."
              onChange={(event) => setImageForm({ ...imageForm, prompt: event.target.value })}
            />
          </label>
          <div className="inline-actions">
            <button disabled={busy} type="button" onClick={() => void onImproveImagePrompt()}>
              Improve Prompt (AI)
            </button>
          </div>
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
              <option value="draft">Draft (Fast SDXL Turbo)</option>
              <option value="hq">HQ (Max SDXL)</option>
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
            Generate Image Only
          </button>
        </div>
      </section>

      <section className="panel panel-wide">
        <h2>Step 3: Results</h2>
        <p className="status">{status}</p>
        {assets.length === 0 ? <p>No assets yet.</p> : null}
        {imageAssets.length > 0 ? (
          <>
            <h3>Latest Images</h3>
            <div className="asset-grid">
              {imageAssets.slice(0, 8).map((asset) => (
                <article key={asset.id} className="asset-card">
                  <img className="asset-thumb" src={assetUrl(asset.id)} alt={`asset-${asset.id}`} />
                  <p className="small-note">{asset.id.slice(0, 8)}</p>
                  <p className="small-note">engine: {String(asset.meta?.engine ?? "unknown")}</p>
                  <p className="small-note">model: {String(asset.meta?.model_key ?? "unknown")}</p>
                  <p className="small-note">steps: {String(asset.meta?.steps ?? "n/a")}</p>
                  <p className="small-note">guidance: {String(asset.meta?.guidance_scale ?? "n/a")}</p>
                  <p className="small-note">device: {String(asset.meta?.device ?? "unknown")}</p>
                </article>
              ))}
            </div>
          </>
        ) : null}

        {copyAssets.length > 0 ? (
          <>
            <h3>Copy Files</h3>
            <div className="asset-grid">
              {copyAssets.slice(0, 4).map((asset) => (
                <article key={asset.id} className="asset-card">
                  <p>
                    <strong>copy</strong>
                  </p>
                  <p className="small-note">{asset.id.slice(0, 8)}</p>
                  <p className="small-note">{asset.path.split(/[/\\]/).slice(-2).join("/")}</p>
                </article>
              ))}
            </div>
          </>
        ) : null}

        {assets.length > 0 ? <h3>All Assets</h3> : null}
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

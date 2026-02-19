import { useEffect, useMemo, useRef, useState } from "react";
import { BrushCanvas, type BrushCanvasRef } from "../components/BrushCanvas";
import { assetUrl, inpaintImage, listProjectAssets, pollJob, uploadAsset } from "../lib/api";
import type { Asset, RenderMode } from "../types/api";

const CURRENT_PROJECT_KEY = "clipper_current_project_id";

export function EditorPage() {
  const [projectId, setProjectId] = useState(localStorage.getItem(CURRENT_PROJECT_KEY) ?? "");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedImageAssetId, setSelectedImageAssetId] = useState("");
  const [editPrompt, setEditPrompt] = useState("add glossy neon highlights");
  const [strength, setStrength] = useState(0.6);
  const [mode, setMode] = useState<RenderMode>("draft");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Select an image and paint the mask.");
  const brushRef = useRef<BrushCanvasRef>(null);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    localStorage.setItem(CURRENT_PROJECT_KEY, projectId);
    void refreshAssets(projectId);
  }, [projectId]);

  async function refreshAssets(targetProjectId: string) {
    try {
      const result = await listProjectAssets(targetProjectId);
      setAssets(result.assets);
      const firstImage = result.assets.find((asset) => asset.kind === "image");
      if (firstImage && !selectedImageAssetId) {
        setSelectedImageAssetId(firstImage.id);
      }
    } catch (error) {
      setStatus(`Failed to load assets: ${(error as Error).message}`);
    }
  }

  const imageAssets = useMemo(() => assets.filter((asset) => asset.kind === "image"), [assets]);
  const selectedImage = imageAssets.find((asset) => asset.id === selectedImageAssetId) ?? null;

  async function onRunInpaint() {
    if (!projectId || !selectedImageAssetId) {
      setStatus("Set active project and select an image.");
      return;
    }
    if (!brushRef.current) {
      setStatus("Mask canvas is not ready.");
      return;
    }

    setBusy(true);
    setStatus("Exporting mask...");
    try {
      const maskBlob = await brushRef.current.exportMaskBlob();
      if (!maskBlob) {
        throw new Error("Mask export failed.");
      }
      const maskFile = new File([maskBlob], "mask.png", { type: "image/png" });
      const upload = await uploadAsset(projectId, "mask", maskFile);

      const queued = await inpaintImage({
        project_id: projectId,
        image_asset_id: selectedImageAssetId,
        mask_asset_id: upload.asset_id,
        edit_prompt: editPrompt,
        mode,
        strength,
      });
      const finished = await pollJob(queued.job_id, (job) =>
        setStatus(`Inpaint job ${job.status}: ${job.stage} (${job.progress_pct}%)`),
      );
      setStatus(`Inpaint finished: ${finished.job.status}`);
      await refreshAssets(projectId);
      brushRef.current.clear();
    } catch (error) {
      setStatus(`Inpaint failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <h2>Brush Editor</h2>
        <label>
          Active Project ID
          <input
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            placeholder="Paste project ID"
          />
        </label>
        <button disabled={!projectId || busy} type="button" onClick={() => void refreshAssets(projectId)}>
          Refresh Assets
        </button>
        <label>
          Base Image
          <select
            value={selectedImageAssetId}
            onChange={(event) => setSelectedImageAssetId(event.target.value)}
          >
            <option value="">Select image asset</option>
            {imageAssets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.id.slice(0, 8)} | {asset.path.split(/[/\\]/).slice(-1)[0]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Edit Prompt
          <textarea value={editPrompt} onChange={(event) => setEditPrompt(event.target.value)} />
        </label>
        <label>
          Strength: {strength.toFixed(2)}
          <input
            type="range"
            min={0.05}
            max={1}
            step={0.05}
            value={strength}
            onChange={(event) => setStrength(Number(event.target.value))}
          />
        </label>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as RenderMode)}>
            <option value="draft">Draft</option>
            <option value="hq">HQ</option>
          </select>
        </label>
        <div className="inline-actions">
          <button disabled={busy || !selectedImage} type="button" onClick={() => void onRunInpaint()}>
            Apply Inpaint
          </button>
          <button disabled={busy} type="button" onClick={() => brushRef.current?.clear()}>
            Clear Mask
          </button>
        </div>
        <p className="status">{status}</p>
      </section>

      <section className="panel panel-wide">
        <h2>Mask Canvas</h2>
        {selectedImage ? (
          <BrushCanvas
            ref={brushRef}
            width={540}
            height={540}
            backgroundUrl={assetUrl(selectedImage.id)}
            brushSize={30}
          />
        ) : (
          <p>Select an image asset to enable brush editing.</p>
        )}
      </section>
    </div>
  );
}

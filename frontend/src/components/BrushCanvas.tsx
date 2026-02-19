import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type PointerEvent,
} from "react";

export interface BrushCanvasRef {
  clear: () => void;
  exportMaskBlob: () => Promise<Blob | null>;
}

interface BrushCanvasProps {
  width: number;
  height: number;
  backgroundUrl?: string;
  brushSize?: number;
}

export const BrushCanvas = forwardRef<BrushCanvasRef, BrushCanvasProps>(function BrushCanvas(
  { width, height, backgroundUrl, brushSize = 24 },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [painting, setPainting] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }
    ctx.fillStyle = "black";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }, [width, height]);

  useImperativeHandle(
    ref,
    () => ({
      clear() {
        const canvas = canvasRef.current;
        if (!canvas) {
          return;
        }
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          return;
        }
        ctx.fillStyle = "black";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      },
      async exportMaskBlob() {
        const canvas = canvasRef.current;
        if (!canvas) {
          return null;
        }
        return await new Promise<Blob | null>((resolve) =>
          canvas.toBlob((blob) => resolve(blob), "image/png"),
        );
      },
    }),
    [],
  );

  function drawAtPoint(event: PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }
    ctx.fillStyle = "white";
    ctx.beginPath();
    ctx.arc(x, y, brushSize / 2, 0, 2 * Math.PI);
    ctx.fill();
  }

  return (
    <div className="brush-wrap" style={{ width, height }}>
      {backgroundUrl ? <img className="brush-bg" src={backgroundUrl} alt="Base" /> : null}
      <canvas
        ref={canvasRef}
        className="brush-canvas"
        width={width}
        height={height}
        onPointerDown={(event) => {
          setPainting(true);
          drawAtPoint(event);
        }}
        onPointerMove={(event) => {
          if (!painting) {
            return;
          }
          drawAtPoint(event);
        }}
        onPointerUp={() => setPainting(false)}
        onPointerLeave={() => setPainting(false)}
      />
    </div>
  );
});


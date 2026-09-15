import { useState } from "react";
import { Eye, EyeOff, Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AssessmentImage, Detection } from "@/types/claim";

function formatClass(value: string) {
  return value.replace(/_/g, " ");
}

/**
 * Renders YOLO detections over the frame. Boxes are supplied in the image's
 * native pixel space and converted to percentages, so they stay accurate at
 * any rendered size.
 */
export function AnnotatedImage({ image }: { image: AssessmentImage }) {
  const [showBoxes, setShowBoxes] = useState(true);
  const [active, setActive] = useState<string | null>(null);

  const rect = (d: Detection) => ({
    left: `${(d.bbox.x / image.native_width) * 100}%`,
    top: `${(d.bbox.y / image.native_height) * 100}%`,
    width: `${(d.bbox.width / image.native_width) * 100}%`,
    height: `${(d.bbox.height / image.native_height) * 100}%`,
  });

  return (
    <figure className="overflow-hidden rounded-md border border-border bg-shell">
      <div className="flex items-center justify-between gap-3 border-b border-shell-border px-3 py-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-xs text-shell-foreground">{image.filename}</p>
          <p className="tech-label text-shell-muted">
            {image.native_width}×{image.native_height} px · {image.detections.length} detections
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowBoxes((v) => !v)}
          aria-pressed={showBoxes}
          className="focus-ring tech-label inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-shell-border px-2 py-1 text-shell-muted transition-colors hover:bg-shell-elevated hover:text-shell-foreground"
        >
          {showBoxes ? <EyeOff className="size-3" aria-hidden /> : <Eye className="size-3" aria-hidden />}
          {showBoxes ? "Hide boxes" : "Show boxes"}
        </button>
      </div>

      <div
        className="relative w-full select-none"
        style={{ aspectRatio: `${image.native_width} / ${image.native_height}` }}
      >
        <img
          src={image.url}
          alt={`Vehicle damage frame ${image.filename}`}
          loading="lazy"
          width={image.native_width}
          height={image.native_height}
          className="absolute inset-0 size-full object-cover"
        />
        {showBoxes &&
          image.detections.map((d) => (
            <div
              key={d.id}
              style={rect(d)}
              onMouseEnter={() => setActive(d.id)}
              onMouseLeave={() => setActive(null)}
              className={cn(
                "absolute border-2 transition-all duration-200",
                active === d.id
                  ? "border-steel bg-steel/20 shadow-[0_0_0_9999px_rgba(12,16,22,0.35)]"
                  : "border-steel/80 bg-steel/5",
              )}
            >
              <span className="tech-label absolute -top-[1px] left-0 -translate-y-full whitespace-nowrap rounded-t-sm bg-steel px-1.5 py-0.5 text-shell-foreground">
                {formatClass(d.damage_class)} · {(d.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
      </div>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-shell-border px-3 py-2 text-shell-muted">
        <span className="tech-label inline-flex items-center gap-1.5">
          <Maximize2 className="size-3" aria-hidden />
          Boxes scaled from native resolution
        </span>
      </figcaption>
    </figure>
  );
}

import { useRef, useState } from "react";
import { UploadCloud, X, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function UploadDropzone({
  files,
  onChange,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const add = (list: FileList | null) => {
    if (!list) return;
    const images = Array.from(list).filter((f) => f.type.startsWith("image/"));
    onChange([...files, ...images].slice(0, 6));
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabled) add(e.dataTransfer.files);
        }}
        className={cn(
          "rounded-md border-2 border-dashed p-6 text-center transition-colors",
          dragging ? "border-primary bg-accent/60" : "border-border bg-card",
          disabled && "opacity-60",
        )}
      >
        <UploadCloud className="mx-auto size-7 text-muted-foreground" aria-hidden />
        <p className="mt-3 text-sm font-medium">Drop assessment images here</p>
        <p className="mt-1 text-xs text-muted-foreground">
          JPG or PNG · up to 6 frames · wide plus close detail angles
        </p>
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          className="focus-ring mt-4 inline-flex items-center gap-2 rounded-sm border border-input bg-background px-3 py-2 text-sm transition-colors hover:bg-accent disabled:cursor-not-allowed"
        >
          <ImageIcon className="size-4" aria-hidden />
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          aria-label="Assessment images"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {files.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="group relative overflow-hidden rounded-sm border border-border bg-card"
            >
              <img
                src={URL.createObjectURL(file)}
                alt={file.name}
                className="aspect-[4/3] w-full object-cover"
              />
              <p className="truncate px-2 py-1.5 font-mono text-[11px] text-muted-foreground">
                {file.name}
              </p>
              <button
                type="button"
                onClick={() => onChange(files.filter((_, idx) => idx !== i))}
                aria-label={`Remove ${file.name}`}
                className="focus-ring absolute right-1.5 top-1.5 rounded-sm bg-shell/80 p-1 text-shell-foreground opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"""Reproducible, non-destructive preparation of validated YOLO datasets."""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.dataset_validation import ValidationReport, validate_yolo_archive


@dataclass(frozen=True)
class PreparedDataset:
    root: Path
    data_yaml: Path
    manifest: Path
    validation: ValidationReport


SUPPORTED_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})


class InvalidImageError(ValueError):
    """Raised when a user-supplied file is not a supported readable image."""


@dataclass(frozen=True)
class ValidatedImage:
    path: Path
    width: int
    height: int
    format: str


def validate_inference_image(image_path: str | Path) -> ValidatedImage:
    """Validate an image for inference without modifying its contents.

    Model inputs are deliberately limited to formats the service explicitly
    supports. Pillow verifies image integrity before YOLO opens the file.
    """
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise InvalidImageError("Image file does not exist")
    if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise InvalidImageError(f"Unsupported image type: {path.suffix or 'no extension'}")
    # Recent Ultralytics releases monkey-patch ``PIL.Image.open`` and, on any
    # decode failure, try to install optional HEIF support.  Upload validation
    # must never alter the environment, especially for an invalid JPEG/PNG.
    # If that patch is present, use its preserved original Pillow opener.
    patches = sys.modules.get("ultralytics.utils.patches")
    image_open = getattr(patches, "_image_open", Image.open)
    try:
        with image_open(path) as image:
            image.verify()
        with image_open(path) as image:
            width, height = image.size
            image_format = image.format or path.suffix.lstrip(".").upper()
    # Ultralytics patches Pillow for optional HEIF support. When pi-heif is not
    # installed, corrupt/non-HEIF inputs can surface as ModuleNotFoundError;
    # callers must still receive the same safe invalid-image response.
    except (UnidentifiedImageError, OSError, ValueError, ModuleNotFoundError) as exc:
        raise InvalidImageError("Image could not be read safely") from exc
    if width < 1 or height < 1:
        raise InvalidImageError("Image dimensions must be positive")
    return ValidatedImage(path=path, width=width, height=height, format=image_format)


def materialize_validated_yolo_dataset(archive_path: str | Path, destination_parent: str | Path) -> PreparedDataset:
    """Extract a validated archive once, preserving its source archive unchanged.

    The destination uses the archive SHA prefix. Existing materializations are
    reused only when their manifest records the identical source hash.
    """
    archive = Path(archive_path).resolve()
    validation = validate_yolo_archive(archive)
    if not validation.is_valid:
        raise ValueError("Refusing to materialize an invalid dataset: " + "; ".join(validation.errors[:5]))

    destination = Path(destination_parent).resolve() / f"severity_{validation.archive_sha256[:12]}"
    manifest = destination / "dataset_manifest.json"
    if destination.exists():
        if not manifest.is_file():
            raise FileExistsError(f"Refusing to reuse untracked dataset directory: {destination}")
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        if existing.get("archive_sha256") != validation.archive_sha256:
            raise FileExistsError(f"Dataset directory has a different source identity: {destination}")
        return PreparedDataset(destination, destination / validation.dataset_root / "data.yaml", manifest, validation)

    staging = destination.with_name(destination.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"Refusing to overwrite interrupted staging directory: {staging}")
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as source:
            root_prefix = validation.dataset_root.rstrip("/") + "/"
            members = [name for name in source.namelist() if name.startswith(root_prefix) and not name.endswith("/")]
            if not members:
                raise ValueError("Validated dataset root has no extractable files")
            for member in members:
                relative = Path(member[len(root_prefix) :])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Unsafe archive member: {member}")
                target = staging / validation.dataset_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_stream, target.open("wb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)
        metadata = {
            "archive": str(archive),
            "archive_sha256": validation.archive_sha256,
            "dataset_root": validation.dataset_root,
            "class_names": validation.class_names,
            "split_images": validation.split_images,
            "split_labels": validation.split_labels,
            "validation_report": validation.to_dict(),
        }
        (staging / "dataset_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        staging.rename(destination)
    except Exception:
        # Preserve failed staging output for inspection instead of deleting it.
        raise
    return PreparedDataset(destination, destination / validation.dataset_root / "data.yaml", manifest, validation)

// Field validation and slug/filename derivation for incoming submissions.
//
// This mirrors (but does not need to exactly match) the authoritative
// slug/filename logic in scripts/generate_listing.py. The Worker only uses
// its own derivation to name the branch and any image files it commits
// itself, then passes those exact paths through to the workflow — so a
// JS/Python slugification mismatch can't cause a broken listing.

export const CATEGORIES = [
  "Archivers",
  "Browsers",
  "Chat",
  "FTP Clients",
  "IP Cams",
  "Multimedia",
  "Network",
  "Others",
  "SD Cards",
  "SSH Clients",
  "Sys info",
  "Text Editors",
] as const;

export const ALLOWED_IMAGE_TYPES: Record<string, string> = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/webp": "webp",
};

export const MAX_ICON_BYTES = 300 * 1024;
export const MAX_SCREENSHOT_BYTES = 1024 * 1024;

export class ValidationError extends Error {}

export function slugify(value: string): string {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (slug || "app").slice(0, 60);
}

export function safeImageBasename(appName: string): string {
  const cleaned = appName.replace(/[/\\:*?"<>|]/g, "").trim();
  return cleaned || "App";
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export interface ImageInput {
  mode: "url" | "file";
  url?: string;
  file?: File;
}

export interface ValidatedFields {
  appName: string;
  category: string;
  tags: string;
  summary: string;
  homepageUrl: string;
  downloadUrl: string;
  portableUrl: string | null;
  icon: ImageInput;
  screenshot: ImageInput;
  turnstileToken: string;
}

function requireText(formData: FormData, field: string, maxLength: number): string {
  const raw = formData.get(field);
  if (typeof raw !== "string" || !raw.trim()) {
    throw new ValidationError(`${field} is required`);
  }
  const value = raw.trim();
  if (value.length > maxLength) {
    throw new ValidationError(`${field} must be ${maxLength} characters or fewer`);
  }
  return value;
}

function requireUrl(formData: FormData, field: string): string {
  const value = requireText(formData, field, 2000);
  if (!isHttpUrl(value)) {
    throw new ValidationError(`${field} must be a valid http(s) URL`);
  }
  return value;
}

function optionalUrl(formData: FormData, field: string): string | null {
  const raw = formData.get(field);
  if (typeof raw !== "string" || !raw.trim()) {
    return null;
  }
  const value = raw.trim();
  if (value.length > 2000 || !isHttpUrl(value)) {
    throw new ValidationError(`${field} must be a valid http(s) URL`);
  }
  return value;
}

function readImageInput(
  formData: FormData,
  field: "icon" | "screenshot",
  maxBytes: number
): ImageInput {
  const mode = formData.get(`${field}_mode`);
  if (mode === "file") {
    const file = formData.get(`${field}_file`);
    if (!(file instanceof File) || file.size === 0) {
      throw new ValidationError(`${field}_file is required when upload mode is selected`);
    }
    if (!(file.type in ALLOWED_IMAGE_TYPES)) {
      throw new ValidationError(`${field}_file must be PNG, JPEG or WebP`);
    }
    if (file.size > maxBytes) {
      throw new ValidationError(`${field}_file exceeds the ${maxBytes} byte limit`);
    }
    return { mode: "file", file };
  }

  if (mode === "url") {
    const url = requireText(formData, `${field}_url`, 2000);
    if (!isHttpUrl(url)) {
      throw new ValidationError(`${field}_url must be a valid http(s) URL`);
    }
    return { mode: "url", url };
  }

  throw new ValidationError(`${field}_mode must be "url" or "file"`);
}

export function validateFormFields(formData: FormData): ValidatedFields {
  const appName = requireText(formData, "app_name", 100);

  const category = requireText(formData, "category", 50);
  if (!(CATEGORIES as readonly string[]).includes(category)) {
    throw new ValidationError(`Unknown category: ${category}`);
  }

  const tagsRaw = requireText(formData, "tags", 200);
  const tags = tagsRaw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .join(", ");
  if (!tags) {
    throw new ValidationError("At least one tag is required");
  }

  const summary = requireText(formData, "summary", 600);
  const homepageUrl = requireUrl(formData, "homepage_url");
  const downloadUrl = requireUrl(formData, "download_url");
  const portableUrl = optionalUrl(formData, "portable_url");

  const icon = readImageInput(formData, "icon", MAX_ICON_BYTES);
  const screenshot = readImageInput(formData, "screenshot", MAX_SCREENSHOT_BYTES);

  const turnstileToken = formData.get("cf-turnstile-response");
  if (typeof turnstileToken !== "string" || !turnstileToken) {
    throw new ValidationError("Turnstile verification token is missing");
  }

  return {
    appName,
    category,
    tags,
    summary,
    homepageUrl,
    downloadUrl,
    portableUrl,
    icon,
    screenshot,
    turnstileToken,
  };
}

import { GitHubApiError, GitHubClient } from "./github";
import { verifyTurnstile } from "./turnstile";
import {
  ALLOWED_IMAGE_TYPES,
  ImageInput,
  ValidationError,
  safeImageBasename,
  slugify,
  validateFormFields,
} from "./validate";

const DISPATCH_EVENT_TYPE = "new-listing";
const MAX_SLUG_ATTEMPTS = 5;

function corsHeaders(allowedOrigin: string): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": allowedOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function jsonResponse(body: unknown, status: number, allowedOrigin: string): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(allowedOrigin),
    },
  });
}

async function resolveUniqueSlug(github: GitHubClient, appName: string): Promise<string> {
  const base = slugify(appName);
  for (let attempt = 0; attempt < MAX_SLUG_ATTEMPTS; attempt++) {
    const candidate = attempt === 0 ? base : `${base}-${attempt + 1}`;
    if (!(await github.slugTaken(candidate))) {
      return candidate;
    }
  }
  // Fall back to a random suffix rather than failing the submission outright.
  return `${base}-${crypto.randomUUID().slice(0, 6)}`;
}

async function resolveImageForCommit(
  github: GitHubClient,
  field: "icon" | "screenshot",
  image: ImageInput,
  appName: string,
  branch: string
): Promise<Record<string, string>> {
  if (image.mode === "url") {
    return { type: "url", value: image.url! };
  }

  const file = image.file!;
  const ext = ALLOWED_IMAGE_TYPES[file.type];
  const basename = safeImageBasename(appName);
  const dir = field === "screenshot" ? "content/images/screenshots" : "content/images";
  const path = `${dir}/${basename}.${ext}`;

  await github.commitFile({
    path,
    content: await file.arrayBuffer(),
    branch,
    message: `Add ${field} image for '${appName}' submission`,
  });

  return { type: "committed", path };
}

async function handleSubmit(request: Request, env: Env): Promise<Response> {
  const allowedOrigin = env.ALLOWED_ORIGIN;

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return jsonResponse({ ok: false, error: "Request body must be multipart/form-data" }, 400, allowedOrigin);
  }

  let fields;
  try {
    fields = validateFormFields(formData);
  } catch (err) {
    if (err instanceof ValidationError) {
      return jsonResponse({ ok: false, error: err.message }, 400, allowedOrigin);
    }
    throw err;
  }

  const turnstileOk = await verifyTurnstile(
    fields.turnstileToken,
    env.TURNSTILE_SECRET_KEY,
    request.headers.get("CF-Connecting-IP")
  );
  if (!turnstileOk) {
    return jsonResponse({ ok: false, error: "Verification challenge failed, please try again" }, 400, allowedOrigin);
  }

  const github = new GitHubClient({
    owner: env.GITHUB_OWNER,
    repo: env.GITHUB_REPO,
    baseBranch: env.GITHUB_BASE_BRANCH,
    token: env.GITHUB_PAT,
  });

  try {
    const slug = await resolveUniqueSlug(github, fields.appName);
    const branch = `listing/${slug}-${crypto.randomUUID().slice(0, 6)}`;
    const baseSha = await github.getBaseBranchSha();
    await github.createBranch(branch, baseSha);

    const icon = await resolveImageForCommit(github, "icon", fields.icon, fields.appName, branch);
    const screenshot = await resolveImageForCommit(github, "screenshot", fields.screenshot, fields.appName, branch);

    await github.dispatch(DISPATCH_EVENT_TYPE, {
      branch,
      app_name: fields.appName,
      category: fields.category,
      tags: fields.tags,
      summary: fields.summary,
      homepage_url: fields.homepageUrl,
      download_url: fields.downloadUrl,
      portable_url: fields.portableUrl,
      icon,
      screenshot,
    });
  } catch (err) {
    if (err instanceof GitHubApiError) {
      console.error("GitHub API error while processing submission", err);
      return jsonResponse(
        { ok: false, error: "Could not submit your listing right now, please try again later" },
        502,
        allowedOrigin
      );
    }
    throw err;
  }

  return jsonResponse({ ok: true }, 200, allowedOrigin);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const allowedOrigin = env.ALLOWED_ORIGIN;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(allowedOrigin) });
    }

    if (request.method !== "POST") {
      return jsonResponse({ ok: false, error: "Method not allowed" }, 405, allowedOrigin);
    }

    try {
      return await handleSubmit(request, env);
    } catch (err) {
      console.error("Unhandled error processing submission", err);
      return jsonResponse({ ok: false, error: "Unexpected error, please try again later" }, 500, allowedOrigin);
    }
  },
} satisfies ExportedHandler<Env>;

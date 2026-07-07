#!/usr/bin/env python3
"""Turn a community "new app" submission (repository_dispatch client_payload)
into a content/<slug>.html listing, matching the site's existing format.

Invoked by .github/workflows/new-listing.yml as two steps:
  --step download-images  fetches any URL-sourced icon/screenshot images
  --step write-html       renders content/<slug>.html and pr_body.md

Untrusted submitter input is passed in via the PAYLOAD_JSON environment
variable rather than command-line arguments or shell interpolation.
"""
import argparse
import html
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
IMAGES_DIR = CONTENT_DIR / "images"
SCREENSHOTS_DIR = IMAGES_DIR / "screenshots"

ALLOWED_CATEGORIES = {
    "Archivers", "Browsers", "Chat", "FTP Clients", "IP Cams", "Multimedia",
    "Network", "Others", "SD Cards", "SSH Clients", "Sys info", "Text Editors",
}

ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB ceiling for URL-sourced downloads


def load_payload():
    raw = os.environ.get("PAYLOAD_JSON")
    if not raw:
        sys.exit("PAYLOAD_JSON environment variable is required")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"PAYLOAD_JSON is not valid JSON: {exc}")


def resolved_payload_cache_path():
    base = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    return Path(base) / "winapps-listing-payload.json"


def slugify(value):
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:60] or "app"


def unique_slug(base_slug):
    slug = base_slug
    n = 2
    while (CONTENT_DIR / f"{slug}.html").exists():
        slug = f"{base_slug}-{n}"
        n += 1
    return slug


def safe_image_basename(app_name):
    # Mirrors the existing convention: icon/screenshot filenames use the
    # app's display name verbatim (Title Case with spaces), not the slug.
    cleaned = re.sub(r'[\/\\:*?"<>|]', "", app_name).strip()
    return cleaned or "App"


def guess_extension(content_type, url):
    if content_type:
        content_type = content_type.split(";")[0].strip().lower()
        if content_type in ALLOWED_CONTENT_TYPES:
            return ALLOWED_CONTENT_TYPES[content_type]
    ext = Path(urllib.parse.urlparse(url).path).suffix.lstrip(".").lower()
    if ext == "jpeg":
        return "jpg"
    if ext in ("png", "jpg", "webp"):
        return ext
    return None


def download_image(url, dest_dir, basename):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        sys.exit(f"Rejected image URL, must be http(s): {url!r}")

    request = urllib.request.Request(url, headers={"User-Agent": "winapps-listing-bot/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        content_type = response.headers.get("Content-Type", "")
        ext = guess_extension(content_type, url)
        if ext is None:
            sys.exit(f"Rejected image download from {url}: unsupported content type {content_type!r}")
        data = response.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            sys.exit(f"Rejected image download from {url}: exceeds {MAX_IMAGE_BYTES} bytes")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{basename}.{ext}"
    dest_path.write_bytes(data)
    return dest_path


def resolve_image(field, payload, app_name):
    """Ensures the image for `field` exists in the repo (downloading it if
    it was submitted as a URL), and returns its site-relative src path.

    Mutates payload[field] in place to the "committed" shape once resolved,
    so a cached payload can be reused across steps without re-downloading.
    """
    image = payload.get(field)
    if not image or "type" not in image:
        sys.exit(f"Missing required image field: {field}")

    if image["type"] == "committed":
        repo_relative = image["path"]
    elif image["type"] == "url":
        basename = safe_image_basename(app_name)
        dest_dir = SCREENSHOTS_DIR if field == "screenshot" else IMAGES_DIR
        dest_path = download_image(image["value"], dest_dir, basename)
        repo_relative = str(dest_path.relative_to(REPO_ROOT)).replace(os.sep, "/")
        image["type"] = "committed"
        image["path"] = repo_relative
    else:
        sys.exit(f"Unknown image type for {field}: {image['type']!r}")

    full_path = REPO_ROOT / repo_relative
    if not full_path.is_file():
        sys.exit(f"Expected {field} image at {repo_relative}, but it's missing")

    return "/" + repo_relative.split("content/", 1)[-1]


def step_download_images(payload):
    app_name = payload["app_name"]
    for field in ("icon", "screenshot"):
        resolve_image(field, payload, app_name)
    resolved_payload_cache_path().write_text(json.dumps(payload))


def validate_url_field(payload, field, required):
    value = (payload.get(field) or "").strip()
    if not value:
        if required:
            sys.exit(f"{field} is required")
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        sys.exit(f"{field} must be a valid http(s) URL")
    return value


def normalize_tags(raw_tags):
    parts = [p.strip() for p in (raw_tags or "").split(",")]
    parts = [p for p in parts if p]
    if not parts:
        sys.exit("At least one tag is required")
    return ", ".join(parts)


LISTING_TEMPLATE = """<html>
<head>
<title>{title}</title>
<meta name="date" content="{date}">
<meta name="category" content="{category}">
<meta name="tags" content="{tags}">
<meta name="slug" content="{slug}">
<meta name="summary" content="{summary}">
<meta name="image" content="{icon_src}">
</head>
<body>
<img alt="{title}" src="{icon_src}" style="float:left;margin-right:30px;margin-top:8px;margin-bottom:10px;"/>
<h2>{title}</h2>
<p>{summary}</p>
<div style="clear: left;"></div>
<br/>
<h3>{title} Screen Shot</h3>
<img class="img-fluid" src="{screenshot_src}" style="max-width: 100%; height: auto; display: block; "/><br/><br/>
<div class="row">
<br/>
</div>
<p></p>
<a class="btn btn-primary" href="{homepage_url}" rel="nofollow" style="text-decoration: none" target="_blank"><i class="fa fa-home"></i>  {title} Home Page</a> <br/><br/>
<a class="btn btn-warning" href="{download_url}" rel="nofollow" style="text-decoration: none" target="_blank"><i class="fa fa-download"></i> Download {title}</a><br/><br/>
{portable_button}</body>
</html>
"""

PORTABLE_BUTTON_TEMPLATE = (
    '<a class="btn btn-danger" href="{portable_url}" rel="nofollow" '
    'style="text-decoration: none" target="_blank">'
    '<i class="fa fa-suitcase"></i>  {title} Portable Version</a><br/><br/>\n'
)

PR_BODY_TEMPLATE = """## New app submission: {title}

| Field | Value |
|---|---|
| Category | {category} |
| Tags | {tags} |
| Homepage | {homepage_url} |
| Download | {download_url} |
| Portable version | {portable_display} |

**Summary**

> {summary}

---
Auto-generated from a public submission on the site. Please review before merging — this PR is never auto-merged.
"""


def step_write_html(payload):
    cache = resolved_payload_cache_path()
    if cache.exists():
        payload = json.loads(cache.read_text())

    app_name = (payload.get("app_name") or "").strip()
    if not app_name:
        sys.exit("app_name is required")
    if len(app_name) > 100:
        sys.exit("app_name must be 100 characters or fewer")

    category = payload.get("category")
    if category not in ALLOWED_CATEGORIES:
        sys.exit(f"Unknown category: {category!r}")

    summary = (payload.get("summary") or "").strip()
    if not summary or len(summary) > 600:
        sys.exit("summary is required and must be 600 characters or fewer")

    tags = normalize_tags(payload.get("tags"))
    homepage_url = validate_url_field(payload, "homepage_url", required=True)
    download_url = validate_url_field(payload, "download_url", required=True)
    portable_url = validate_url_field(payload, "portable_url", required=False)

    slug = unique_slug(slugify(app_name))
    icon_src = resolve_image("icon", payload, app_name)
    screenshot_src = resolve_image("screenshot", payload, app_name)

    title = html.escape(app_name)
    portable_button = ""
    if portable_url:
        portable_button = PORTABLE_BUTTON_TEMPLATE.format(
            portable_url=html.escape(portable_url), title=title
        )

    listing_html = LISTING_TEMPLATE.format(
        title=title,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        category=html.escape(category),
        tags=html.escape(tags),
        slug=slug,
        summary=html.escape(summary),
        icon_src=html.escape(icon_src),
        screenshot_src=html.escape(screenshot_src),
        homepage_url=html.escape(homepage_url),
        download_url=html.escape(download_url),
        portable_button=portable_button,
    )

    dest = CONTENT_DIR / f"{slug}.html"
    dest.write_text(listing_html)

    pr_body = PR_BODY_TEMPLATE.format(
        title=app_name,
        category=category,
        tags=tags,
        homepage_url=homepage_url,
        download_url=download_url,
        portable_display=portable_url or "—",
        summary=summary,
    )
    (REPO_ROOT / "pr_body.md").write_text(pr_body)

    print(f"Wrote {dest.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True, choices=["download-images", "write-html"])
    args = parser.parse_args()

    payload = load_payload()

    if args.step == "download-images":
        step_download_images(payload)
    elif args.step == "write-html":
        step_write_html(payload)


if __name__ == "__main__":
    main()

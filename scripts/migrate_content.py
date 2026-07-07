#!/usr/bin/env python3
"""One-off migration of content/*.html bodies from the legacy Bootstrap/Font
Awesome markup to the redesigned framework-free markup.

Rewrites, inside <body> only (head metadata bytes are left untouched):
  - the floated app icon         -> <img class="app-icon">
  - "X Screen Shot" h3 + img     -> <figure class="app-screenshot">
  - Bootstrap col-sm-6 pros/cons -> <section class="pros-cons"> with real <ul>s
  - btn-primary/warning/danger/success links -> one <p class="app-links"> with
    btn-home/btn-download/btn-portable/btn-screens (Download promoted first)
  - layout junk: div.row wrappers, clear:left divs, empty <p>, stray <br>

Safety: per file, every original href must survive, and the body's visible
text (as a word multiset, minus the dropped "X Screen Shot" headings) must be
unchanged. Files failing the invariant are reported and left unmodified.

Usage:  migrate_content.py [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

BUTTON_CLASS_MAP = {
    "btn-primary": "btn-home",
    "btn-warning": "btn-download",
    "btn-danger": "btn-portable",
    "btn-success": "btn-screens",
}
BUTTON_ORDER = ["btn-download", "btn-home", "btn-portable", "btn-screens"]


def words(text):
    return sorted(re.sub(r"[\s\xa0]+", " ", text).split())


def norm_text(value):
    return re.sub(r"[\s\xa0]+", " ", value).strip()


def is_screenshot_heading(tag):
    if not (isinstance(tag, Tag) and tag.name == "h3"):
        return False
    text = norm_text(tag.get_text())
    return text.endswith("Screen Shot") or text.endswith("Screen Shots")


def migrate_icon(soup):
    for img in soup.body.find_all("img"):
        style = img.get("style", "")
        if "float" in style.replace(" ", ""):
            img["class"] = ["app-icon"]
            del img["style"]
            img["width"] = "128"
            img["height"] = "128"
            return True
    return False


def migrate_screenshot(soup, title):
    changed = False
    for h3 in soup.body.find_all(is_screenshot_heading):
        img = h3.find_next("img")
        if img is None:
            h3.decompose()
            continue
        figure = soup.new_tag("figure", attrs={"class": "app-screenshot"})
        new_img = soup.new_tag(
            "img",
            attrs={
                "src": img.get("src", ""),
                "alt": f"{title} screenshot",
                "loading": "lazy",
            },
        )
        figure.append(new_img)
        img.replace_with(figure)
        h3.decompose()
        changed = True
    return changed


def extract_pros_cons_items(div, heading):
    """Items are delimited by <i class="fa fa-plus/minus"> markers with the
    item text (and <br> separators) following each marker."""
    items = []
    current = None
    for node in div.descendants:
        if isinstance(node, Tag) and node.name == "i":
            if current is not None and norm_text(current):
                items.append(norm_text(current))
            current = ""
        elif isinstance(node, NavigableString) and current is not None:
            if node.find_parent("h3") is None:
                current += str(node)
    if current is not None and norm_text(current):
        items.append(norm_text(current))
    return items


def migrate_pros_cons(soup):
    new_divs = []
    for div in soup.body.find_all("div", class_="col-sm-6"):
        h3 = div.find("h3")
        if h3 is None:
            continue
        heading = norm_text(h3.get_text())
        if heading not in ("Pros", "Cons"):
            continue
        items = extract_pros_cons_items(div, heading)
        kind = heading.lower()
        new_div = soup.new_tag("div", attrs={"class": kind})
        new_h3 = soup.new_tag("h3")
        new_h3.string = heading
        new_div.append(new_h3)
        ul = soup.new_tag("ul")
        for item in items:
            li = soup.new_tag("li")
            li.string = item
            ul.append(li)
        new_div.append(ul)
        div.replace_with(new_div)
        new_divs.append(new_div)
    if new_divs:
        section = soup.new_tag("section", attrs={"class": "pros-cons"})
        new_divs[0].insert_before(section)
        for div in new_divs:
            section.append(div.extract())
    return bool(new_divs)


def migrate_buttons(soup):
    buttons = []
    for a in soup.body.find_all("a", class_="btn"):
        classes = a.get("class", [])
        new_class = next(
            (BUTTON_CLASS_MAP[c] for c in classes if c in BUTTON_CLASS_MAP), None
        )
        if new_class is None:
            continue
        label = norm_text(a.get_text())
        new_a = soup.new_tag(
            "a",
            attrs={
                "class": f"btn {new_class}",
                "href": a.get("href", ""),
                "rel": "nofollow noopener",
                "target": "_blank",
            },
        )
        new_a.string = label
        buttons.append((new_class, new_a))
        a.decompose()
    if not buttons:
        return 0
    buttons.sort(key=lambda pair: BUTTON_ORDER.index(pair[0]))
    p = soup.new_tag("p", attrs={"class": "app-links"})
    for _, new_a in buttons:
        p.append(new_a)
        p.append("\n")
    soup.body.append(p)
    return len(buttons)


def cleanup(soup):
    for div in soup.body.find_all("div"):
        if "clear" in div.get("style", ""):
            div.decompose()
    for div in soup.body.find_all("div", class_="row"):
        div.unwrap()
    for br in list(soup.body.children):
        if isinstance(br, Tag) and br.name == "br":
            br.decompose()
    for p in soup.body.find_all("p"):
        if not norm_text(p.get_text()) and not p.find(True):
            p.decompose()
    # drop <br> runs left dangling directly in body or trailing inside body
    for br in soup.body.find_all("br", recursive=False):
        br.decompose()


def migrate_file(path, dry_run):
    original = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(original, "html.parser")
    if soup.body is None or soup.head is None:
        return f"SKIP  {path.name}: no <body>/<head>"

    title = norm_text(soup.title.get_text()) if soup.title else path.stem

    before_hrefs = sorted(
        a.get("href", "") for a in soup.body.find_all("a") if a.get("href")
    )
    dropped_headings = " ".join(
        norm_text(h3.get_text()) for h3 in soup.body.find_all(is_screenshot_heading)
    )
    before_words = words(soup.body.get_text(" ") + " ")
    for word in words(dropped_headings):
        before_words.remove(word)

    icon = migrate_icon(soup)
    shot = migrate_screenshot(soup, title)
    proscons = migrate_pros_cons(soup)
    nbuttons = migrate_buttons(soup)
    cleanup(soup)

    after_hrefs = sorted(
        a.get("href", "") for a in soup.body.find_all("a") if a.get("href")
    )
    after_words = words(soup.body.get_text(" "))

    problems = []
    if before_hrefs != after_hrefs:
        problems.append(
            f"href mismatch: -{set(before_hrefs) - set(after_hrefs)} "
            f"+{set(after_hrefs) - set(before_hrefs)}"
        )
    if before_words != after_words:
        missing = [w for w in before_words if w not in list(after_words)]
        added = [w for w in after_words if w not in list(before_words)]
        problems.append(f"text mismatch: -{missing[:10]} +{added[:10]}")
    if not icon:
        problems.append("no icon found")

    status = (
        f"{'FAIL' if problems else 'OK  '}  {path.name}: "
        f"buttons={nbuttons} screenshot={'y' if shot else '-'} "
        f"proscons={'y' if proscons else '-'}"
    )
    if problems:
        return status + "\n      " + "\n      ".join(problems)

    if not dry_run:
        # splice the migrated body back, leaving <head> bytes untouched
        start = original.index("<body>") + len("<body>")
        end = original.rindex("</body>")
        new_body = "".join(str(c) for c in soup.body.contents)
        new_body = re.sub(r"\n{3,}", "\n\n", new_body).strip("\n")
        path.write_text(
            original[:start] + "\n" + new_body + "\n" + original[end:],
            encoding="utf-8",
        )
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = sorted(p for p in CONTENT_DIR.glob("*.html"))
    failures = 0
    for path in files:
        report = migrate_file(path, args.dry_run)
        if "FAIL" in report or "SKIP" in report:
            failures += 1
            print(report)
        elif args.dry_run:
            print(report)
    print(f"\n{len(files)} files processed, {failures} failed"
          f"{' (dry run, nothing written)' if args.dry_run else ''}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

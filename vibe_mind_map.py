"""vibe-mind-map — Generate interactive mind maps from GitHub project state.

Usage:
    python vibe_mind_map.py --repo qzyu999/inference-exchange
    python vibe_mind_map.py --repo qzyu999/inference-exchange --milestone Alpha
    python vibe_mind_map.py --repo qzyu999/inference-exchange --watch
    python vibe_mind_map.py --repo qzyu999/inference-exchange --output map.html
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Issue:
    number: int
    title: str
    state: str
    milestone: str
    labels: list[str]
    url: str
    body: str = ""
    depends_on: list[int] = field(default_factory=list)
    blocks: list[int] = field(default_factory=list)


@dataclass
class Milestone:
    title: str
    description: str
    open_count: int
    closed_count: int
    issues: list[Issue] = field(default_factory=list)


@dataclass
class PullRequest:
    number: int
    title: str
    state: str  # OPEN, MERGED, CLOSED
    url: str
    head_branch: str
    additions: int
    deletions: int
    changed_files: int
    closes_issues: list[int] = field(default_factory=list)


def fetch_issues(repo: str) -> list[Issue]:
    """Fetch all issues from a GitHub repo using gh CLI."""
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "200",
         "--json", "number,title,state,milestone,labels,url,body"],
        capture_output=True, text=True, check=True,
    )
    raw = json.loads(result.stdout)
    issues = []
    for item in raw:
        milestone = item.get("milestone")
        ms_title = milestone["title"] if milestone else "Unassigned"
        labels = [l["name"] for l in item.get("labels", [])]
        issues.append(Issue(
            number=item["number"],
            title=item["title"],
            state=item["state"],
            milestone=ms_title,
            labels=labels,
            url=item["url"],
            body=item.get("body", "") or "",
        ))
    return issues


def fetch_milestones(repo: str) -> list[Milestone]:
    """Fetch milestones from a GitHub repo."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/milestones", "--jq", "."],
        capture_output=True, text=True, check=True,
    )
    raw = json.loads(result.stdout)
    milestones = []
    for item in raw:
        milestones.append(Milestone(
            title=item["title"],
            description=item.get("description", ""),
            open_count=item["open_issues"],
            closed_count=item["closed_issues"],
        ))
    return milestones


def fetch_prs(repo: str) -> list[PullRequest]:
    """Fetch all PRs from a GitHub repo."""
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", "100",
         "--json", "number,title,state,url,headRefName,additions,deletions,changedFiles,body"],
        capture_output=True, text=True, check=True,
    )
    raw = json.loads(result.stdout)
    prs = []
    for item in raw:
        # Extract "closes #N" references from PR body
        body = item.get("body", "") or ""
        closes: list[int] = []
        for match in re.finditer(r"[Cc]loses?\s+#(\d+)", body):
            closes.append(int(match.group(1)))

        prs.append(PullRequest(
            number=item["number"],
            title=item["title"],
            state=item["state"],
            url=item["url"],
            head_branch=item.get("headRefName", ""),
            additions=item.get("additions", 0),
            deletions=item.get("deletions", 0),
            changed_files=item.get("changedFiles", 0),
            closes_issues=closes,
        ))
    return prs


def extract_dependencies(issues: list[Issue]) -> None:
    """Parse issue bodies for #N references to build dependency graph."""
    all_numbers = {i.number for i in issues}
    dep_patterns = [
        r"[Dd]epends?\s+on\s+#(\d+)",
        r"[Bb]locked?\s+by\s+#(\d+)",
        r"[Rr]equires?\s+#(\d+)",
        r"[Aa]fter\s+#(\d+)",
    ]
    related_pattern = r"#(\d+)"

    for issue in issues:
        if not issue.body:
            continue

        # Strong dependency signals
        strong_deps: set[int] = set()
        for pattern in dep_patterns:
            for match in re.finditer(pattern, issue.body):
                num = int(match.group(1))
                if num in all_numbers and num != issue.number:
                    strong_deps.add(num)

        # Weaker: any #N reference in "Related" or "Depends on" sections
        lines = issue.body.split("\n")
        for line in lines:
            lower = line.lower().strip()
            if any(kw in lower for kw in ["depends", "requires", "blocked", "after", "needs"]):
                for match in re.finditer(related_pattern, line):
                    num = int(match.group(1))
                    if num in all_numbers and num != issue.number:
                        strong_deps.add(num)

        issue.depends_on = sorted(strong_deps)

    # Build reverse mapping (blocks)
    dep_map: dict[int, list[int]] = {}
    for issue in issues:
        for dep in issue.depends_on:
            dep_map.setdefault(dep, []).append(issue.number)
    for issue in issues:
        issue.blocks = sorted(dep_map.get(issue.number, []))


def build_markdown(repo: str, issues: list[Issue], milestones: list[Milestone],
                   prs: list[PullRequest] | None = None,
                   filter_milestone: str | None = None) -> str:
    """Build a markmap-compatible Markdown string."""
    repo_name = repo.split("/")[-1]
    repo_url = f"https://github.com/{repo}"

    # Group issues by milestone
    ms_map: dict[str, list[Issue]] = {}
    for issue in issues:
        ms_map.setdefault(issue.milestone, []).append(issue)

    ms_order = {"Alpha": 0, "Beta": 1, "Future": 2, "Unassigned": 99}
    sorted_milestones = sorted(ms_map.keys(), key=lambda m: ms_order.get(m, 50))

    if filter_milestone:
        sorted_milestones = [m for m in sorted_milestones if m == filter_milestone]

    lines = [f"# [{repo_name}]({repo_url})"]

    for ms_name in sorted_milestones:
        ms_issues = ms_map[ms_name]
        closed_count = sum(1 for i in ms_issues if i.state == "CLOSED")
        total = len(ms_issues)

        progress = f"({closed_count}/{total} done)" if total > 0 else ""
        lines.append(f"\n## {ms_name} {progress}")

        label_groups: dict[str, list[Issue]] = {}
        for issue in ms_issues:
            if issue.labels:
                for label in issue.labels:
                    label_groups.setdefault(label, []).append(issue)
            else:
                label_groups.setdefault("unlabeled", []).append(issue)

        seen: set[int] = set()
        label_order = ["security", "docs", "devex", "provider", "matching", "billing",
                        "enhancement", "unlabeled"]
        sorted_labels = sorted(label_groups.keys(),
                                key=lambda l: label_order.index(l) if l in label_order else 50)

        for label in sorted_labels:
            label_issues = [i for i in label_groups[label] if i.number not in seen]
            if not label_issues:
                continue
            for i in label_issues:
                seen.add(i.number)

            lines.append(f"\n### {label}")
            for issue in sorted(label_issues, key=lambda i: i.number):
                icon = "✅" if issue.state == "CLOSED" else "🔴"
                dep_text = ""
                if issue.depends_on:
                    deps = ", ".join(f"#{d}" for d in issue.depends_on)
                    dep_text = f" ← needs {deps}"
                block_text = ""
                if issue.blocks:
                    blocks = ", ".join(f"#{b}" for b in issue.blocks)
                    block_text = f" → unblocks {blocks}"
                suffix = dep_text + block_text
                lines.append(f"- {icon} [#{issue.number} {issue.title}]({issue.url}){suffix}")

    # PRs section
    if prs:
        open_prs = [p for p in prs if p.state == "OPEN"]
        merged_prs = [p for p in prs if p.state == "MERGED"]

        if open_prs or merged_prs:
            lines.append(f"\n## Pull Requests")

            if open_prs:
                lines.append(f"\n### Open ({len(open_prs)})")
                for pr in sorted(open_prs, key=lambda p: p.number):
                    closes_text = ""
                    if pr.closes_issues:
                        closes_text = " → closes " + ", ".join(f"#{n}" for n in pr.closes_issues)
                    lines.append(
                        f"- 🟡 [PR #{pr.number} {pr.title}]({pr.url})"
                        f" (+{pr.additions}/-{pr.deletions}){closes_text}"
                    )

            if merged_prs:
                lines.append(f"\n### Merged ({len(merged_prs)})")
                for pr in sorted(merged_prs, key=lambda p: p.number):
                    closes_text = ""
                    if pr.closes_issues:
                        closes_text = " → closed " + ", ".join(f"#{n}" for n in pr.closes_issues)
                    lines.append(
                        f"- ✅ [PR #{pr.number} {pr.title}]({pr.url}){closes_text}"
                    )

    return "\n".join(lines)


def build_html(markdown: str, repo: str, auto_refresh: int = 0) -> str:
    """Wrap markdown in an HTML page with markmap rendering."""
    refresh_tag = f'<meta http-equiv="refresh" content="{auto_refresh}">' if auto_refresh > 0 else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  {refresh_tag}
  <title>Mind Map — {repo}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #f5f5f5; }}
    #mindmap {{ width: 100vw; height: 100vh; }}
    .markmap-node-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; fill: #1a1a1a; }}
    .markmap-link {{ stroke: #666; }}
    .controls {{
      position: fixed; bottom: 20px; right: 20px; z-index: 1000;
      display: flex; gap: 8px;
    }}
    .controls button {{
      width: 40px; height: 40px; border-radius: 8px; border: 1px solid #ccc;
      background: white; font-size: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .controls button:hover {{ background: #e8e8e8; }}
    .status {{
      position: fixed; top: 10px; right: 20px; z-index: 1000;
      font-family: -apple-system, sans-serif; font-size: 12px; color: #888;
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.17"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.17"></script>
</head>
<body>
  <svg id="mindmap"></svg>
  <div class="controls">
    <button onclick="zoomIn()" title="Zoom in">+</button>
    <button onclick="zoomOut()" title="Zoom out">−</button>
    <button onclick="resetZoom()" title="Fit to screen">⊙</button>
  </div>
  <div class="status">{"Auto-refresh: " + str(auto_refresh) + "s" if auto_refresh > 0 else ""}</div>
  <script>
    const md = {json.dumps(markdown)};
    const {{ Transformer }} = window.markmap;
    const {{ Markmap }} = window.markmap;
    const transformer = new Transformer();
    const {{ root }} = transformer.transform(md);
    const mm = Markmap.create('#mindmap', {{
      colorFreezeLevel: 2,
      maxWidth: 400,
      initialExpandLevel: 3,
      paddingX: 20,
    }}, root);

    function zoomIn() {{ mm.rescale(1.3); }}
    function zoomOut() {{ mm.rescale(0.7); }}
    function resetZoom() {{ mm.fit(); }}
  </script>
</body>
</html>"""


def generate(repo: str, milestone: str | None, output: Path, auto_refresh: int = 0) -> None:
    """Fetch data and generate the mind map HTML."""
    print(f"Fetching issues from {repo}...")
    issues = fetch_issues(repo)
    milestones = fetch_milestones(repo)
    prs = fetch_prs(repo)
    print(f"  {len(issues)} issues, {len(milestones)} milestones, {len(prs)} PRs")

    print("  Extracting dependencies...")
    extract_dependencies(issues)
    dep_count = sum(len(i.depends_on) for i in issues)
    print(f"  {dep_count} dependency links found")

    markdown = build_markdown(repo, issues, milestones, prs, milestone)
    html = build_html(markdown, repo, auto_refresh)
    output.write_text(html, encoding="utf-8")
    print(f"Mind map written to: {output}")


def main():
    parser = argparse.ArgumentParser(description="Generate mind map from GitHub project")
    parser.add_argument("--repo", required=True, help="GitHub repo (owner/name)")
    parser.add_argument("--milestone", default=None, help="Filter to a specific milestone")
    parser.add_argument("--output", default=None, help="Output HTML file path")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh every 60 seconds")
    parser.add_argument("--watch-interval", type=int, default=60, help="Watch interval in seconds")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else Path("mindmap.html")
    refresh = args.watch_interval if args.watch else 0

    generate(args.repo, args.milestone, output_path, auto_refresh=refresh)

    if not args.no_open:
        webbrowser.open(str(output_path.resolve()))

    if args.watch:
        print(f"\nWatching for changes every {args.watch_interval}s (Ctrl+C to stop)...")
        try:
            while True:
                time.sleep(args.watch_interval)
                generate(args.repo, args.milestone, output_path, auto_refresh=refresh)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()

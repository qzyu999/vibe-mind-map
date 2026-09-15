"""vibe-mind-map — Generate interactive mind maps from GitHub project state.

Usage:
    python vibe_mind_map.py --repo qzyu999/inference-exchange
    python vibe_mind_map.py --repo qzyu999/inference-exchange --milestone Alpha
    python vibe_mind_map.py --repo qzyu999/inference-exchange --output map.html
"""

import argparse
import json
import subprocess
import sys
import tempfile
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


@dataclass
class Milestone:
    title: str
    description: str
    open_count: int
    closed_count: int
    issues: list[Issue] = field(default_factory=list)


def fetch_issues(repo: str) -> list[Issue]:
    """Fetch all issues from a GitHub repo using gh CLI."""
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "200",
         "--json", "number,title,state,milestone,labels,url"],
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


def build_markdown(repo: str, issues: list[Issue], milestones: list[Milestone],
                   filter_milestone: str | None = None) -> str:
    """Build a markmap-compatible Markdown string."""
    repo_name = repo.split("/")[-1]

    # Group issues by milestone
    ms_map: dict[str, list[Issue]] = {}
    for issue in issues:
        ms_map.setdefault(issue.milestone, []).append(issue)

    # Sort milestones: Alpha first, then Beta, then Future, then Unassigned
    ms_order = {"Alpha": 0, "Beta": 1, "Future": 2, "Unassigned": 99}
    sorted_milestones = sorted(ms_map.keys(), key=lambda m: ms_order.get(m, 50))

    if filter_milestone:
        sorted_milestones = [m for m in sorted_milestones if m == filter_milestone]

    lines = [f"# {repo_name}"]

    for ms_name in sorted_milestones:
        ms_issues = ms_map[ms_name]
        open_count = sum(1 for i in ms_issues if i.state == "OPEN")
        closed_count = sum(1 for i in ms_issues if i.state == "CLOSED")
        total = len(ms_issues)

        # Milestone header with progress
        progress = f"({closed_count}/{total} done)" if total > 0 else ""
        lines.append(f"\n## {ms_name} {progress}")

        # Group by label within milestone
        label_groups: dict[str, list[Issue]] = {}
        for issue in ms_issues:
            if issue.labels:
                for label in issue.labels:
                    label_groups.setdefault(label, []).append(issue)
            else:
                label_groups.setdefault("unlabeled", []).append(issue)

        # Deduplicate: if an issue appears under multiple labels, pick the first
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
                lines.append(f"- {icon} #{issue.number} {issue.title}")

    return "\n".join(lines)


def build_html(markdown: str, repo: str) -> str:
    """Wrap markdown in an HTML page with markmap rendering."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Mind Map — {repo}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #1a1a2e; }}
    #mindmap {{ width: 100vw; height: 100vh; }}
    .markmap-node-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@latest"></script>
</head>
<body>
  <div class="markmap">
    <script type="text/template">
---
markmap:
  colorFreezeLevel: 2
  maxWidth: 400
  initialExpandLevel: 3
---

{markdown}
    </script>
  </div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate mind map from GitHub project")
    parser.add_argument("--repo", required=True, help="GitHub repo (owner/name)")
    parser.add_argument("--milestone", default=None, help="Filter to a specific milestone")
    parser.add_argument("--output", default=None, help="Output HTML file path")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    args = parser.parse_args()

    print(f"Fetching issues from {args.repo}...")
    issues = fetch_issues(args.repo)
    milestones = fetch_milestones(args.repo)
    print(f"  {len(issues)} issues, {len(milestones)} milestones")

    markdown = build_markdown(args.repo, issues, milestones, args.milestone)
    html = build_html(markdown, args.repo)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(tempfile.mktemp(suffix=".html", prefix="mindmap_"))

    output_path.write_text(html, encoding="utf-8")
    print(f"Mind map written to: {output_path}")

    if not args.no_open:
        webbrowser.open(str(output_path))


if __name__ == "__main__":
    main()

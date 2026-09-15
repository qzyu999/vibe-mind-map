# vibe-mind-map

Generate interactive mind maps from GitHub project state. Pulls issues, milestones, and labels from any GitHub repo and renders an interactive, zoomable mind map in the browser.

## Usage

```bash
# Full project map
python vibe_mind_map.py --repo qzyu999/inference-exchange

# Filter to Alpha milestone only
python vibe_mind_map.py --repo qzyu999/inference-exchange --milestone Alpha

# Save to a specific file
python vibe_mind_map.py --repo qzyu999/inference-exchange --output alpha-map.html
```

## Requirements

- Python 3.11+
- `gh` CLI installed and authenticated
- Internet connection (loads markmap from CDN)

## How it works

1. Fetches all issues + milestones from the GitHub API via `gh` CLI
2. Groups by milestone → label → issue
3. Generates markmap-compatible Markdown
4. Wraps in an HTML page with the markmap autoloader
5. Opens in your default browser

Issues are marked ✅ (closed) or 🔴 (open). Milestones show progress counts.

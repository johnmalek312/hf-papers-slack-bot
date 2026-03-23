import os
import sys
import json
from datetime import datetime
from urllib.request import urlopen, Request

import requests

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_IDS = os.environ["SLACK_USER_IDS"].split(",")
HF_API_URL = "https://huggingface.co/api/daily_papers"
MAX_PAPERS = 3


def fetch_papers():
    """Fetch top papers from HF Daily Papers API, sorted by upvotes."""
    req = Request(HF_API_URL, headers={"Accept": "application/json"})
    with urlopen(req) as resp:
        data = json.loads(resp.read())

    if not data:
        print("No papers found.")
        return []

    # Sort by upvotes descending, take top N
    data.sort(key=lambda x: x.get("paper", {}).get("upvotes", 0), reverse=True)

    papers = []
    for entry in data[:MAX_PAPERS]:
        p = entry.get("paper", {})
        arxiv_id = p.get("id", "")
        authors = [a["name"] for a in p.get("authors", []) if not a.get("hidden")]

        papers.append({
            "title": entry.get("title", "Untitled"),
            "summary": entry.get("summary", "No summary available."),
            "authors": authors,
            "upvotes": p.get("upvotes", 0),
            "arxiv_id": arxiv_id,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None,
            "hf_url": f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else None,
            "github_url": p.get("githubRepo"),
            "thumbnail": entry.get("thumbnail"),
            "published": entry.get("publishedAt", ""),
        })

    return papers


def format_authors(authors, max_shown=3):
    """Format author list, truncating if needed."""
    if not authors:
        return "Unknown"
    if len(authors) <= max_shown:
        return ", ".join(authors)
    return ", ".join(authors[:max_shown]) + f" +{len(authors) - max_shown} more"


def format_date(date_str):
    """Parse ISO date to readable format."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except ValueError:
        return date_str


def build_paper_blocks(paper, index):
    """Build Slack Block Kit blocks for a single paper."""
    authors_str = format_authors(paper["authors"])
    date_str = format_date(paper["published"])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 Paper #{index}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{paper['title']}*",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"👤 {authors_str}"},
                {"type": "mrkdwn", "text": f"📅 {date_str}"},
                {"type": "mrkdwn", "text": f"👍 {paper['upvotes']} upvotes"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": paper["summary"][:3000],
            },
        },
    ]

    # Link buttons
    buttons = []
    if paper["hf_url"]:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "HF Paper"},
            "url": paper["hf_url"],
        })
    if paper["arxiv_url"]:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "arXiv"},
            "url": paper["arxiv_url"],
        })
    if paper["pdf_url"]:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "PDF"},
            "url": paper["pdf_url"],
        })
    if paper["github_url"]:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "GitHub"},
            "url": paper["github_url"],
        })

    if buttons:
        blocks.append({"type": "actions", "elements": buttons})

    return blocks


def send_slack_dm(user_id, blocks, fallback_text):
    """Send a DM to a Slack user."""
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={
            "channel": user_id,
            "text": fallback_text,
            "blocks": blocks,
            "unfurl_links": False,
            "unfurl_media": False,
        },
    )

    data = resp.json()
    if not data.get("ok"):
        print(f"ERROR: Slack API error for {user_id}: {data.get('error')}")
        sys.exit(1)


def main():
    print("Fetching papers...")
    papers = fetch_papers()

    if not papers:
        print("No papers today. Skipping.")
        return

    print(f"Found {len(papers)} papers. Sending to {len(SLACK_USER_IDS)} users...")

    for user_id in SLACK_USER_IDS:
        user_id = user_id.strip()
        for i, paper in enumerate(papers, 1):
            blocks = build_paper_blocks(paper, i)
            send_slack_dm(user_id, blocks, paper["title"])
        print(f"Sent {len(papers)} papers to {user_id}")


if __name__ == "__main__":
    main()

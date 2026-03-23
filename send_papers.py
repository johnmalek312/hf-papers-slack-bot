import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen

import requests

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_ID = os.environ["SLACK_USER_ID"]
RSS_FEED_URL = "https://papers.takara.ai/api/feed"
MAX_PAPERS = 3


def fetch_papers():
    """Fetch latest papers from HF Daily Papers RSS feed."""
    with urlopen(RSS_FEED_URL) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    items = root.findall(".//item")

    if not items:
        print("No entries found in feed.")
        return []

    papers = []
    for item in items[:MAX_PAPERS]:
        title = item.findtext("title", "Untitled")
        link = item.findtext("link", "#")
        description = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "")

        # Extract arxiv ID from link (e.g. https://tldr.takara.ai/p/2603.17531)
        arxiv_id = link.rstrip("/").split("/")[-1] if "/p/" in link else None
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None

        # Parse date
        date_str = ""
        if pub_date:
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                date_str = dt.strftime("%B %d, %Y")
            except ValueError:
                date_str = pub_date

        if len(description) > 1000:
            description = description[:997] + "..."

        papers.append({
            "title": title,
            "link": link,
            "description": description,
            "date": date_str,
            "arxiv_url": arxiv_url,
            "pdf_url": pdf_url,
        })

    return papers


def build_paper_blocks(paper, index):
    """Build Slack Block Kit blocks for a single paper message."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 Paper #{index}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{paper['link']}|{paper['title']}>*",
            },
        },
    ]

    # Date
    if paper["date"]:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"📅 {paper['date']}"},
            ],
        })

    # Abstract
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": paper["description"],
        },
    })

    # Links
    links = [f"<{paper['link']}|TLDR>"]
    if paper["arxiv_url"]:
        links.append(f"<{paper['arxiv_url']}|arXiv>")
    if paper["pdf_url"]:
        links.append(f"<{paper['pdf_url']}|PDF>")

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "TLDR"},
                "url": paper["link"],
            },
            *(
                [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "arXiv"},
                    "url": paper["arxiv_url"],
                }] if paper["arxiv_url"] else []
            ),
            *(
                [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "PDF"},
                    "url": paper["pdf_url"],
                }] if paper["pdf_url"] else []
            ),
        ],
    })

    return blocks


def send_slack_dm(blocks, fallback_text):
    """Send a DM to the configured Slack user."""
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={
            "channel": SLACK_USER_ID,
            "text": fallback_text,
            "blocks": blocks,
            "unfurl_links": False,
            "unfurl_media": False,
        },
    )

    data = resp.json()
    if not data.get("ok"):
        print(f"ERROR: Slack API error: {data.get('error')}")
        sys.exit(1)

    print(f"Message sent successfully to {SLACK_USER_ID}")


def main():
    print("Fetching papers...")
    papers = fetch_papers()

    if not papers:
        print("No papers today. Skipping.")
        return

    print(f"Found {len(papers)} papers. Sending to Slack...")

    for i, paper in enumerate(papers, 1):
        blocks = build_paper_blocks(paper, i)
        send_slack_dm(blocks, paper["title"])
        print(f"Sent paper {i}/{len(papers)}: {paper['title']}")


if __name__ == "__main__":
    main()

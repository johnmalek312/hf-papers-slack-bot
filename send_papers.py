import os
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
        if len(title) > 120:
            title = title[:117] + "..."
        if len(description) > 1000:
            description = description[:997] + "..."
        papers.append({"title": title, "link": link, "description": description})

    return papers


def build_blocks(papers):
    """Build Slack Block Kit blocks for the message."""
    today = datetime.now(timezone.utc).strftime("%A, %B %d %Y")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 HF Daily Papers — {today}"},
        },
        {"type": "divider"},
    ]

    for i, p in enumerate(papers, 1):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{i}. <{p['link']}|{p['title']}>*\n{p['description']}",
                },
            }
        )
        if i < len(papers):
            blocks.append({"type": "divider"})

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Source: <https://huggingface.co/papers|HF Daily Papers>",
                }
            ],
        }
    )

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
    blocks = build_blocks(papers)
    fallback = ", ".join(p["title"] for p in papers)
    send_slack_dm(blocks, fallback)


if __name__ == "__main__":
    main()

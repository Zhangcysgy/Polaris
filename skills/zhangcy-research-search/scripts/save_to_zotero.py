#!/usr/bin/env python
"""
save_to_zotero.py — Zotero MCP fallback script.

当 Zotero MCP 不可用时，通过 pyzotero 将论文添加到 Zotero 库。

Usage:
    uv run --with pyzotero python save_to_zotero.py \\
        --doi "10.1175/JCLI-D-23-0123.1" \\
        --title "Machine Learning for Precipitation Nowcasting" \\
        --authors "Zhang C, Li Y" \\
        --journal "Journal of Climate" \\
        --year 2024 \\
        --collection "precipitation-nowcasting"

Environment:
    ZOTERO_LIBRARY_ID - Zotero user ID (from zotero.org/settings/keys)
    ZOTERO_API_KEY    - Zotero API key
    ZOTERO_LIBRARY_TYPE - "user" (default) or "group"
"""

import argparse
import os
import sys

try:
    from pyzotero import zotero
except ImportError:
    print("ERROR: pyzotero not installed. Run: uv pip install pyzotero")
    sys.exit(1)


def get_zotero():
    """Get Zotero client from environment variables."""
    library_id = os.getenv("ZOTERO_LIBRARY_ID")
    api_key = os.getenv("ZOTERO_API_KEY")
    library_type = os.getenv("ZOTERO_LIBRARY_TYPE", "user")

    if not library_id or not api_key:
        print("ERROR: ZOTERO_LIBRARY_ID and ZOTERO_API_KEY must be set.")
        print("Get them at: https://www.zotero.org/settings/keys")
        sys.exit(1)

    return zotero.Zotero(library_id, library_type, api_key)


def check_exists(zot, doi=None, title=None):
    """Check if an item already exists in Zotero library."""
    if doi:
        items = zot.items(q=doi, limit=5)
        for item in items:
            if item.get("data", {}).get("DOI", "").lower() == doi.lower():
                return item
    if title:
        items = zot.items(q=title, limit=5)
        for item in items:
            data = item.get("data", {})
            if title.lower() in data.get("title", "").lower():
                return item
    return None


def add_item(zot, doi=None, title=None, authors=None, journal=None,
             year=None, volume=None, issue=None, pages=None,
             abstract=None, url=None, arxiv_id=None,
             collection=None):
    """Add an item to Zotero."""
    # Check for duplicates first
    existing = check_exists(zot, doi=doi, title=title)
    if existing:
        key = existing.get("data", {}).get("key", "?")
        print(f"⏭ Already exists (key: {key})")
        return existing["data"]["key"]

    # Build item template
    creators = []
    if authors:
        for author in authors.split(","):
            author = author.strip()
            parts = author.split()
            if len(parts) >= 2:
                creators.append({
                    "creatorType": "author",
                    "lastName": parts[0],
                    "firstName": " ".join(parts[1:]),
                })
            else:
                creators.append({
                    "creatorType": "author",
                    "lastName": parts[0],
                    "firstName": "",
                })

    extra = ""
    if arxiv_id:
        extra = f"arXiv: {arxiv_id}"

    item_type = "preprint" if arxiv_id else "journalArticle"

    template = {
        "itemType": item_type,
        "title": title or "",
        "creators": creators,
        "DOI": doi or "",
        "publicationTitle": journal or "",
        "date": str(year) if year else "",
        "volume": volume or "",
        "issue": issue or "",
        "pages": pages or "",
        "abstractNote": abstract or "",
        "url": url or "",
        "extra": extra,
    }

    # Create item
    response = zot.create_items([template])
    if response and "successful" in response:
        keys = list(response["successful"].keys())
        print(f"✅ Created item: {keys[0]}")

        # Add to collection if specified
        if collection:
            collections = zot.collections()
            target = None
            for col in collections:
                if col.get("data", {}).get("name", "").lower() == collection.lower():
                    target = col
                    break
            if target:
                zot.addto_collection(target["data"]["key"], keys[0])
                print(f"  → Added to collection: {collection}")
            else:
                # Create collection if not exists
                new_col = zot.create_collection(collection)
                zot.addto_collection(new_col["data"]["key"], keys[0])
                print(f"  → Created & added to collection: {collection}")

        return keys[0]
    else:
        print(f"❌ Failed to create item: {response}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Save paper to Zotero")
    parser.add_argument("--doi", help="DOI of the paper")
    parser.add_argument("--title", help="Paper title")
    parser.add_argument("--authors", help="Authors (e.g. 'Zhang C, Li Y')")
    parser.add_argument("--journal", help="Journal name")
    parser.add_argument("--year", type=int, help="Publication year")
    parser.add_argument("--volume", help="Volume")
    parser.add_argument("--issue", help="Issue")
    parser.add_argument("--pages", help="Pages")
    parser.add_argument("--abstract", help="Abstract")
    parser.add_argument("--url", help="URL")
    parser.add_argument("--arxiv-id", help="arXiv ID")
    parser.add_argument("--collection", help="Zotero collection name")
    args = parser.parse_args()

    zot = get_zotero()
    add_item(zot,
        doi=args.doi,
        title=args.title,
        authors=args.authors,
        journal=args.journal,
        year=args.year,
        volume=args.volume,
        issue=args.issue,
        pages=args.pages,
        abstract=args.abstract,
        url=args.url,
        arxiv_id=args.arxiv_id,
        collection=args.collection,
    )


if __name__ == "__main__":
    main()

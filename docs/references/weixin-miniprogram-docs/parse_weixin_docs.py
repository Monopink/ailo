#!/usr/bin/env python3
"""
Parse WeChat MiniProgram documentation HTML files and generate JSON index.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


def extract_navigation_with_hierarchy(html_content: str) -> List[Dict[str, Any]]:
    """Extract page-level navigation, grouping by base URL."""
    # Find the TreeNavigation section
    tree_nav_match = re.search(
        r'<div class="TreeNavigation">(.*?)</div>\s*</aside>', html_content, re.DOTALL
    )
    if not tree_nav_match:
        return []

    tree_content = tree_nav_match.group(1)

    # Extract all navigation links
    link_pattern = (
        r'<a\s+href="([^"]+)"\s+class="NavigationItem__router-link"[^>]*>\s*([^<]+?)\s*<!----></a>'
    )

    # Group by base URL (without anchor)
    url_groups = defaultdict(lambda: {"main_title": "", "subtitles": []})

    for match in re.finditer(link_pattern, tree_content, re.DOTALL):
        url = match.group(1).strip()
        title = match.group(2).strip()

        if url and title:
            base_url = url.split("#")[0]

            # If URL has no anchor, it's the main title
            if "#" not in url:
                url_groups[base_url]["main_title"] = title
            else:
                # Has anchor, it's a subtitle
                url_groups[base_url]["subtitles"].append(title)

    # Create navigation items
    navigation = []
    for base_url, data in url_groups.items():
        # Remove duplicate subtitles while preserving order
        unique_subtitles = []
        seen = set()
        for subtitle in data["subtitles"]:
            if subtitle not in seen:
                unique_subtitles.append(subtitle)
                seen.add(subtitle)

        nav_item = {"title": data["main_title"], "url": base_url}

        # Add subtitles if they exist
        if unique_subtitles:
            nav_item["subtitles"] = unique_subtitles

        navigation.append(nav_item)

    return navigation


def parse_html_file(file_path: Path) -> Dict[str, Any]:
    """Parse a single HTML file and extract navigation."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract title from HTML
    title_match = re.search(r"<title>([^<]+)</title>", content)
    title = title_match.group(1) if title_match else file_path.stem

    # Extract navigation
    navigation = extract_navigation_with_hierarchy(content)

    return {"title": title, "pages": navigation}


def map_file_to_url(filename: str) -> str:
    """Map filename to original documentation URL."""
    url_mapping = {
        "微信开放文档---框架.htm": "https://developers.weixin.qq.com/miniprogram/dev/framework/",
        "微信开放文档---组件.htm": "https://developers.weixin.qq.com/miniprogram/dev/component/",
        "微信开放文档---API.htm": "https://developers.weixin.qq.com/miniprogram/dev/api/",
        "微信开放文档---开发.htm": "https://developers.weixin.qq.com/miniprogram/dev/devtools/devtools.html",
        "微信开放文档---服务端.htm": "https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/",
        "产品简介---多端框架概述.htm": "https://developers.weixin.qq.com/miniprogram/dev/platform-capabilities/miniapp/intro/intro.html",
        "介绍.htm": "https://developers.weixin.qq.com/miniprogram/introduction/",
        "概览.htm": "https://developers.weixin.qq.com/miniprogram/dev/reference/",
    }
    return url_mapping.get(filename, "")


def main():
    """Main function to parse all HTML files and generate separate JSON files."""
    docs_dir = Path("references/weixin-miniprogram-docs")

    if not docs_dir.exists():
        print(f"Error: Directory {docs_dir} does not exist")
        return

    html_files = sorted(docs_dir.glob("*.htm"))
    total_items = 0

    for html_file in html_files:
        print(f"Parsing {html_file.name}...")
        try:
            doc_data = parse_html_file(html_file)
            doc_data["source_url"] = map_file_to_url(html_file.name)

            # Generate JSON filename from HTML filename
            json_filename = html_file.stem + ".json"
            json_path = docs_dir / json_filename

            # Write individual JSON file
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(doc_data, f, ensure_ascii=False, indent=2)

            item_count = len(doc_data["items"])
            total_items += item_count
            print(f"  Generated {json_filename} with {item_count} items")

        except Exception as e:
            print(f"  Error parsing {html_file.name}: {e}")

    print(f"\nTotal JSON files generated: {len(html_files)}")
    print(f"Total navigation items: {total_items}")


if __name__ == "__main__":
    main()

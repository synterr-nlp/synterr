#!/usr/bin/env python3
"""Extract clean sentences from a Russian Wikipedia XML dump.

Streams bz2-compressed dump, extracts article text via mwparserfromhell,
splits into sentences with razdel, filters for quality.

Usage:
    uv run python scripts/extract_wiki_sents.py \
        ~/Projects/gector/ruwiki-latest-pages-articles.xml.bz2 \
        -o data/wiki_sents_200k.txt -n 200000
"""

import argparse
import bz2
import re
import xml.etree.ElementTree as ET

import mwparserfromhell
from razdel import sentenize


def clean_wikitext(raw: str) -> str:
    """Strip wikimarkup to plain text."""
    wikicode = mwparserfromhell.parse(raw)
    text = wikicode.strip_code()
    # Remove residual markup
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_good_sentence(s: str) -> bool:
    """Filter for clean, full Russian sentences."""
    if len(s) < 30 or len(s) > 500:
        return False
    # Must start with uppercase Cyrillic
    if not re.match(r'^[А-ЯЁ«"]', s):
        return False
    # Must end with sentence-final punctuation
    if not re.search(r'[.!?»"]$', s):
        return False
    # Reject if too many non-Cyrillic chars (tables, formulas)
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic / max(len(s), 1) < 0.5:
        return False
    # Reject list items, headers, refs
    if re.match(r'^[\d*#•—\-]', s):
        return False
    if '|' in s or '=' in s:
        return False
    # Reject empty template outputs: "составляет человек", "( )"
    if re.search(r'\(\s*\)', s) or re.search(r'\(\s*,', s):
        return False
    # Reject sentences with dangling "составляет" + no number
    if 'составляет ' in s and not re.search(r'составляет\s+[\d,.]', s):
        return False
    # Reject if contains leftover wiki/template artifacts
    if '{{' in s or '}}' in s or '[[' in s or ']]' in s:
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", help="Path to ruwiki XML dump (.xml.bz2)")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-n", "--max-sents", type=int, default=200000)
    parser.add_argument("--skip-articles", type=int, default=0)
    args = parser.parse_args()

    count = 0
    articles = 0
    ns_tag = '{http://www.mediawiki.org/xml/export-0.11/}'

    with bz2.open(args.dump, 'rt', encoding='utf-8') as f_in, \
         open(args.output, 'w', encoding='utf-8') as f_out:

        # Stream parse to avoid loading 5GB into memory
        for event, elem in ET.iterparse(f_in, events=('end',)):
            if not elem.tag.endswith('}page') and elem.tag != 'page':
                continue

            # Find <text> inside <revision>
            text_elem = elem.find(f'.//{ns_tag}text')
            if text_elem is None:
                text_elem = elem.find('.//text')
            if text_elem is None or not text_elem.text:
                elem.clear()
                continue

            # Skip redirects
            raw = text_elem.text
            if raw.strip().upper().startswith('#REDIRECT') or raw.strip().upper().startswith('#ПЕРЕНАПРАВЛЕНИЕ'):
                elem.clear()
                continue

            articles += 1
            if articles <= args.skip_articles:
                elem.clear()
                continue

            if articles % 10000 == 0:
                print(f"  articles: {articles}, sentences: {count}", flush=True)

            text = clean_wikitext(raw)
            # Strip combining acute accent (stress marks)
            text = text.replace('\u0301', '')
            for sent in sentenize(text):
                s = sent.text.strip()
                if is_good_sentence(s):
                    f_out.write(s + '\n')
                    count += 1
                    if count >= args.max_sents:
                        break

            elem.clear()

            if count >= args.max_sents:
                break

    print(f"Done: {count} sentences from {articles} articles → {args.output}")


if __name__ == '__main__':
    main()

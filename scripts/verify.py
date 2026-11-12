#!/usr/bin/env python3
"""Check complete message coverage, source downloads, links and search anchors."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.messages = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError('Duplicate HTML ID: ' + attrs['id'])
            self.ids.add(attrs['id'])
        if attrs.get('class') == 'message':
            self.messages += 1
        for key in ['href', 'src']:
            if attrs.get(key):
                self.links.append(attrs[key])


def verify(root=ROOT):
    site = (root / 'site').resolve()
    report = json.loads((root / 'build/report.json').read_text())
    cross = set()
    ids = {}
    messages = 0
    checked = 0
    pages = 0
    for file in site.rglob('*.html'):
        file = file.resolve()
        parser = Links()
        parser.feed(file.read_text())
        ids[file] = parser.ids
        messages += parser.messages
        pages += 1
        if pages % 1000 == 0:
            print(f'Verified {pages} HTML pages; {messages:,} messages', flush=True)
        for link in parser.links:
            if link.startswith('#'):
                checked += 1
                if unquote(link[1:]) not in parser.ids:
                    raise ValueError(f'{file}: broken fragment: {link}')
                continue
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            checked += 1
            if url.path.startswith('/'):
                raise ValueError(f'{file}: root-absolute URL would break project Pages: {link}')
            target = (file.parent / unquote(url.path)).resolve() if url.path else file
            if target.is_dir():
                target /= 'index.html'
            if not target.is_relative_to(site) or not target.is_file():
                raise ValueError(f'{file}: broken link: {link}')
            if url.fragment:
                fragment = unquote(url.fragment)
                if target == file:
                    if fragment not in parser.ids:
                        raise ValueError(f'{file}: broken fragment: {link}')
                else:
                    cross.add((target, fragment))
    for target, fragment in cross:
        if fragment not in ids.get(target, set()):
            raise ValueError(f'Broken target: {target}#{fragment}')
    indexed = 0
    with (root / 'build/search-records.jsonl').open() as stream:
        for line in stream:
            record = json.loads(line)
            path, fragment = record['url'].split('#', 1)
            target = (site / path.lstrip('/')).resolve()
            if fragment not in ids.get(target, set()):
                raise ValueError('Search result has no target: ' + record['url'])
            indexed += 1
    csvs = sorted((root / 'logs').rglob('*.csv'))
    for source in csvs:
        target = site / 'csv' / source.relative_to(root / 'logs')
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError('Changed CSV download: ' + str(target))
    if messages != report['messages'] or indexed != report['search_records'] or len(csvs) != report['csv_files']:
        raise ValueError('Rendered message, source or search-record counts differ')
    for bundle in ['pagefind-entry.json', 'pagefind-ui.js', 'pagefind-ui.css', 'pagefind.js']:
        if not (site / 'pagefind' / bundle).is_file():
            raise ValueError('Missing search bundle: ' + bundle)
    result = {'complete': True, 'rendered_messages': messages, 'csv_files_verified': len(csvs),
              'search_targets_verified': indexed, 'html_pages_checked': pages, 'internal_links_checked': checked}
    (root / 'build/verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    verify()

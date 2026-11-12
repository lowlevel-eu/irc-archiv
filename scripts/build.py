#!/usr/bin/env python3
"""Render recovered IRC CSVs without changing their contents or message order."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from functools import lru_cache
import hashlib
from html import escape
import json
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {'lost': '#lost', 'tyndur': '#tyndur'}
MONTHS = ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
HEADER = ['date/time', 'nick', 'message']
URL = re.compile(r'https?://[^\s<>"\x00-\x1f]+')


def href(current, target):
    path, sep, fragment = target.partition('#')
    result = posixpath.relpath(path, posixpath.dirname(current) or '.')
    return quote(result, safe='/') + (sep + quote(fragment) if sep else '')


def anchor(current, target, label):
    return f'<a href="{escape(href(current, target), quote=True)}">{escape(str(label))}</a>'


def linkify(text):
    chunks, start = [], 0
    for match in URL.finditer(text):
        url = match[0].rstrip('.,;:!?)')
        try:
            if not urlsplit(url).hostname:
                continue
        except ValueError:
            # Preserve malformed historical URLs as text instead of broken links.
            continue
        end = match.start() + len(url)
        chunks += [escape(text[start:match.start()]), f'<a rel="noreferrer" href="{escape(url, quote=True)}">{escape(url)}</a>']
        start = end
    return ''.join(chunks) + escape(text[start:])


@lru_cache(maxsize=10000)
def nick_class(nick):
    return 'nick-' + str(int.from_bytes(hashlib.sha256(nick.encode()).digest()[:2], 'big') % 6)


def read_day(file, day):
    csv.field_size_limit(16 * 1024 * 1024)
    rows = []
    previous = ''
    with file.open(encoding='utf-8', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != HEADER:
            raise ValueError(f'{file}: expected CSV header {HEADER}')
        for number, row in enumerate(reader, 2):
            if len(row) != 3:
                raise ValueError(f'{file}: record {number} does not have three columns')
            stamp, nick, message = row
            if not re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', stamp):
                raise ValueError(f'{file}: invalid timestamp {stamp!r}')
            datetime.fromisoformat(stamp)
            if stamp[:10] != day or stamp < previous:
                raise ValueError(f'{file}: wrong date or nonchronological message at record {number}')
            previous = stamp
            rows.append((stamp, nick, message))
    if not rows:
        raise ValueError(f'{file}: no messages')
    return rows


def page_name(channel, day, part=0):
    return f'{channel}/{day[:4]}/{day[5:7]}/{day}/' + ('index.html' if part == 0 else f'page-{part+1:03}.html')


def render_page(site, path, title, body, crumbs=(), search=False):
    nav = [anchor(path, 'index.html', 'IRC-Archiv'), anchor(path, 'search/index.html', 'Suche')]
    nav += [anchor(path, target, label) for target, label in crumbs]
    extra = ''
    if search:
        extra = f'<link rel="stylesheet" href="{href(path, "pagefind/pagefind-ui.css")}"><script src="{href(path, "pagefind/pagefind-ui.js")}" defer></script><script src="{href(path, "static/search.js")}" defer></script>'
    html = f'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · Lowlevel IRC-Archiv</title><link rel="stylesheet" href="{href(path, 'static/style.css')}">{extra}</head>
<body><header><nav aria-label="Navigation">{' <span aria-hidden="true">/</span> '.join(nav)}</nav></header>
<main><h1>{escape(title)}</h1>{body}</main>
<footer>Historische öffentliche IRC-Nachrichten.
<a href="https://github.com/lowlevel-eu/wiki/discussions">Heute diskutieren</a> · <a href="https://lowlevel-eu.github.io/">Forum und Wiki im Archiv</a></footer></body></html>
'''
    file = site / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(html, encoding='utf-8')


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + escape(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + value + '</td>' for value in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def build(source, site, work, page_size=200, chunk_size=50):
    source, site, work = source.resolve(), site.resolve(), work.resolve()
    if page_size < 1 or chunk_size < 1 or page_size % chunk_size:
        raise ValueError('Page size must be a positive multiple of search chunk size')
    if source.is_relative_to(site) or site.is_relative_to(source) or site == ROOT or work == site:
        raise ValueError('Input, output and build directories must be separate')
    if site.exists():
        if not (site / '.irc-archive-generated').is_file():
            raise ValueError('Refusing to replace an output directory without the build marker')
        shutil.rmtree(site)
    site.mkdir(parents=True)
    work.mkdir(parents=True, exist_ok=True)
    (site / '.irc-archive-generated').touch()
    (site / '.nojekyll').touch()
    shutil.copytree(ROOT / 'static', site / 'static')
    days = defaultdict(list)
    for file in sorted(source.rglob('*.csv')):
        relative = file.relative_to(source)
        if len(relative.parts) != 4:
            raise ValueError('Unexpected CSV path: ' + str(relative))
        channel, year, month, name = relative.parts
        day = name.removesuffix('.csv')
        if not re.fullmatch(r'[a-z0-9-]+', channel) or not re.fullmatch(r'\d{4}-\d\d-\d\d', day) or day[:4] != year or day[5:7] != month:
            raise ValueError('Unexpected CSV path: ' + str(relative))
        days[channel].append((day, file))
    if not days:
        raise ValueError('No CSVs found')
    report = {'messages': 0, 'csv_files': 0, 'search_records': 0, 'log_pages': 0, 'channels': {}}
    summary = defaultdict(list)
    records_path = work / 'search-records.jsonl'
    with records_path.open('w', encoding='utf-8') as records:
        for channel, entries in sorted(days.items()):
            channel_name = CHANNELS.get(channel, '#' + channel)
            count = 0
            for index, (day, file) in enumerate(entries):
                rows = read_day(file, day)
                count += len(rows)
                summary[channel].append((day, len(rows)))
                report['messages'] += len(rows)
                report['csv_files'] += 1
                csv_target = site / 'csv' / file.relative_to(source)
                csv_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, csv_target)
                parts = (len(rows) + page_size - 1) // page_size
                for part in range(parts):
                    path = page_name(channel, day, part)
                    start = part * page_size
                    batch = rows[start:start+page_size]
                    crumbs = [(f'{channel}/index.html', channel_name), (f'{channel}/{day[:4]}/index.html', day[:4]), (f'{channel}/{day[:4]}/{day[5:7]}/index.html', MONTHS[int(day[5:7])])]
                    controls = []
                    if part:
                        controls.append(anchor(path, page_name(channel, day, part-1), '← Vorherige Seite'))
                    if part + 1 < parts:
                        controls.append(anchor(path, page_name(channel, day, part+1), 'Nächste Seite →'))
                    day_links = []
                    if index:
                        day_links.append(anchor(path, page_name(channel, entries[index-1][0]), '← Vorheriger Tag mit Nachrichten'))
                    if index + 1 < len(entries):
                        day_links.append(anchor(path, page_name(channel, entries[index+1][0]), 'Nächster Tag mit Nachrichten →'))
                    info = f'<p>{len(rows):,} Nachrichten · Seite {part+1} von {parts} · ' + anchor(path, 'csv/' + file.relative_to(source).as_posix(), 'Original-CSV herunterladen') + '</p>'
                    pager = '<nav class="pager" aria-label="Blättern">' + ' · '.join(controls) + '</nav>'
                    messages = []
                    for offset, (stamp, nick, message) in enumerate(batch, start+1):
                        ident = f'm{offset:06}'
                        messages.append(f'<li id="{ident}" class="message"><a class="time" href="#{ident}" aria-label="Nachricht {offset}, {stamp[11:]}"><time datetime="{stamp.replace(" ", "T")}">{stamp[11:]}</time></a><span class="nick {nick_class(nick)}">{escape(nick)}</span><span class="text">{linkify(message)}</span></li>')
                    body = info + '<nav class="pager" aria-label="Tage">' + ' · '.join(day_links) + '</nav>' + pager + '<ol class="messages" start="' + str(start+1) + '">' + '\n'.join(messages) + '</ol>' + pager
                    render_page(site, path, channel_name + ' · ' + day, body, crumbs)
                    report['log_pages'] += 1
                    for group_start in range(0, len(batch), chunk_size):
                        group = batch[group_start:group_start+chunk_size]
                        message_id = start + group_start + 1
                        record = {'url': '/' + path + f'#m{message_id:06}', 'language': 'de',
                                  'content': '\n'.join(f'{stamp[11:]} <{nick}> {message}' for stamp, nick, message in group),
                                  'meta': {'title': f'{channel_name} · {day} · {group[0][0][11:]}–{group[-1][0][11:]}'},
                                  'filters': {'Kanal': [channel_name], 'Jahr': [day[:4]]}}
                        records.write(json.dumps(record, ensure_ascii=False) + '\n')
                        report['search_records'] += 1
                if report['csv_files'] % 500 == 0:
                    print(f'Rendered {report["csv_files"]} CSVs, {report["messages"]:,} messages', flush=True)
            report['channels'][channel] = {'name': channel_name, 'messages': count, 'days': len(entries), 'first': entries[0][0], 'last': entries[-1][0]}
    for channel, entries in summary.items():
        name = CHANNELS.get(channel, '#' + channel)
        years = defaultdict(list)
        months = defaultdict(list)
        for day, count in entries:
            years[day[:4]].append((day, count))
            months[day[:7]].append((day, count))
        for month, items in months.items():
            path = f'{channel}/{month[:4]}/{month[5:]}/index.html'
            rows = [(anchor(path, page_name(channel, day), day), f'{count:,}') for day, count in items]
            render_page(site, path, f'{name} · {MONTHS[int(month[5:])]} {month[:4]}', table(['Tag', 'Nachrichten'], rows), [(f'{channel}/index.html', name), (f'{channel}/{month[:4]}/index.html', month[:4])])
        for year, items in years.items():
            path = f'{channel}/{year}/index.html'
            rows = [(anchor(path, f'{channel}/{month[:4]}/{month[5:]}/index.html', MONTHS[int(month[5:])]), str(len(months[month])), f'{sum(c for _, c in months[month]):,}') for month in sorted(months) if month.startswith(year)]
            render_page(site, path, name + ' · ' + year, table(['Monat', 'Tage', 'Nachrichten'], rows), [(f'{channel}/index.html', name)])
        path = f'{channel}/index.html'
        rows = [(anchor(path, f'{channel}/{year}/index.html', year), str(len(items)), f'{sum(c for _, c in items):,}') for year, items in sorted(years.items())]
        render_page(site, path, name, table(['Jahr', 'Tage', 'Nachrichten'], rows))
    channel_rows = [(anchor('index.html', channel + '/index.html', data['name']), f'{data["messages"]:,}', f'{data["first"]} bis {data["last"]}') for channel, data in report['channels'].items()]
    intro = '<p>Willkommen im IRC-Archiv der Lowlevel-Community! Hier kannst du in den alten Gesprächen stöbern oder nach Begriffen und Nicknamen suchen.</p>'
    intro += '<p>' + anchor('index.html', 'search/index.html', 'Archiv durchsuchen') + f' · {report["messages"]:,} Nachrichten insgesamt</p>'
    intro += '<p>Enthalten sind ausschließlich öffentliche Nachrichten. Join-, Leave- und andere Ereignisse wurden nicht übernommen. Nicknamen und Nachrichten bleiben wie aufgezeichnet.</p>'
    intro += '<p>Eine beschädigte Nachricht vom 04.03.2013 in #lost enthält den ursprünglichen Wiederherstellungshinweis <code>[RECOVERY: 64 bytes lost to ciphertext overwrite]</code>.</p>'
    render_page(site, 'index.html', 'Lowlevel IRC-Archiv', intro + table(['Kanal', 'Nachrichten', 'Zeitraum'], channel_rows))
    render_page(site, 'search/index.html', 'IRC-Archiv durchsuchen', '<p>Suche in allen Nachrichten. Die Ergebnisse führen direkt zum passenden Gesprächsausschnitt. Mit den Filtern kannst du Kanal und Jahr eingrenzen.</p><div id="search"></div><p id="search-error" role="alert" hidden>Die Suche konnte nicht geladen werden. Bitte öffne das Archiv über einen Webserver und versuche es erneut.</p><noscript>Bitte JavaScript aktivieren, um die Suche zu verwenden. Die Kanal- und Datumsübersichten funktionieren auch ohne JavaScript.</noscript>', search=True)
    report['first'] = min(items[0][0] for items in summary.values())
    report['last'] = max(items[-1][0] for items in summary.values())
    (work / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'logs')
    parser.add_argument('--output', type=Path, default=ROOT / 'site')
    parser.add_argument('--work', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    build(args.input, args.output, args.work)

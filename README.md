# Lowlevel IRC-Archiv

Die alten Gespräche der Lowlevel-Community zum Stöbern und Nachlesen: **1.058.067 öffentliche Nachrichten** aus `#lost` und `#tyndur`, von September 2007 bis Juni 2017.

Aus den CSV-Dateien unter `logs/` entsteht eine statische Website mit Kanal-, Jahres-, Monats- und Tagesübersichten. Lange Tage werden auf Seiten mit je 200 Nachrichten verteilt. Jede Nachricht hat einen stabilen Link. Die Volltextsuche mit [Pagefind](https://pagefind.app/) führt zu Gesprächsausschnitten und lässt sich nach Kanal und Jahr filtern. Die Original-CSVs stehen pro Tag zum Download bereit.

## Auf GitHub Pages veröffentlichen

Dieses Verzeichnis ist ein eigenständiges Git-Repository. Auf GitHub beispielsweise das öffentliche Repository `lowlevel-eu/irc-archive` erstellen und die lokale Historie dorthin pushen:

```sh
git push -u origin main
```

Unter **Settings → Pages → Build and deployment → Source** die Option **GitHub Actions** auswählen. Der Workflow baut und prüft das Archiv bei einem Push auf `main` oder bei manuellem Start. Die Website liegt anschließend unter `https://lowlevel-eu.github.io/irc-archive/`.

CSV-Dateien und Bauwerkzeuge liegen im Repository. HTML und Suchindex werden bei jedem Build erzeugt und als Pages-Artefakt veröffentlicht; `site/`, `build/` und `node_modules/` werden nicht eingecheckt. Ohne JavaScript bleibt das Archiv vollständig über die Datumsübersichten nutzbar; nur die Suche benötigt JavaScript. Es werden keine externen Skripte, Schriften oder Analysedienste geladen.

## Lokal bauen

Benötigt werden Python 3.11 oder neuer und Node.js 22 mit npm. Python benötigt keine zusätzlichen Pakete.

```sh
npm ci
npm test
npm run build
python3 scripts/verify.py
node tests/search-smoke.mjs
python3 -m http.server 8000 --directory site
```

Dann `http://localhost:8000/` öffnen. Die Suche benötigt einen Webserver; direktes Öffnen der HTML-Dateien reicht dafür nicht. Relative Links und die Suchkonfiguration unterstützen sowohl eine Website am Domain-Stamm als auch ein Pages-Projektverzeichnis.

Der Build-Bericht und die Prüfresultate liegen unter `build/`. Die Prüfung kontrolliert jede gerenderte Nachricht, lokale Links, Suchtreffer-Anker und die unveränderten CSV-Downloads. Die Suche indexiert Gruppen von höchstens 50 Nachrichten, um Gesprächskontext zu bewahren und den Index überschaubar zu halten.

## Datenbestand

Die CSVs wurden unverändert aus dem wiederhergestellten Archiv übernommen. Das Format ist UTF-8 mit den Spalten `date/time`, `nick`, `message`; CSV-Quoting erhält Anführungszeichen, Kommas und mehrzeilige Nachrichten. Der Build übernimmt auch Nachrichten mit identischen Zeitstempeln in der ursprünglichen Reihenfolge.

Nicknamen bleiben wie aufgezeichnet. Enthalten sind ausschließlich öffentliche Nachrichten, keine Join-, Leave-, Quit- oder sonstigen Ereignisse.

Eine Nachricht in `#lost` vom 04.03.2013 enthält den Wiederherstellungshinweis `[RECOVERY: 64 bytes lost to ciphertext overwrite]`; dieser Text bleibt erhalten. Weitere Hinweise und die ursprünglichen Datumsübersichten stehen in [logs/README.md](logs/README.md).

Neue oder korrigierte CSVs werden im Schema `logs/<kanal>/<jahr>/<monat>/YYYY-MM-DD.csv` abgelegt. Fehlerhafte Spalten, Zeitstempel oder eine falsche Sortierung brechen den Build ab. Nachrichten-HTML wird als Text dargestellt; gültige HTTP-/HTTPS-Links sind anklickbar.

Das heutige [Wiki](https://github.com/lowlevel-eu/wiki/wiki), die [Discussions](https://github.com/lowlevel-eu/wiki/discussions) und das [Forum-/Wiki-Archiv](https://lowlevel-eu.github.io/) findest du ebenfalls auf GitHub.

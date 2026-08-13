# Horizon Setup — Übergabe

Kontext für Claude Code. Ziel: tägliche, zeitungsartige News-Briefing-Seite,
generiert von [Horizon](https://github.com/Thysrael/Horizon) via GitHub Actions,
publiziert auf GitHub Pages, lesbar auf Handy (PWA) und Laptop.

Kein eigener Server. Kein Docker-Deployment. Alles läuft in Actions.

## Getroffene Entscheidungen

| Punkt | Entscheidung |
|---|---|
| Tool | Horizon (`Thysrael/Horizon`, MIT, Python) |
| Deployment | GitHub Actions Cron + GitHub Pages |
| LLM-Provider | Gemini Flash (`provider: "gemini"`, `api_key_env: "GOOGLE_API_KEY"`) |
| Repo-Sichtbarkeit | public (Pages ist im Free-Plan nur bei public verfügbar) |
| Ausgabesprache | Deutsch gewünscht — **offener Punkt, siehe unten** |
| Reddit | kein API-Key nötig, Horizon scrapt über old.reddit.com |

## Aufgaben

### 1. Lokaler Testlauf zuerst

Nicht in Actions debuggen. Erst lokal, bis die Ausgabe passt.

```bash
uv sync
cp .env.example .env          # GOOGLE_API_KEY eintragen
uv run horizon-wizard         # generiert data/config.json
uv run horizon --hours 24     # Ergebnis in data/summaries/
```

Falls `uv` fehlt: `curl -LsSf https://astral.sh/uv/install.sh | sh`
Alternativ `pip install -e .` und dann `horizon` statt `uv run horizon`.

### 2. Quellen in `data/config.json`

Kategorien sind wichtig — sie steuern später die Ressort-Zuordnung.

```json
{
  "collection": { "time_window_hours": 24 },
  "ai": {
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "api_key_env": "GOOGLE_API_KEY",
    "throttle_sec": 4.5
  },
  "sources": {
    "rss": [
      { "name": "heise",        "url": "https://www.heise.de/rss/heise-atom.xml",   "category": "tech-de",  "enabled": true },
      { "name": "tagesschau",   "url": "https://www.tagesschau.de/xml/rss2/",       "category": "news-de",  "enabled": true },
      { "name": "Simon Willison","url": "https://simonwillison.net/atom/everything/","category": "tech",    "enabled": true },
      { "name": "Quanta",       "url": "https://www.quantamagazine.org/feed/",      "category": "science", "profile": "science", "enabled": true },
      { "name": "Spektrum",     "url": "https://www.spektrum.de/alias/rss/spektrum-de-rss-feed/996406", "category": "science", "profile": "science", "enabled": true },
      { "name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "science", "profile": "science", "enabled": true },
      { "name": "IEEE Spectrum","url": "https://spectrum.ieee.org/feeds/feed.rss",  "category": "science", "profile": "science", "enabled": true }
    ],
    "hackernews": {
      "enabled": true, "fetch_top_stories": 30, "min_score": 100, "category": "tech"
    },
    "reddit": {
      "enabled": true,
      "fetch_comments": 5,
      "subreddits": [
        { "subreddit": "selfhosted",         "sort": "hot", "fetch_limit": 25, "min_score": 50,   "category": "tech" },
        { "subreddit": "devops",             "sort": "top", "fetch_limit": 25, "min_score": 30,   "category": "tech" },
        { "subreddit": "netsec",             "sort": "hot", "fetch_limit": 25, "min_score": 50,   "category": "security" },
        { "subreddit": "EverythingScience",  "sort": "hot", "fetch_limit": 25, "min_score": 200,  "category": "science", "profile": "science" },
        { "subreddit": "space",              "sort": "hot", "fetch_limit": 15, "min_score": 500,  "category": "space",   "profile": "science" }
      ]
    },
    "ossinsight": {
      "enabled": true,
      "period": "past_24_hours",
      "languages": ["All", "Python", "Go", "Rust"],
      "min_stars": 50,
      "max_items": 20,
      "category": "oss-trending"
    },
    "github": [
      { "type": "repo_releases", "owner": "grafana",  "repo": "loki",   "category": "oss-stack", "enabled": true },
      { "type": "repo_releases", "owner": "grafana",  "repo": "alloy",  "category": "oss-stack", "enabled": true },
      { "type": "repo_releases", "owner": "keycloak", "repo": "keycloak","category": "oss-stack", "enabled": true }
    ]
  }
}
```

**Feed-URLs vor dem Commit prüfen** — einige sind aus dem Gedächtnis notiert:

```bash
for u in URL1 URL2; do
  echo -n "$u -> "; curl -so /dev/null -w "%{http_code}\n" -A "Mozilla/5.0" "$u"
done
```
Alles außer 200 fliegt raus oder wird korrigiert.

### 3. Zeitungs-Struktur

Zwei Profile mit unterschiedlichem Bewertungsmaßstab, plus Ressort-Quoten:

```json
{
  "processing": {
    "profiles_dir": "profiles",
    "default_profile": "tech-news",
    "profile_settings": {
      "tech-news": { "threshold": 7.0, "topic_dedup": true },
      "science":   { "threshold": 7.5, "topic_dedup": true }
    }
  },
  "digest": {
    "max_items": 20,
    "profile_order": ["tech-news", "science"],
    "category_groups": {
      "aufmacher": { "name": "Top",              "limit": 4, "categories": ["news-de"] },
      "tech":      { "name": "Tech",             "limit": 5, "categories": ["tech", "tech-de", "security"] },
      "oss":       { "name": "OSS Trending",     "limit": 3, "categories": ["oss-trending"] },
      "stack":     { "name": "Mein Stack",       "limit": 3, "categories": ["oss-stack"] },
      "science":   { "name": "Forschung",        "limit": 5, "categories": ["science", "space"] }
    },
    "default_group": "vermischtes",
    "default_group_limit": 3
  }
}
```

Begründung für die Struktur:
- `oss-trending` und `oss-stack` bewusst **getrennt**. Sonst verdrängt
  "Rust-Projekt mit 3000 neuen Stars" jedes Release-Update, weil es höher scort.
- `default_group_limit: 3` ist ein bewusster Anti-Filterbubble-Slot: dort landet,
  was in kein Ressort passt.
- Das `science`-Profil braucht einen anderen Maßstab als `tech-news`. Der
  Scoring-Prompt in `profiles/science/` soll nach *Überraschung und Tragweite*
  fragen, nicht nach beruflicher Relevanz — und explizit festhalten, dass Nähe
  zu IT keine Bonuspunkte gibt. Sonst driftet die Auswahl zurück zu Computing.
- Wenn das Forschungs-Ressort an manchen Tagen leer bleibt: so gewollt.
  Threshold nicht senken, um die Seite zu füllen.

### 4. Sprache — offener Punkt

Horizon bewirbt offiziell nur Englisch und Chinesisch. Es gibt ein
`ai.languages`-Feld. Zu klären:

1. `"languages": ["de"]` setzen, lokal laufen lassen, Ausgabe prüfen.
2. Falls die Ausgabe nicht deutsch wird: Prompts in `profiles/` untersuchen.
   Dort liegen Analyse- und Zusammenfassungs-Anweisungen; ggf. auf Deutsch
   umschreiben und ein Sprach-Statement ergänzen.
3. Falls die Sprache im Code hart auf en/zh gemappt ist: prüfen, ob eine
   minimale Erweiterung möglich ist, sonst en akzeptieren.

### 5. GitHub Actions + Pages

Der mitgelieferte Workflow liegt unter `.github/workflows/daily-summary.yml`.
Horizon schreibt publizierbares Markdown nach `docs/`, Pages baut daraus.

1. `data/config.json` committen. `.env` **nicht** (steht in `.gitignore`).
2. Settings → Secrets and variables → Actions → `GOOGLE_API_KEY` anlegen.
3. Im Workflow prüfen, dass das Secret im `env:`-Block durchgereicht wird und
   der Name exakt dem `api_key_env` aus der Config entspricht.
4. Settings → Pages aktivieren.
5. **Actions-Tab einmal öffnen und Workflows aktivieren** — in frisch geforkten
   Repos sind sie standardmäßig aus.
6. Cron: Actions läuft in UTC. Für 06:00 Berlin → `0 4 * * *` (Sommerzeit),
   `0 5 * * *` (Winterzeit). Keine automatische DST-Umstellung.
7. Erst per `workflow_dispatch` manuell auslösen, bevor auf den Cron vertraut wird.

## Bekannte Fallstricke

- **Erste Ausgabe zu leer** → Threshold zu hoch. 7.0 → 6.0.
- **Rate Limit in Actions, obwohl lokal ok** → mehr Items im echten Lauf.
  `throttle_sec` hoch oder `analysis_concurrency` runter.
- **Alles landet in "Vermischtes"** → `category`-Strings der Quellen matchen
  nicht die `categories`-Listen in `digest.category_groups`.
- **Reddit liefert nichts** → `min_score` zu hoch, oder Reddit blockt den
  Request. Reddit filtert unauthentifizierte Feed-Zugriffe heuristisch nach
  Headern und antwortet dann mit 403.
- **Fork lässt sich nicht auf privat stellen.** Falls doch privat gewünscht:
  Mirror-Push in ein neu angelegtes privates Repo, dazu GitHub Pro für Pages.

## Nicht tun

- Kein Docker-Compose-Deployment aufsetzen. Bewusst verworfen (kein Server).
- Kein arXiv-Feed ohne eigenes Profil mit Threshold ≥ 8.5 und `limit: 2` —
  sonst besteht die Ausgabe aus Paper-Titeln.
- Kein phys.org / EurekAlert. Das sind Verteiler für Uni-Pressemitteilungen;
  das LLM verwechselt PR-Superlative mit Bedeutung.

# Integration Log Search

A small search tool for integration platform logs. It turns large CSV log exports into a SQLite index and gives you a local web page where one search shows every step of a business transaction, across all processes.

I built the original version during my IT internship at a logistics company, where support staff had to search through large middleware log exports to trace what happened to a booking or an EDI message. My first version scanned the raw files on every search and was too slow. The second version, which this repository is based on, indexes the data once into SQLite and answers searches almost instantly. This is a clean rewrite with invented sample data and contains no company code or data.

## How it works

**Indexing (`build_index.py`)**

- Reads every CSV export in a folder.
- Decodes Base64 payloads so the text inside each message can be searched.
- Stores rows in SQLite and builds an inverted index (word → rows), plus indexes on message id and correlation id. Indexes are created after loading, which is much faster than updating them row by row.

**Searching (`search.py`)**

1. **Direct hits:** rows that contain every word in the query, found by intersecting the inverted index.
2. **Related steps:** all other rows that share a message id or correlation id with a direct hit. Searching for a booking number therefore also shows the customs and invoice steps that only mention the container number.

**Web page (`server.py`, `web/index.html`)**

A local server built only on Python's standard library (`http.server`), so it runs on a locked-down work laptop without installing anything. It serves a search page and two JSON endpoints, `/api/search?q=` and `/api/stats`.

## Run it

Requires Python 3.10 or newer. No third-party packages are needed.

```bash
python generate_sample_data.py              # fake log exports in sample_data/
python build_index.py sample_data --db logs.db
python server.py --db logs.db
```

Then open http://127.0.0.1:8770 and search for a booking number from the sample data, for example `BKG553470`.

## Tests

```bash
pip install pytest
pytest
```

## What I learned

- Measure first: the slow part was reading the files on every search, so indexing once fixed the real problem.
- A search tool is more useful when it answers the question behind the query. People did not want "the row with this number", they wanted "everything that happened to this shipment".
- Keeping to the standard library made the tool easy to hand over and run on any machine.

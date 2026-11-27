# Intel AI PC Arena prototype architecture

The Vite + React + TypeScript frontend owns presentation, the anonymous timed game session, persona and explainable recommendation rules. It talks to the optional hosted FastAPI API for anonymous sessions and round events. The hosted API persists catalogues, benchmark evidence and game events through SQLAlchemy; SQLite is the default and `ARENA_DATABASE_URL` can point at PostgreSQL.

Actual local hardware work belongs to `local-runner`, a separate localhost FastAPI companion. The runner reports detected OpenVINO devices, but detection alone does not verify inference. It deliberately returns `NOT VERIFIED` until a compatible model artifact, fixed benchmark contract and captured runtime evidence are configured. The web build remains playable without this process.

The included laptop catalogue and comparison fixtures are illustrative `SAMPLE DATA`. They are not inventory, Intel-certified measurements, or purchasing performance claims. Verified comparisons require approved, non-sample records with compatible brand, round, configuration and test protocol.

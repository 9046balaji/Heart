# Contributing

## Code Style

This project enforces consistent formatting and linting via **Black** and **Ruff**.

### Setup

Install the development tools and enable the pre-commit hooks:

```bash
pip install black ruff pre-commit
pre-commit install
```

### Formatting

```bash
# Format all files
black .

# Check without modifying
black --check .
```

### Linting

```bash
# Lint and auto-fix
ruff check --fix .

# Lint only (no fixes)
ruff check .
```

### Pre-commit

Once installed, the pre-commit hooks run automatically on `git commit`.
To run them manually against all files:

```bash
pre-commit run --all-files
```

### Configuration

- **Black** and **Ruff** settings live in `pyproject.toml`.
- **Pre-commit** hook versions are pinned in `.pre-commit-config.yaml`.

### Rules Summary

| Tool | Purpose |
|------|---------|
| Black | Opinionated code formatter (line-length 100) |
| Ruff | Fast linter — pycodestyle, Pyflakes, isort, bugbear, and more |
| pre-commit | Git hook runner — enforces style on every commit |

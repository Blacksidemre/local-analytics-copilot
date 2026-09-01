# Offline-first operation

Local Analytics Copilot is local-first and can perform normal file analysis without cloud APIs after
dependencies and the chosen Ollama model are installed.

## What needs internet once

- cloning/downloading the repository;
- installing Python and Node dependencies;
- installing Ollama;
- downloading a selected local model;
- optional dependency/security updates.

## What works offline afterward

- CSV/XLSX ingestion and deterministic profiling;
- Quick and Analyst calculations;
- bounded Agent planning/synthesis when Ollama and its model are already local;
- verifier, dashboards and Excel/HTML/PDF reports;
- local verified analysis history.

## Model unavailable behavior

- Quick and Analyst deterministic calculations remain available.
- The UI reports whether Ollama is unreachable or the selected model is missing.
- Unverified fallback prose is not invented.
- The user can select another installed local model in Settings.

## Local storage

Development mode uses the repository workspace. The packaged desktop design uses the operating
system's user-local application-data directory for workspace, config and logs. Dataset rows are not
automatically copied into analysis history.

## Network boundary

The canonical launcher and Data Bridge bind to loopback. Web research, remote Ollama and cloud model
tags remain disabled unless a user deliberately changes policy. Offline-first does not mean the
software replaces OS firewall, DLP or company information-security controls.

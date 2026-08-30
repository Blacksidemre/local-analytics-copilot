# Hermetic adapter boundary

This directory holds the versioned adapter contract for the future `Blacksidemre/hermetic` fork.
Hermetic should call the LAC Bridge on loopback rather than parse CSV/XLSX independently when the
hybrid mode is active.

Integration sequence:

1. Call `GET /api/v1/health` and require `data_bridge.status = ready`.
2. Send the selected file to `POST /api/v1/datasets/upload`.
3. If `status = sheet_selection_required`, show Hermetic's existing sheet picker and call
   `client.profile(result.file_path, chosenSheet)`; do not upload the workbook a second time.
4. Render Quick cards from `dashboard.cards`; every numeric card is already bound to a stable
   `finding_id` and deterministic `source`.
5. Treat `interpretation.status = unavailable` as a non-fatal local-model warning; the deterministic
   profile remains valid.

Do not bind dashboard cards by “first numeric column” or by display label. Bind them to stable
finding IDs and preserve the supplied unit and source.

Ingestion failures use `LacBridgeError.detail` with the stable shape
`{ code, message, hint, details }`; show `message` and optional `hint` to the user without replacing
the machine-readable `code`.

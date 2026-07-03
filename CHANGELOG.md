# Changelog

All notable changes to the Google Threat Intelligence (GTI) MCP Server repository for this deployment are documented below.

## [1.0.0-run] - 2026-07-03

### Changed
- **Target Project & Service**: Configured `gti-remotemcp-deploy.sh` to target GCP Project `apj-tsc-lab1` with Service Name `gti-mcp-service` in region `us-central1`.
- **Authentication**:
  - Removed standard token authentication middleware (`BearerTokenAuthMiddleware`) from the FastAPI server (`gti_mcp/server.py`).
  - Switched Cloud Run deployment configuration (`gti-remotemcp-deploy.sh`) to `--no-allow-unauthenticated`, delegating authentication to native Google Cloud IAM.
  - Removed custom token configuration (`MCP_AUTH_TOKEN`) from the deployment scripts.
- **Routing & Endpoints**:
  - Consolidated route endpoints in `gti_mcp/server.py` from `/sse` (GET) and `/messages` (POST) to a single route `/mcp` (GET and POST).
- **CORS Handling**:
  - Configured `CORSMiddleware` in `gti_mcp/server.py` to allow cross-origin requests (`*` for origins, methods, and headers).
- **Environment Ingestion**:
  - Ingested the API key `VT_APIKEY` directly as an environment variable in the Cloud Run deployment command.
- **Ignore Lists**:
  - Excluded the `.venv` directory from being uploaded to Cloud Build in `.gcloudignore`.

### Added
- **SSE Client Verification Script**: Added `test_gti_mcp_sse.py` to the repository root for verifying the health and tool-calling capabilities of the deployed service.

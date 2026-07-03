# Deployment & Usage Guide: GTI MCP Server on Cloud Run

This guide outlines how to deploy the modified Google Threat Intelligence (GTI) MCP server onto Google Cloud Run, secure it with IAM, and test it.

---

## 1. Architecture & Security Model

The deployment configuration replaces custom bearer-token middleware with native Google Cloud IAM authentication.

- **Egress**: The service runs on Cloud Run and makes outbound HTTPS requests to the VirusTotal/GTI API.
- **Ingress**: Only authorized Google Cloud IAM identities (users or service accounts) with the **Cloud Run Invoker** (`roles/run.invoker`) role can access the service.
- **Authentication**: Clients must pass a Google Cloud IAM Identity Token in the `Authorization: Bearer <ID_TOKEN>` header.

---

## 2. Deployment Steps

### Prerequisites
1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/gcloud).
2. Authenticate to Google Cloud:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```
3. Ensure the required APIs are enabled in your target project:
   - `run.googleapis.com` (Cloud Run Admin API)
   - `artifactregistry.googleapis.com` (Artifact Registry API)
   - `cloudbuild.googleapis.com` (Cloud Build API)

### Execute Deployment
1. Run the deployment script:
   ```bash
   chmod +x gti-remotemcp-deploy.sh
   ./gti-remotemcp-deploy.sh
   ```
2. The script will:
   - Build the container image using the `Dockerfile` and Google Cloud Build.
   - Store the image in Google Artifact Registry.
   - Deploy a Cloud Run service named `gti-mcp-service` in the `us-central1` region.
   - Restrict access to authenticated calls (`--no-allow-unauthenticated`).
   - Securely pass your `VT_APIKEY` as a service environment variable.

On completion, the script will output the **Service URL**, **SSE Endpoint**, and verification details.

---

## 3. How to Use & Connect

### Endpoint Details
- **Base Endpoint**: `https://<service-name>-<hash>-uc.a.run.app`
- **MCP SSE Endpoint**: `https://<service-name>-<hash>-uc.a.run.app/mcp`
  - A `GET` request starts the Server-Sent Events (SSE) stream.
  - Subsequent `POST` requests containing JSON-RPC payloads are sent to `/mcp?session_id=<id>`.

### Accessing the Restricted Service (IAM Authenticated)
Since the service is protected, standard requests require a Bearer token:
```bash
curl -i -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://gti-mcp-service-pkv46crkma-uc.a.run.app/mcp
```

For IDE clients (like Cline or Claude Desktop) or tools that do not support signing ID tokens natively, you can tunnel traffic through a local `gcloud` proxy:
1. Run the proxy:
   ```bash
   gcloud run services proxy gti-mcp-service --project <PROJECT_ID> --region us-central1
   ```
2. Connect your MCP client to:
   - URL: `http://localhost:8080/mcp`

---

## 4. Verification and Testing

We have provided a verification script `test_gti_mcp_sse.py` in the root of the repository to check if your deployment is fully operational.

### Running the Test Script

1. Set up a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install httpx
   ```
2. Execute the test script by passing your deployed Service URL:
   ```bash
   python3 test_gti_mcp_sse.py <YOUR_CLOUD_RUN_SERVICE_URL>
   ```
   *Example:*
   ```bash
   python3 test_gti_mcp_sse.py https://gti-mcp-service-pkv46crkma-uc.a.run.app
   ```

### What the Test Script Does
1. Authenticates using your active `gcloud` identity.
2. Connects to the SSE stream at `/mcp` and waits for a session ID.
3. Sends a JSON-RPC `initialize` message to the session POST endpoint.
4. Sends a JSON-RPC `tools/list` message.
5. Listens to the SSE stream and outputs the list of threat intelligence tools registered on the server.

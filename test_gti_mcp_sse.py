import asyncio
import httpx
import json
import subprocess
import sys

async def get_gcloud_token():
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error getting gcloud token: {e}")
        print("Please ensure you are authenticated with 'gcloud auth login'.")
        sys.exit(1)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_gti_mcp_sse.py <service-url>")
        print("Example: python3 test_gti_mcp_sse.py https://gti-mcp-service-pkv46crkma-uc.a.run.app")
        sys.exit(1)

    service_url = sys.argv[1].rstrip("/")
    mcp_endpoint = f"{service_url}/mcp"
    
    token = await get_gcloud_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"Connecting to SSE stream at {mcp_endpoint}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_path_event = asyncio.Event()
        session_path_holder = []

        async def read_sse():
            try:
                async with client.stream("GET", mcp_endpoint, headers=headers) as response:
                    print("SSE Connection Status Code:", response.status_code)
                    if response.status_code != 200:
                        print("Failed to connect to SSE stream")
                        return
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        print("SSE Received:", line)
                        if line.startswith("data: /mcp?session_id="):
                            session_path = line[5:].strip()
                            session_path_holder.append(session_path)
                            session_path_event.set()
            except Exception as e:
                print(f"Error in SSE reader: {e}")

        # Start the reader task in the background
        reader_task = asyncio.create_task(read_sse())

        # Wait for the session path to be discovered
        try:
            await asyncio.wait_for(session_path_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            print("Timed out waiting for session endpoint path from SSE stream.")
            reader_task.cancel()
            sys.exit(1)

        session_path = session_path_holder[0]
        post_url = f"{service_url}{session_path}"
        print(f"Discovered session endpoint path. Poster URL: {post_url}")

        # 1. Send POST initialize request
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        post_headers = headers.copy()
        post_headers["Content-Type"] = "application/json"
        
        print("\nSending 'initialize' request...")
        init_resp = await client.post(post_url, json=initialize_payload, headers=post_headers)
        print("Initialize POST Status Code:", init_resp.status_code)

        # Give it a second to process initialize
        await asyncio.sleep(1)

        # 2. Send POST tools/list request
        list_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2,
            "params": {}
        }
        
        print("\nSending 'tools/list' request...")
        list_resp = await client.post(post_url, json=list_payload, headers=post_headers)
        print("tools/list POST Status Code:", list_resp.status_code)
        
        # Keep running for a short time to allow the SSE stream to print the responses
        await asyncio.sleep(5)
        
        # Clean up the reader task
        reader_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())

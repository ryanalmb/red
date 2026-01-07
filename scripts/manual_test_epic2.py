import sys
import os
import asyncio
import shutil
import tempfile
import yaml
from pathlib import Path
from testcontainers.redis import RedisContainer
from aiohttp import web

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from cyberred.daemon.server import DaemonServer
from cyberred.daemon.ipc import IPCCommand, build_request, encode_message, decode_message
from cyberred.core.config import get_settings, reset_settings

async def mock_llm_handler(request):
    return web.json_response({
        "data": [{"id": "gpt-4", "object": "model"}]
    })

async def start_mock_llm():
    app = web.Application()
    app.router.add_get('/v1/models', mock_llm_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 0)
    await site.start()
    # Access the port from the socket
    server = site._server
    if server is None:
        # Fallback if _server not set immediately (should be for TCPSite)
        # Try a fixed port if random fails? But 0 should bind.
        # site.name usually has it? No.
        port = runner.addresses[0][1]
        return runner, f"http://localhost:{port}/v1"
    
    # Check runner.addresses
    port = runner.addresses[0][1]
    return runner, f"http://localhost:{port}/v1"

async def send_command(socket_path: Path, command: IPCCommand, params: dict = None):
    print(f"-> Sending {command} with params={params}...")
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        request = build_request(command, **(params or {}))
        writer.write(encode_message(request))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        
        writer.close()
        await writer.wait_closed()
        
        if response.status == "ok":
            print(f"<- OK: {response.data}")
            return response.data
        else:
            print(f"<- ERROR: {response.error}")
            return {"error": response.error}
            
    except Exception as e:
        print(f"<- EXCEPTION: {e}")
        return {"error": str(e)}

async def run_test():
    print("Starting Manual Verification for Epic 2...")
    
    # 1. Start Redis
    print("Starting Redis container...")
    with RedisContainer() as redis:
        redis_port = redis.get_exposed_port(6379)
        redis_host = redis.get_container_host_ip()
        print(f"Redis started at {redis_host}:{redis_port}")
        
        # 2. Start Mock LLM
        llm_runner, llm_base_url = await start_mock_llm()
        print(f"Mock LLM started at {llm_base_url}")

        # 3. Setup Env and Config
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            os.environ["CYBERRED_STORAGE__BASE_PATH"] = str(base_path)
            os.environ["CYBERRED_REDIS__HOST"] = redis_host
            os.environ["CYBERRED_REDIS__PORT"] = str(redis_port)
            os.environ["CYBERRED_LLM__TIMEOUT"] = "5" # Speed up check
            
            # Reset settings to pick up env vars
            reset_settings()
            
            # Create dummy scope and engagement config
            engagements_dir = base_path / "engagements"
            engagements_dir.mkdir(parents=True)
            
            scope_path = base_path / "scope.yaml"
            with open(scope_path, "w") as f:
                yaml.dump({
                    "allowed_networks": ["127.0.0.1/32"],
                    "excluded_networks": [],
                    "allowed_hostnames": ["localhost"]
                }, f)
                
            config_path = base_path / "engagements" / "test-eng.yaml"
            with open(config_path, "w") as f:
                yaml.dump({
                    "name": "test-eng",
                    "scope_path": str(scope_path),
                    "objectives": ["verify_daemon"],
                    "max_agents": 10,
                    # Inject LLM config for PreFlight LLMCheck
                    "openai_api_key": "fake-key",
                    "openai_api_base": llm_base_url
                }, f)
                
            # 4. Start Daemon
            print("Starting DaemonServer...")
            server = DaemonServer()
            server_task = asyncio.create_task(server.start())
            
            # Wait for socket
            socket_path = base_path / "daemon.sock"
            for _ in range(50):
                if socket_path.exists():
                    break
                await asyncio.sleep(0.1)
            
            if not socket_path.exists():
                print("FAIL: Socket not created")
                return
                
            print(f"Daemon socket found at {socket_path}")
            
            # 5. Verify Lifecycle
            try:
                # Story 2.5: Session Manager
                print("\n--- Testing Story 2.5: List Sessions ---")
                res = await send_command(socket_path, IPCCommand.SESSIONS_LIST)
                assert len(res["engagements"]) == 0
                print("PASS: Initially 0 engagements")
                
                # Story 2.6: Start Engagement
                print("\n--- Testing Story 2.6: Start Engagement ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_START, {
                    "config_path": str(config_path),
                    "ignore_warnings": True
                })
                
                if res.get("error"):
                     print(f"FAIL: Start failed: {res.get('error')}")
                     return

                eng_id = res.get("id")
                state = res.get("state")
                assert eng_id is not None
                assert state == "RUNNING"
                print(f"PASS: Started engagement {eng_id} in state {state}")
                
                # Story 2.4: State Machine (Pause/Resume)
                print("\n--- Testing Story 2.4 & 2.7: Pause ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_PAUSE, {"engagement_id": eng_id})
                assert res["state"] == "PAUSED"
                print("PASS: Paused engagement")
                
                print("\n--- Testing Story 2.4 & 2.7: Resume ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_RESUME, {"engagement_id": eng_id})
                assert res["state"] == "RUNNING"
                print("PASS: Resumed engagement")
                
                # Story 2.9: Attach/Detach (just verifying successful response)
                print("\n--- Testing Story 2.9: Attach ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_ATTACH, {"engagement_id": eng_id})
                sub_id = res.get("subscription_id")
                assert sub_id is not None
                print(f"PASS: Attached (subscription_id={sub_id})")
                
                print("\n--- Testing Story 2.9: Detach ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_DETACH, {"subscription_id": sub_id, "engagement_id": eng_id})
                assert res["detached"] is True
                print("PASS: Detached")

                # Story 2.8: Stop & Checkpoint
                print("\n--- Testing Story 2.8: Stop & Checkpoint ---")
                res = await send_command(socket_path, IPCCommand.ENGAGEMENT_STOP, {"engagement_id": eng_id})
                assert res["state"] == "COMPLETED" or res["state"] == "STOPPED"
                ckpt = res.get("checkpoint_path")
                print(f"PASS: Stopped engagement (checkpoint={ckpt})")
                
                # Check DB schema (Story 2.12)
                if ckpt and os.path.exists(ckpt):
                    print("PASS: Checkpoint file exists")
                else:
                    print("WARN: Checkpoint file missing or not returned")

                # Story 2.11: Daemon Stop
                print("\n--- Testing Story 2.11: Daemon Stop ---")
                res = await send_command(socket_path, IPCCommand.DAEMON_STOP)
                assert res["stopping"] is True
                print("PASS: Daemon stop requested")
                
                # Wait for server task to finish
                await server_task
                print("PASS: Daemon server task finished")
                
            except Exception as e:
                print(f"FAIL: Logic error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Cleanup
                await llm_runner.cleanup()
                if server._running:
                    await server.stop()

if __name__ == "__main__":
    asyncio.run(run_test())

"""Unix Socket Server for Daemon IPC.

Provides the DaemonServer class that listens on a Unix domain socket
for IPC communication with TUI/CLI clients.

Socket Path: ~/.cyber-red/daemon.sock
Permissions: 0o600 (owner only)

Usage:
    from cyberred.daemon.server import DaemonServer, run_daemon

    # Run daemon server
    await run_daemon(foreground=True)

    # Or manual control
    server = DaemonServer()
    await server.start()
    # ... server is running
    await server.stop()
"""

import asyncio
import os
import signal
import structlog
from pathlib import Path
from typing import Optional, Set, Callable

from cyberred.core.config import get_settings
from cyberred.core.exceptions import (
    EngagementNotFoundError,
    InvalidStateTransition,
    IPCProtocolError,
    ResourceLimitError,
    PreFlightCheckError,
    PreFlightWarningError,
)
from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    decode_message,
    encode_message,
    MAX_MESSAGE_SIZE,
)
from cyberred.daemon.session_manager import SessionManager
from cyberred.core.event_bus import EventBus
from cyberred.core.worker_pool import WorkerPool
from cyberred.daemon.state_machine import EngagementState
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.rag import RAGScheduler
from cyberred.rag.director_client import DirectorRAGClient


READ_TIMEOUT = 30.0  # seconds - prevents hung clients
MAX_CONNECTIONS = 100  # Prevent resource exhaustion


log = structlog.get_logger()


def get_socket_path() -> Path:
    """Get daemon socket path from settings.

    Returns:
        Path to daemon Unix socket file.
    """
    settings = get_settings()
    return Path(settings.storage.base_path).expanduser() / "daemon.sock"


def get_pid_path() -> Path:
    """Get daemon PID file path from settings.

    Returns:
        Path to daemon PID file.
    """
    settings = get_settings()
    return Path(settings.storage.base_path).expanduser() / "daemon.pid"


class DaemonServer:
    """Unix socket server for daemon IPC.

    Handles client connections, message parsing, and command routing.
    Supports multiple concurrent clients with graceful shutdown.

    Attributes:
        _socket_path: Path to the Unix socket file.
        _pid_path: Path to the PID file.
        _server: The asyncio server instance.
        _clients: Set of active client writers.
        _running: Flag indicating server is running.
        _shutdown_callback: Optional callback to signal main loop shutdown.
    """

    def __init__(
        self,
        socket_path: Optional[Path] = None,
        pid_path: Optional[Path] = None,
        max_engagements: int = 10,
        shutdown_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize DaemonServer.

        Args:
            socket_path: Optional path to Unix socket. Defaults to settings.
            pid_path: Optional path to PID file. Defaults to settings.
            max_engagements: Maximum concurrent engagements (default: 10).
            shutdown_callback: Optional callback to signal main loop shutdown.
        """
        if socket_path is None:
            socket_path = get_socket_path()
        if pid_path is None:
            pid_path = get_pid_path()

        self._socket_path = socket_path
        self._pid_path = pid_path
        self._server: Optional[asyncio.Server] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._running = False
        
        # Initialize EventBus with Redis URL constructed from host/port
        settings = get_settings()
        redis_url = f"redis://{settings.redis.host}:{settings.redis.port}"
        self._event_bus = EventBus(redis_url=redis_url)

        # Initialize CheckpointManager
        from cyberred.storage.checkpoint import CheckpointManager
        checkpoint_manager = CheckpointManager(base_path=settings.storage.base_path)

        # WorkerPool will be initialized in start() after async setup
        self._worker_pool: WorkerPool | None = None

        self._session_manager = SessionManager(
            max_engagements=max_engagements,
            event_bus=self._event_bus,
            checkpoint_manager=checkpoint_manager,
            worker_pool=None,  # Will be set in start() after initialization
        )
        self._shutdown_callback = shutdown_callback

        # Initialize RAG Scheduler (Story 6.12)
        # Note: get_settings already imported at module level
        self._rag_scheduler = RAGScheduler(settings.rag)

        # Track streaming clients: writer -> (engagement_id, streaming_task)
        self._streaming_clients: dict[asyncio.StreamWriter, tuple[str, asyncio.Task]] = {}

    @property
    def session_manager(self) -> SessionManager:
        """Get the session manager instance."""
        return self._session_manager

    async def start(self) -> None:
        """Start the Unix socket server.

        Creates socket at configured path with restricted permissions.
        Cleans up stale socket files from previous unclean shutdown.
        Creates PID file for daemon identification.
        """
        # Clean up stale socket file
        if self._socket_path.exists():
            log.warning("removing_stale_socket", path=str(self._socket_path))
            self._socket_path.unlink()

        # Ensure parent directory exists
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Start server
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self._socket_path),
            limit=MAX_MESSAGE_SIZE * 2,  # Allow headroom for soft limit check
        )

        # Set restrictive permissions (owner only)
        os.chmod(self._socket_path, 0o600)

        # Write PID file
        self._pid_path.write_text(str(os.getpid()))

        self._running = True

        # Initialize shared worker pool for all engagements
        self._worker_pool = WorkerPool(
            event_bus=self._event_bus,
            pool_size=10,
            container_prefix="red-kali-worker"
        )
        try:
            await self._worker_pool.initialize()
            # Pass to session manager for use by orchestrators
            self._session_manager._worker_pool = self._worker_pool
            log.info("worker_pool_initialized", pool_size=10)
        except Exception as e:
            log.warning("worker_pool_init_failed", error=str(e))
            # Continue without Docker - agents can still do LLM work

        # Start config file watcher for hot reload (Story 2.13)
        from cyberred.core.config import _SettingsHolder
        settings = get_settings()
        system_config_path = Path(settings.storage.base_path).expanduser() / "config.yaml"
        if system_config_path.exists():
            try:
                _SettingsHolder.start_watching(system_config_path)
                log.info("config_watcher_started", path=str(system_config_path))
            except Exception as e:
                log.warning("config_watcher_start_failed", error=str(e))
        
        log.info(
            "daemon_server_started",
            socket=str(self._socket_path),
            pid=os.getpid(),
        )

        # Start RAG Scheduler (Story 6.12)
        await self._rag_scheduler.start()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single client connection.

        Reads messages in a loop, routes commands, and sends responses.
        Handles client disconnection and protocol errors gracefully.

        Args:
            reader: Stream reader for client connection.
            writer: Stream writer for client connection.
        """
        if len(self._clients) >= MAX_CONNECTIONS:
            log.warning("max_connections_reached", limit=MAX_CONNECTIONS)
            writer.close()
            await writer.wait_closed()
            return

        self._clients.add(writer)
        client_id = id(writer)
        log.info("client_connected", client_id=client_id)

        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(
                        reader.readline(),
                        timeout=READ_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    # Don't timeout clients with active streaming sessions.
                    # The streaming task manages its own heartbeats and
                    # connection health. Once streaming ends, the entry is
                    # removed from _streaming_clients and the next timeout
                    # will break normally.
                    if writer in self._streaming_clients:
                        continue
                    log.warning("client_read_timeout", client_id=client_id)
                    break
                except (asyncio.LimitOverrunError, ValueError):
                    log.warning("message_hard_limit_exceeded", client_id=client_id)
                    break

                if not data:
                    break  # Client disconnected

                # Fix: Race Condition (Review Finding #1)
                # Check running state again as shutdown might have started while we awaited read
                if not self._running:
                    log.warning("command_received_during_shutdown", client_id=client_id)
                    break

                # Enforce message size limit (prevent DoS)
                if len(data) > MAX_MESSAGE_SIZE:
                    log.warning(
                        "message_too_large_disconnecting",
                        size=len(data),
                        limit=MAX_MESSAGE_SIZE,
                        client_id=client_id,
                    )
                    break # Disconnect client immediately

                try:
                    request = decode_message(data)
                    if not isinstance(request, IPCRequest):
                        raise IPCProtocolError("Expected IPCRequest")

                    response = await self._handle_command(request, writer)
                    writer.write(encode_message(response))
                    await writer.drain()

                except IPCProtocolError as e:
                    log.warning("protocol_error", error=str(e))
                    # Can't send error response without request_id

        except (ConnectionResetError, BrokenPipeError):
            log.warning("client_disconnected_abruptly", client_id=client_id)
        finally:
            # Cancel any streaming task for this client
            if writer in self._streaming_clients:
                _, streaming_task = self._streaming_clients.pop(writer)
                streaming_task.cancel()
                log.info("streaming_task_cancelled", client_id=client_id)

            self._clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass  # Ignore errors during close
            log.info("client_disconnected", client_id=client_id)

    async def _handle_command(
        self, request: IPCRequest, writer: asyncio.StreamWriter | None = None
    ) -> IPCResponse:
        """Route and handle IPC command.

        Args:
            request: The IPC request to handle.
            writer: Optional stream writer for streaming commands.

        Returns:
            IPCResponse with result or error.
        """
        log.debug(
            "handling_command",
            command=request.command,
            request_id=request.request_id,
        )

        try:
            command = IPCCommand(request.command)
        except ValueError:
            return IPCResponse.create_error(
                f"Unknown command: {request.command}",
                request.request_id,
            )

        try:
            # Special handling for attach - needs writer for streaming
            if command == IPCCommand.ENGAGEMENT_ATTACH and writer:
                return await self._handle_engagement_attach(request, writer)

            handler_map = {
                IPCCommand.SESSIONS_LIST: self._handle_sessions_list,
                IPCCommand.ENGAGEMENT_START: self._handle_engagement_start,
                IPCCommand.ENGAGEMENT_ATTACH: lambda r: self._handle_engagement_attach(r, None),
                IPCCommand.ENGAGEMENT_DETACH: self._handle_engagement_detach,
                IPCCommand.ENGAGEMENT_PAUSE: self._handle_engagement_pause,
                IPCCommand.ENGAGEMENT_RESUME: self._handle_engagement_resume,
                IPCCommand.ENGAGEMENT_STOP: self._handle_engagement_stop,
                IPCCommand.DAEMON_STOP: self._handle_daemon_stop,
                IPCCommand.DAEMON_CONFIG_RELOAD: self._handle_config_reload,
                IPCCommand.RAG_REFRESH: self._handle_rag_refresh,
                IPCCommand.ENGAGEMENT_PIVOT: self._handle_engagement_pivot,
            }

            handler = handler_map.get(command)
            if handler:
                return await handler(request)

            # Fallback for any unhandled commands
            return IPCResponse.create_ok({}, request.request_id)

        except EngagementNotFoundError as e:
            return IPCResponse.create_error(str(e), request.request_id)
        except InvalidStateTransition as e:
            return IPCResponse.create_error(str(e), request.request_id)
        except ResourceLimitError as e:
            return IPCResponse.create_error(str(e), request.request_id)
        except FileNotFoundError as e:
            return IPCResponse.create_error(str(e), request.request_id)
        except Exception as e:
            log.exception("command_handler_error", error=str(e))
            return IPCResponse.create_error(f"Internal error: {e}", request.request_id)

    async def _handle_sessions_list(self, request: IPCRequest) -> IPCResponse:
        summaries = self._session_manager.list_engagements()
        return IPCResponse.create_ok(
            {
                "engagements": [
                    {
                        "id": s.id,
                        "state": s.state,
                        "agent_count": s.agent_count,
                        "finding_count": s.finding_count,
                        "created_at": s.created_at.isoformat(),
                    }
                    for s in summaries
                ]
            },
            request.request_id,
        )

    async def _handle_engagement_start(self, request: IPCRequest) -> IPCResponse:
        config_path = request.params.get("config_path")
        if not config_path:
            return IPCResponse.create_error(
                "Missing required parameter: config_path",
                request.request_id,
            )
        config_path = Path(config_path)
        ignore_warnings = request.params.get("ignore_warnings", False)
        
        try:
            engagement_id = self._session_manager.create_engagement(config_path)
            new_state = await self._session_manager.start_engagement(engagement_id, ignore_warnings=ignore_warnings)
            return IPCResponse.create_ok(
                {"id": engagement_id, "state": str(new_state)},
                request.request_id,
            )
        except (PreFlightCheckError, PreFlightWarningError) as e:
            return IPCResponse.create_error(str(e), request.request_id)

    async def _handle_engagement_attach(
        self, request: IPCRequest, writer: asyncio.StreamWriter | None = None
    ) -> IPCResponse:
        engagement_id = request.params.get("engagement_id")
        if not engagement_id:
            return IPCResponse.create_error(
                "Missing required parameter: engagement_id",
                request.request_id,
            )

        # Get engagement context for state snapshot
        context = self._session_manager.get_engagement_or_raise(engagement_id)

        # Validate state allows attachment
        if context.state not in (EngagementState.RUNNING, EngagementState.PAUSED):
            return IPCResponse.create_error(
                f"Cannot attach to engagement in {context.state} state. "
                "Engagement must be RUNNING or PAUSED.",
                request.request_id,
            )

        # Create subscription for streaming (noop callback)
        def _noop_callback(event: object) -> None:
            pass

        subscription_id = self._session_manager.subscribe_to_engagement(
            engagement_id, _noop_callback
        )

        # Build initial state snapshot
        scope_targets = []
        if context.orchestrator and hasattr(context.orchestrator, "get_scope_targets"):
            try:
                scope_targets = context.orchestrator.get_scope_targets()
            except Exception:
                pass

        snapshot = {
            "engagement_id": engagement_id,
            "state": str(context.state),
            "agent_count": context.agent_count,
            "finding_count": context.finding_count,
            "subscription_id": subscription_id,
            "agents": [],
            "findings": [],
            "scope_targets": scope_targets,
        }

        log.info(
            "client_attached",
            engagement_id=engagement_id,
            subscription_id=subscription_id,
        )

        # If writer is provided, start streaming EventBus events to client
        if writer and context.orchestrator:
            streaming_task = asyncio.create_task(
                self._stream_events_to_client(writer, engagement_id)
            )
            self._streaming_clients[writer] = (engagement_id, streaming_task)
            log.info("streaming_started", engagement_id=engagement_id)

        return IPCResponse.create_ok(snapshot, request.request_id)

    async def _stream_events_to_client(
        self, writer: asyncio.StreamWriter, engagement_id: str
    ) -> None:
        """Stream EventBus events to an attached TUI client.

        Subscribes to swarm:* channels and forwards events as StreamEvents.
        Runs until the writer is closed or an error occurs.
        """
        event_queue: asyncio.Queue = asyncio.Queue()

        async def queue_event(channel: str, data: dict) -> None:
            """Queue an event for sending to client."""
            await event_queue.put((channel, data))

        # Subscribe to relevant EventBus channels
        channels = [
            "swarm:log",
            "swarm:brain",
            "swarm:status",
            "swarm:terminal",
            "swarm:worker_status",
            "swarm:tool",
            # Story 12.4: C2 Heartbeat Monitoring
            "c2:heartbeat:warning",
            "c2:heartbeat:critical",
            "c2:heartbeat:lost",
            "c2:reconnecting",
        ]
        # Keep subscription tasks alive - they run background listeners
        subscription_tasks = []
        for channel in channels:
            task = await self._event_bus.subscribe(channel, lambda d, c=channel: queue_event(c, d))
            subscription_tasks.append(task)

        # Story 7.26: Subscribe to stigmergic agent channels via pattern matching
        stigmergic_patterns = [
            "findings:*",
            "agents:*",
            "strategies:*",
        ]
        for pattern in stigmergic_patterns:
            task = await self._event_bus.psubscribe(
                pattern,
                lambda ch, d, p=pattern: queue_event(ch, d),
            )
            subscription_tasks.append(task)

        log.info("event_subscriptions_started", engagement_id=engagement_id, channels=channels)

        try:
            while True:
                try:
                    # Wait for events with timeout for heartbeat
                    channel, data = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Map channel to StreamEventType
                    event_type_map = {
                        "swarm:log": StreamEventType.LOG_UPDATE,
                        "swarm:brain": StreamEventType.BRAIN_UPDATE,
                        "swarm:status": StreamEventType.AGENT_STATUS,
                        "swarm:terminal": StreamEventType.TERMINAL_UPDATE,
                        "swarm:worker_status": StreamEventType.WORKER_STATUS,
                        "swarm:tool": StreamEventType.TOOL_UPDATE,
                        # Story 12.4: C2 Heartbeat Monitoring
                        "c2:heartbeat:warning": StreamEventType.C2_HEARTBEAT,
                        "c2:heartbeat:critical": StreamEventType.C2_HEARTBEAT,
                        "c2:heartbeat:lost": StreamEventType.C2_HEARTBEAT,
                        "c2:reconnecting": StreamEventType.C2_HEARTBEAT,
                    }
                    # Check static map first, then match stigmergic patterns
                    event_type = event_type_map.get(channel)
                    if event_type is None:
                        if channel.startswith("findings:"):
                            event_type = StreamEventType.FINDING
                        elif channel.startswith("strategies:"):
                            event_type = StreamEventType.STRATEGY_UPDATE
                        elif channel.startswith("agents:"):
                            event_type = StreamEventType.AGENT_STATUS
                        else:
                            event_type = StreamEventType.AGENT_STATUS

                    # Create and send StreamEvent
                    stream_event = StreamEvent(
                        event_type=event_type,
                        data=data,
                    )
                    writer.write(encode_stream_event(stream_event))
                    await writer.drain()

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = StreamEvent(
                        event_type=StreamEventType.HEARTBEAT,
                        data={"engagement_id": engagement_id},
                    )
                    try:
                        writer.write(encode_stream_event(heartbeat))
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError):
                        log.info("client_disconnected_during_heartbeat", engagement_id=engagement_id)
                        break

                except (ConnectionResetError, BrokenPipeError):
                    log.info("client_disconnected_during_stream", engagement_id=engagement_id)
                    break

        except asyncio.CancelledError:
            log.info("streaming_cancelled", engagement_id=engagement_id)
        finally:
            # Cancel subscription tasks
            for task in subscription_tasks:
                task.cancel()
            # Cleanup: remove from streaming clients
            self._streaming_clients.pop(writer, None)
            log.info("streaming_stopped", engagement_id=engagement_id)

    async def _handle_engagement_detach(self, request: IPCRequest) -> IPCResponse:
        subscription_id = request.params.get("subscription_id")
        if not subscription_id:
            return IPCResponse.create_error(
                "Missing required parameter: subscription_id",
                request.request_id,
            )
        
        self._session_manager.unsubscribe_from_engagement(subscription_id)
        
        log.info("client_detached", subscription_id=subscription_id)
        
        return IPCResponse.create_ok(
            {"detached": True, "subscription_id": subscription_id},
            request.request_id,
        )

    async def _handle_engagement_pause(self, request: IPCRequest) -> IPCResponse:
        engagement_id = request.params.get("engagement_id")
        if not engagement_id:
            return IPCResponse.create_error(
                "Missing required parameter: engagement_id",
                request.request_id,
            )
        new_state = self._session_manager.pause_engagement(engagement_id)
        return IPCResponse.create_ok(
            {"id": engagement_id, "state": str(new_state)},
            request.request_id,
        )

    async def _handle_engagement_resume(self, request: IPCRequest) -> IPCResponse:
        engagement_id = request.params.get("engagement_id")
        if not engagement_id:
            return IPCResponse.create_error(
                "Missing required parameter: engagement_id",
                request.request_id,
            )
        new_state = self._session_manager.resume_engagement(engagement_id)
        return IPCResponse.create_ok(
            {"id": engagement_id, "state": str(new_state)},
            request.request_id,
        )

    async def _handle_engagement_stop(self, request: IPCRequest) -> IPCResponse:
        engagement_id = request.params.get("engagement_id")
        if not engagement_id:
            return IPCResponse.create_error(
                "Missing required parameter: engagement_id",
                request.request_id,
            )
        new_state, checkpoint_path = await self._session_manager.stop_engagement(engagement_id)
        return IPCResponse.create_ok(
            {
                "id": engagement_id,
                "state": str(new_state),
                "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
            },
            request.request_id,
        )

    async def _handle_config_reload(self, request: IPCRequest) -> IPCResponse:
        """Handle config reload IPC command (Story 2.13).
        
        Triggers manual config reload check, returning the reload status.
        """
        from cyberred.core.config import _SettingsHolder, get_reload_status
        
        settings = get_settings()
        config_path = Path(settings.storage.base_path).expanduser() / "config.yaml"
        
        if not config_path.exists():
            return IPCResponse.create_error(
                f"Config file not found: {config_path}",
                request.request_id,
            )
        
        # Trigger reload
        _SettingsHolder._handle_config_change(config_path)
        
        # Return current reload status
        status = get_reload_status()
        return IPCResponse.create_ok(status, request.request_id)

    async def _handle_rag_refresh(self, request: IPCRequest) -> IPCResponse:
        """Handle manual RAG refresh trigger (Story 6.12)."""
        await self._rag_scheduler.trigger_now()
        return IPCResponse.create_ok(
            {"triggered": True, "message": "RAG refresh triggered in background"},
            request.request_id
        )

    async def _handle_engagement_pivot(self, request: IPCRequest) -> IPCResponse:
        """Handle operator-initiated strategy pivot via Director RAG."""
        engagement_id = request.params.get("engagement_id")
        if not engagement_id:
            return IPCResponse.create_error(
                "Missing required parameter: engagement_id",
                request.request_id,
            )

        request_text = request.params.get("request_text", "Operator requests strategy pivot")
        operator_hint = request.params.get("hint")

        context = self._session_manager.get_engagement_or_raise(engagement_id)
        orchestrator = context.orchestrator
        if not orchestrator or not getattr(orchestrator, '_director_rag_client', None):
            return IPCResponse.create_error(
                "Director RAG client not available for this engagement",
                request.request_id,
            )

        rag_context = DirectorRAGClient.build_operator_request_context(
            request_text=request_text,
            target_service=request.params.get("target_service"),
            operator_hint=operator_hint,
            current_phase=orchestrator._get_current_phase(),
            environment=orchestrator._get_engagement_environment(),
        )

        try:
            pivot_result = await orchestrator._director_rag_client.query_strategy_pivot(rag_context)
            await orchestrator._publish_rag_pivot(pivot_result)

            return IPCResponse.create_ok({
                "methodologies": len(pivot_result.methodologies),
                "techniques": pivot_result.technique_ids[:20],
                "guidance": pivot_result.actionable_guidance[:2000],
                "query_time_ms": pivot_result.query_time_ms,
            }, request.request_id)
        except Exception as e:
            return IPCResponse.create_error(
                f"RAG pivot query failed: {e}",
                request.request_id,
            )

    async def _handle_daemon_stop(self, request: IPCRequest) -> IPCResponse:
        log.info("daemon_stop_requested", request_id=request.request_id)
        
        # Signal main loop if callback provided
        if self._shutdown_callback:
            self._shutdown_callback()
        
        # Also trigger server stop logic (graceful=True by default)
        asyncio.create_task(self.stop())
        return IPCResponse.create_ok({"stopping": True}, request.request_id)

    async def stop(self, timeout: float = 30.0, graceful: bool = True) -> int:
        """Stop the server gracefully with engagement preservation.

        Story 2.11: Graceful shutdown sequence:
        1. Notify all TUI clients of shutdown
        2. Pause all RUNNING engagements
        3. Checkpoint all PAUSED engagements to SQLite
        4. Disconnect all client subscriptions
        5. Close socket and cleanup files

        Args:
            timeout: Maximum time for graceful shutdown (default: 30s per NFR).
            graceful: If True, preserve engagement state before stopping.

        Returns:
            Exit code: 0 for success, 1 for timeout or error.
        """
        self._running = False
        exit_code = 0

        if graceful:
            try:
                # Import here to avoid circular import
                from cyberred.daemon.streaming import StreamEvent, StreamEventType
                
                async def _graceful_sequence() -> None:
                    nonlocal exit_code
                    # Step 1: Notify all TUI clients of impending shutdown
                    shutdown_event = StreamEvent(
                        event_type=StreamEventType.DAEMON_SHUTDOWN,
                        data={
                            "reason": "daemon_stopping", 
                            "shutdown_in_seconds": int(timeout),
                            "timeout": timeout
                        },
                    )
                    
                    # notify_all_clients is synchronous
                    notification_count = self._session_manager.notify_all_clients(shutdown_event)
                    log.info(
                        "shutdown_notifications_sent",
                        notification_count=notification_count,
                    )
                    
                    # Brief pause for clients to process notification
                    await asyncio.sleep(1.0)
                    
                    # Step 2 & 3: Pause all running, then checkpoint all paused
                    shutdown_result = await self._session_manager.graceful_shutdown()
                    log.info(
                        "engagement_shutdown_complete",
                        paused_count=len(shutdown_result.paused_ids),
                        checkpoint_count=len(shutdown_result.checkpoint_paths),
                        error_count=len(shutdown_result.errors),
                    )
                    
                    # Fix: Exit Code Data Loss (Review Finding #2)
                    if shutdown_result.errors:
                        log.error("shutdown_checkpoint_failures_detected", errors=shutdown_result.errors)
                        exit_code = 1

                    
                    # Step 4: Disconnect all client subscriptions
                    disconnected = self._session_manager.disconnect_all_clients()
                    log.info(
                        "clients_disconnected",
                        disconnected_count=disconnected,
                    )

                # Execute graceful sequence with timeout
                await asyncio.wait_for(_graceful_sequence(), timeout=timeout)
                log.info("graceful_shutdown_sequence_complete")
                
            except asyncio.TimeoutError:
                log.warning(
                    "graceful_shutdown_timeout_exceeded",
                    timeout=timeout,
                )
                exit_code = 1
            except Exception as e:
                log.error(
                    "graceful_shutdown_error",
                    error=str(e),
                )
                exit_code = 1

        # Always perform cleanup regardless of graceful success
        
        # Stop config watcher (Story 2.13)
        from cyberred.core.config import _SettingsHolder
        try:
            _SettingsHolder.stop_watching()
        except Exception as e:
            log.warning("config_watcher_stop_failed", error=str(e))

        # Close EventBus
        if hasattr(self, "_event_bus"):
            try:
                await self._event_bus.close()
            except Exception as e:
                log.warning("event_bus_close_failed", error=str(e))

        # Close all client connections
        for writer in list(self._clients):
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        # Close server
        if self._server:
            self._server.close()
            try:
                await asyncio.wait_for(
                    self._server.wait_closed(),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                log.warning("server_shutdown_timeout")

        # Remove socket file
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError as e:
                log.warning("socket_cleanup_failed", error=str(e))

        # Remove PID file
        if self._pid_path.exists():
            try:
                self._pid_path.unlink()
            except OSError as e:
                log.warning("pid_cleanup_failed", error=str(e))

        # Stop RAG Scheduler (Story 6.12)
        if hasattr(self, "_rag_scheduler"):
            await self._rag_scheduler.stop()

        log.info("daemon_server_stopped", exit_code=exit_code, graceful=graceful)
        return exit_code


async def run_daemon(foreground: bool = False) -> None:
    """Run the daemon server.

    Main entry point for running the daemon. Sets up signal handlers
    and runs the server until shutdown is requested.

    Args:
        foreground: If True, run in foreground (for systemd Type=simple).
                    If False, would daemonize (not implemented - use systemd).
    """
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def shutdown_handler(signum: int) -> None:
        sig_name = signal.Signals(signum).name
        log.info("shutdown_signal_received", signal=sig_name)
        shutdown_event.set()

    def sighup_handler() -> None:
        """Handle SIGHUP for config reload."""
        log.info("sighup_received", action="config_reload")
        # Trigger immediate config reload check (Story 2.13)
        from cyberred.core.config import _SettingsHolder
        settings = get_settings()
        config_path = Path(settings.storage.base_path).expanduser() / "config.yaml"
        if config_path.exists():
            _SettingsHolder._handle_config_change(config_path)

    # Shutdown signals
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown_handler(s))
        
    # SIGHUP for config reload
    if hasattr(signal, "SIGHUP"):
        loop.add_signal_handler(signal.SIGHUP, sighup_handler)



    server = DaemonServer(
        shutdown_callback=shutdown_event.set,
    )

    await server.start()

    try:
        # Wait for shutdown signal
        await shutdown_event.wait()
    finally:
        await server.stop()


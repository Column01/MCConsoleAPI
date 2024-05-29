import argparse
import asyncio
import json
from typing import AsyncGenerator, Optional, Union

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Response, Security, status
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery

from config import TomlConfig
from database import SQLiteDB
from services.process import Process
from util import generate_time_message

api_key_query = APIKeyQuery(name="api_key", auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def validate_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header),
) -> str:
    """Validates a user's API key

    Args:
        api_key_query (str, optional): API key from query parameter `api_key`
        api_key_header (str, optional): API key from header `x-api-key`

    Raises:
        HTTPException: Raised as 401 Unauthorized when API key Invalid or missing

    Returns:
        str: The API key used to authenticate
    """
    db = SQLiteDB("api_keys.db", autocommit=True)
    if api_key_query and db.has_api_key(api_key_query):
        return api_key_query
    if api_key_header and db.has_api_key(api_key_header):
        return api_key_header

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
    )


class MCConsoleAPI:
    def __init__(self, config: TomlConfig):
        self.config = config

        self.app = FastAPI()
        # Setup API routes
        self.router = APIRouter()
        self.router.add_api_route("/", self.read_root, methods=["GET"])
        self.router.add_api_route("/start_server", self.start_server, methods=["POST"])
        self.router.add_api_route("/stop_server", self.stop_server, methods=["POST"])
        self.router.add_api_route("/output", self.console_output, methods=["GET"])
        self.router.add_api_route("/input", self.console_input, methods=["POST"])
        self.router.add_api_route("/restart", self.restart_server, methods=["POST"])
        self.router.add_api_route(
            "/players", self.get_connected_players, methods=["GET"]
        )
        self.router.add_api_route("/servers", self.get_running_servers, methods=["GET"])
        self.router.add_api_route(
            "/reload_config", self.reload_config, methods=["POST"]
        )
        self.router.add_api_route(
            "/gen_api_key", self.generate_api_key, methods=["POST"]
        )

        self.app.include_router(self.router)

        # Dict to store server processes
        self.processes = {}

        # Setup the Database
        self.db = SQLiteDB("api_keys.db", autocommit=True)
        self.db.setup_database()

    async def read_root(self):
        """Web root. Just kinda here for fun"""
        return {
            "line": "Connected to MCConsoleAPI! You can read a server's output at '{server_name}/output'"
        }

    async def start_api_server(self):
        """Starts the API server"""
        server_config = uvicorn.Config(
            self.app,
            host=self.config["general"]["host"],
            port=self.config["general"]["port"],
            log_level=self.config["general"]["log_level"],
        )
        self.server = uvicorn.Server(server_config)

        # Start servers on startup
        await self.start_servers_on_startup()

        await self.server.serve()

    async def start_servers_on_startup(self):
        servers = self.config.get("servers", [])
        for server in servers:
            server_path = server["path"]
            server_name = server["name"]
            autostart = server.get("autostart", False)

            if autostart:
                process = Process(server_path, server_name, self.server_stopped)
                started = await process.start_server()

                if started:
                    self.processes[server_name] = process
                    print(
                        f"Minecraft server started successfully with name: {server_name}"
                    )
                else:
                    jar_pattern = process.config["minecraft"]["server_jar"]
                    print(
                        f"Failed to start the Minecraft server '{server_name}'. Please ensure that a server jar matching the pattern '{jar_pattern}' exists in the server path '{server_path}'"
                    )

    async def start_server(
        self,
        response: Response,
        server_name: str,
        server_path: Optional[str] = None,
        api_key=Security(validate_api_key),
    ) -> dict:
        """Starts a server using the server_name and path. If no path is set, it tries get the path from the API config."""
        if server_path is None:
            # Try to get the server info from the config file
            servers = self.config.get("servers", [])
            server_info = next((s for s in servers if s["name"] == server_name), None)
            if server_info is None:
                response.status_code = status.HTTP_404_NOT_FOUND
                return {
                    "message": f"A server doesn't exist with the name '{server_name}' in the API config. Please specify a file path to start the server"
                }
            server_path = server_info["path"]

        process = Process(server_path, server_name, self.server_stopped)
        started = await process.start_server()

        if started:
            self.processes[server_name] = process
            return {
                "message": f"Minecraft server started successfully with name: {server_name}"
            }
        else:
            jar_pattern = process.config["minecraft"]["server_jar"]
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "message": f"Failed to start the Minecraft server. Please ensure that a server jar matching the pattern '{jar_pattern}' exists in the server path '{server_path}'"
            }

    async def stop_server(
        self, response: Response, server_name: str, api_key=Security(validate_api_key)
    ) -> dict:
        """Stop a server with server_name"""
        if server_name not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with name '{server_name}' not found"}

        process = self.processes[server_name]

        if not process.running:
            return {"message": f"Server with name '{server_name}' is already stopped"}

        await process.server_input("stop")

        # Wait for the server to stop with a timeout of 30 seconds
        timeout = 30
        while process.running and timeout > 0:
            await asyncio.sleep(1)
            timeout -= 1

        if not process.running:
            self.processes.pop(server_name, None)
            return {"message": f"Server with name '{server_name}' stopped successfully"}
        else:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                "message": f"Server with name '{server_name}' failed to stop within the timeout period"
            }

    async def console_output(
        self,
        response: Response,
        server_name: str,
        lines: Union[int, None] = None,
        api_key=Security(validate_api_key),
    ) -> StreamingResponse:
        """Get output from the server console"""
        if server_name not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with name '{server_name}' not found"}
        return StreamingResponse(self.serve_console_lines(server_name, lines))

    async def console_input(
        self,
        response: Response,
        server_name: str,
        command: str,
        api_key=Security(validate_api_key),
    ) -> dict:
        """Send input to the server console"""
        if server_name not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with name '{server_name}' not found"}

        success, line = await self.processes[server_name].server_input(command)
        if success:
            return {"message": "success", "line": line}
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {
                "message": f"Error when processing command: {command}. Is it a valid command?",
                "line": line,
            }

    async def server_stopped(self, server_name: str, exit_code: int):
        """Called when a Minecraft server instance exits"""
        print(
            f"Minecraft server: {server_name} has stopped with exit code: {exit_code}"
        )
        if server_name in self.processes:
            self.processes.pop(server_name, None)

    async def serve_console_lines(
        self, server_name: str, lines: Union[int, None]
    ) -> AsyncGenerator[str, None]:
        """Internal function to stream console lines through /output"""
        if server_name not in self.processes:
            yield json.dumps({"error": f"Server with name '{server_name}' not found"})
            return

        if lines is None:
            last_line_count = 0
            while True:
                current_line_count = len(self.processes[server_name].scrollback_buffer)
                if current_line_count > last_line_count:
                    new_lines = self.processes[server_name].scrollback_buffer[
                        last_line_count:
                    ]
                    for line in new_lines:
                        yield json.dumps({"line": line}) + "\n"
                    last_line_count = current_line_count
                else:
                    # No new lines, pause before checking again
                    await asyncio.sleep(1)
        else:
            # Copy the scrollback buffer so we don't modify it
            for line in self.processes[server_name].scrollback_buffer[-lines:]:
                yield json.dumps({"line": line}) + "\n"

    async def restart_server(
        self,
        response: Response,
        server_name: str,
        time_delta: Optional[int] = None,
        api_key=Security(validate_api_key),
    ) -> dict:
        """Restarts the server with an optional time delta for when to do it"""
        if server_name not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with name '{server_name}' not found"}

        if not self.processes:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"message": "No Minecraft server instances are currently running"}

        process = self.processes[server_name]
        if time_delta is not None:
            if time_delta <= 0:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return {
                    "message": "Invalid time delta. Time delta must be greater than 0 seconds."
                }

            time_to_restart = generate_time_message(time_delta)

            msg = f"say WARNING: PLANNED SERVER RESTART IN {time_to_restart}"

            await process.server_input(msg)

            # Schedule the restart and reminder tasks using asyncio
            loop = asyncio.get_event_loop()
            loop.call_later(
                time_delta,
                asyncio.create_task,
                process.restart_server(),
            )

            alert_intervals = process.config["minecraft"]["restarts"]["alert_intervals"]
            for interval in alert_intervals:
                if time_delta > interval:
                    loop.call_later(
                        time_delta - interval,
                        asyncio.create_task,
                        process.send_restart_reminder(interval),
                    )

            msg2 = f"Scheduled a server restart in {time_to_restart}"
            print(msg2)
            return {"message": msg2}

        # If no time delta is provided, restart immediately
        await process.restart_server()
        print("Triggered server restart")
        return {"message": "Triggered a server restart successfully"}

    async def reload_config(
        self,
        response: Response,
        server_name: Optional[str] = None,
        api_key=Security(validate_api_key),
    ) -> dict:
        """Reloads server_name's config or the API config if none is specified"""
        if server_name is None:
            await self.config.reload()
            return {"message": "Config file reloaded successfully"}
        else:
            if server_name not in self.processes:
                response.status_code = status.HTTP_404_NOT_FOUND
                return {"message": f"Server with name '{server_name}' not found"}
            process = self.processes[server_name]
            await process.config.reload()
            return {
                "message": f"Config file reloaded successfully for server '{server_name}'"
            }

    async def generate_api_key(
        self, response: Response, name: str, api_key=Security(validate_api_key)
    ) -> dict:
        """Generates an API key. Requires an Admin API key"""
        if not self.db.is_admin_api_key(api_key):
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"message": "Only the admin API key can generate new API keys."}

        new_api_key = self.db.add_api_key(name)
        if new_api_key is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"message": f"An API key with the name '{name}' already exists."}
        else:
            return {
                "message": f"An API key was successfully created for the name: {name}",
                "api_key": new_api_key,
            }

    async def get_connected_players(
        self, response: Response, server_name: str, api_key=Security(validate_api_key)
    ) -> dict:
        """Get a list of connected players to server_name"""
        if server_name not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with name '{server_name}' not found"}
        return {"players": self.processes[server_name].connected_players}

    async def get_running_servers(self, api_key=Security(validate_api_key)) -> dict:
        """Get a list of running servers and their file paths"""
        running_servers = []
        for server_name, process in self.processes.items():
            server_path = process.get_server_path()
            running_servers.append({"name": server_name, "path": server_path})
        return {"servers": running_servers}


async def main(args: argparse.Namespace):
    # Load the server config file
    config = TomlConfig("api_config.toml")

    # Setup the API and start the server
    api = MCConsoleAPI(config)
    await api.start_api_server()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="MCConsoleAPI",
        description="A Python-Based async minecraft server wrapper that exposes HTTP endpoints for interaction with your server",
    )

    parser.add_argument(
        "-p",
        "--path",
        metavar="PATH",
        type=str,
        default=".",
        required=False,
        help="The path to your minecraft server",
    )
    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_task = asyncio.ensure_future(main(args))
    loop.run_until_complete(main_task)

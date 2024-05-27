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
        self.router.add_api_route("/start_server", self.start_server, methods=["POST"])
        self.router.add_api_route(
            "/{alias}/output", self.console_output, methods=["GET"]
        )
        self.router.add_api_route(
            "/{alias}/input", self.console_input, methods=["POST"]
        )
        self.router.add_api_route(
            "/{alias}/restart", self.restart_server, methods=["POST"]
        )
        self.router.add_api_route(
            "/{alias}/players", self.get_connected_players, methods=["GET"]
        )
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

        # Lock for reloading config
        self.config_reload_lock = asyncio.Lock()

    async def read_root(self):
        """Web root. Just kinda here for fun"""
        return {
            "line": "Connected to MCConsoleAPI! You can read the server output at '/output'"
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
        await self.server.serve()

    async def start_server(
        self,
        response: Response,
        server_path: str,
        alias: str,
        api_key=Security(validate_api_key),
    ) -> dict:
        process = Process(self.config, server_path, self.server_stopped)
        started = await process.start_server()

        if started:
            self.processes[alias] = process
            return {
                "message": f"Minecraft server started successfully with alias: {alias}"
            }
        else:
            jar_pattern = self.config["minecraft"]["server_jar"]
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "message": f"Failed to start the Minecraft server. Please ensure that a server jar matching the pattern '{jar_pattern}' exists in the server path '{server_path}'"
            }

    async def console_output(
        self,
        alias: str,
        lines: Union[int, None] = None,
        api_key=Security(validate_api_key),
    ) -> StreamingResponse:
        if alias not in self.processes:
            raise HTTPException(
                status_code=404, detail=f"Server with alias '{alias}' not found"
            )
        return StreamingResponse(self.serve_console_lines(alias, lines))

    async def console_input(
        self,
        response: Response,
        alias: str,
        command: str,
        api_key=Security(validate_api_key),
    ) -> dict:
        if alias not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with alias '{alias}' not found"}

        success, line = await self.processes[alias].server_input(command)
        if success:
            return {"message": "success", "line": line}
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {
                "message": f"Error when processing command: {command}. Is it a valid command?",
                "line": line,
            }

    async def server_stopped(self, exit_code: int):
        """Called when a Minecraft server instance exits"""
        print(f"Minecraft server has stopped with exit code: {exit_code}")

    async def serve_console_lines(
        self, alias: str, lines: Union[int, None]
    ) -> AsyncGenerator[str, None]:
        if alias not in self.processes:
            yield json.dumps({"error": f"Server with alias '{alias}' not found"})
            return

        if lines is None:
            last_line_count = 0
            while True:
                current_line_count = len(self.processes[alias].scrollback_buffer)
                if current_line_count > last_line_count:
                    new_lines = self.processes[alias].scrollback_buffer[
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
            for line in self.processes[alias].scrollback_buffer[-lines:]:
                yield json.dumps({"line": line}) + "\n"

    async def restart_server(
        self,
        response: Response,
        alias: str,
        time_delta: Optional[int] = None,
        api_key=Security(validate_api_key),
    ) -> dict:
        """Restarts the server with an optional time delta for when to do it"""
        if alias not in self.processes:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": f"Server with alias '{alias}' not found"}

        if not self.processes:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"message": "No Minecraft server instances are currently running"}

        if time_delta is not None:
            if time_delta <= 0:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return {
                    "message": "Invalid time delta. Time delta must be greater than 0 seconds."
                }

            time_to_restart = generate_time_message(time_delta)

            msg = f"say WARNING: PLANNED SERVER RESTART IN {time_to_restart}"
            await self.processes[alias].server_input(msg)

            # Schedule the restart and reminder tasks using asyncio
            loop = asyncio.get_event_loop()
            loop.call_later(
                time_delta, asyncio.create_task, self.processes[alias].restart_server()
            )

            alert_intervals = self.config["minecraft"]["restarts"]["alert_intervals"]
            for interval in alert_intervals:
                if time_delta > interval:
                    loop.call_later(
                        time_delta - interval,
                        asyncio.create_task,
                        self.processes[alias].send_restart_reminder(interval),
                    )

            msg2 = f"Scheduled a server restart in {time_to_restart}"
            print(msg2)
            return {"message": msg2}

        # If no time delta is provided, restart immediately
        await self.processes[alias].restart_server()
        print("Triggered server restart")
        return {"message": "Triggered a server restart successfully"}

    async def reload_config(self, api_key=Security(validate_api_key)) -> dict:
        async with self.config_reload_lock:
            self.config.reload()
        return {"message": "Config file reloaded successfully"}

    async def generate_api_key(
        self, response: Response, name: str, api_key=Security(validate_api_key)
    ) -> dict:
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

    async def get_connected_players(self, alias: str, api_key=Security(validate_api_key)) -> dict:
        if alias not in self.processes:
            return {"error": f"Server with alias '{alias}' not found"}
        return {"players": self.processes[alias].connected_players}


async def main(args: argparse.Namespace):
    # Load the server config file
    config = TomlConfig("config.toml")

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

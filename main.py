import argparse
import asyncio
import json
import os
from typing import Union

import uvicorn
from fastapi import APIRouter, FastAPI, Response, status, Security, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyQuery, APIKeyHeader

from config import JsonConfig
from database import SQLiteDB
from services.process import Process

api_key_query = APIKeyQuery(name="api_key", auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def validate_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header)
):
    db = SQLiteDB('api_keys.db', autocommit=True)
    if api_key_query and db.has_api_key(api_key_query):
        return api_key_query
    if api_key_header and db.has_api_key(api_key_header):
        return api_key_header

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key"
    )


class MCConsoleAPI:
    def __init__(self, config: JsonConfig, server_path: str):
        self.config = config
        self.server_path = server_path

        self.app = FastAPI()
        # Setup API routes
        self.router = APIRouter()
        self.router.add_api_route("/", self.read_root, methods=["GET"])
        self.router.add_api_route("/output", self.console_output, methods=["GET"])
        self.router.add_api_route("/input", self.console_input, methods=["POST"])

        self.app.include_router(self.router)

        # Setup the server process stuff
        self.process = Process(config, server_path, self.server_stopped)

        # Setup the Database
        self.db = SQLiteDB("api_keys.db", autocommit=True)
        self.db.setup_database()

    async def read_root(self):
        return {"line": "Connected to MCConsoleAPI! You can read the server output at '/output'"}

    async def start_server(self):
        """ This is the entry point to the entire script, this is run to start everything """
        # Start the minecraft server
        await self.process.start_server()
        # Setup the webserver stuff and start it
        server_config = uvicorn.Config(self.app, host=self.config["host"], port=self.config["port"], log_level=self.config["log_level"])
        self.server = uvicorn.Server(server_config)
        try:
            await self.server.serve()
        except (KeyboardInterrupt, RuntimeError, asyncio.CancelledError):
            print("Keyboard interrupt or other error received! Stopping minecraft server gracefully...")
            if self.process.running:
                # Send the server stop command
                success, line = await self.process.server_input("stop")
                if success:
                    print("Successfully triggered server stop. Waiting for process to close...")

                # Wait for the process to stop
                while self.process.running:
                    print('still running')
                    await asyncio.sleep(0.1)
            # TODO: Exit with better option. Only exists because oauth causes to hang when closing process normally.
            os._exit(0)

    async def console_output(self, lines: Union[int, None] = None) -> StreamingResponse:
        """ Gets n lines from the server output and returns it """
        return StreamingResponse(self.serve_console_lines(lines))

    async def console_input(self, response: Response, command: str, api_key=Security(validate_api_key)) -> dict:
        success, line = await self.process.server_input(command)
        if success:
            return {"message": "success", "line": line}
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {"message": f"Error when processing command: {command}. Is it a valid command?", "line": line}

    async def server_stopped(self, exit_code):
        print(f"Minecraft server has stopped with exit code: {exit_code}")

    async def serve_console_lines(self, lines: Union[int, None]) -> str:
        """ Streams console lines via HTTP """
        if lines is None:
            for line in self.process.scrollback_buffer:
                yield json.dumps({"line": line}) + "\n"
        else:
            # Copy the scollback buffer so we don't modify it
            copy = self.process.scrollback_buffer.copy()
            relevant = copy[-lines:]
            for line in relevant:
                yield json.dumps({"line": line}) + "\n"


async def main(args: argparse.Namespace):
    # Get the server path from the command arguments and change to that dir
    server_path = args.path
    os.chdir(server_path)

    # Load the server config file
    config = JsonConfig("config.json")

    # Setup the API and start the server
    api = MCConsoleAPI(config, server_path)
    await api.start_server()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="MCConsoleAPI",
        description="A Python-Based async minecraft server wrapper that exposes HTTP endpoints for interaction with your server"
    )

    parser.add_argument('-p', "--path", metavar="PATH", type=str, default=".", required=False, help="The path to your minecraft server")
    args = parser.parse_args()
    loop = asyncio.get_event_loop()
    main_task = asyncio.ensure_future(main(args))
    loop.run_until_complete(main_task)

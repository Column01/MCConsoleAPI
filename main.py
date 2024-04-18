import argparse
import asyncio
import itertools
import json
import os
import time
from typing import Union

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse

from config import JsonConfig
from services.process import Process


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
    
    async def read_root(self):
        return {"Hello": "World"}

    async def start_server(self):
        """ This is the entry point to the entire script, this is run to start everything """
        # Start the minecraft server
        await self.process.start_server()
        print("Minecraft Server has been started")

        print("Starting webserver")
        # Setup the webserver stuff and start it
        server_config = uvicorn.Config(self.app, host=self.config["host"], port=self.config["port"], log_level=self.config["log_level"])
        server = uvicorn.Server(server_config)
        await server.serve()

    async def console_output(self, lines: Union[int, None] = None) -> StreamingResponse:
        """ Gets n lines from the server output and returns it """
        return StreamingResponse(self.serve_console_lines(lines))

    async def console_input(self, command: str) -> dict:
        await self.process.server_input(command)
        # Wait for a short period of time to allow the process to generate output
        await asyncio.sleep(0.1)
        # Check the last line of the scrollback buffer to see if it ran correctly
        last_line = self.process.scrollback_buffer[-1]
        if "Unknown command" in last_line:
            return {"message": "failure", "reason": last_line}
        else:
            return {"message": "success"}

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
    asyncio.run(main(args))

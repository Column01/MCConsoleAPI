import asyncio
import collections
import json
import typing
from asyncio import SubprocessProtocol, transports
from typing import Optional, Union

from config import JsonConfig
from util.util import LimitedList, find_jar


class Process:
    def __init__(self, config: JsonConfig, server_path: str, exit_future: Optional[typing.Coroutine] = None):
        self.config = config
        self.server_path = server_path
        self.exit_future = exit_future
        self.loop = asyncio.get_event_loop()

    async def start_server(self):
        # Get the java command
        java_cmd = self.build_java_command()
        # Build the process protocol
        self.protocol = ProcessProtocol(self.proc_closed)
        self.scrollback_buffer = self.protocol.scrollback_buffer

        print(f"Starting server: {' '.join(java_cmd)}")
        # Start server process and connect our custom protocol to it
        self._transport, self._protocol = await self.loop.subprocess_exec(
            lambda: self.protocol,
            *java_cmd,
            stdin=asyncio.subprocess.PIPE, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )

    def build_java_command(self) -> list:
        """ Builds a java command from the config """
        java_cmd = []
        mc_config = self.config["minecraft"]
        # Add the java path
        java_cmd.append(mc_config["java_path"])
        # Add java arguments
        if mc_config.get("jvm_args") is not None:
            java_cmd.extend(mc_config["jvm_args"])

        # Add -jar and jar path
        java_cmd.append("-jar")
        jar_path = find_jar(mc_config["server_jar"])
        java_cmd.append(jar_path)
        # No GUI
        java_cmd.append("nogui")

        return java_cmd

    async def server_input(self, data: str) -> tuple[bool, str]:
        if self.protocol:
            print(f"Sending input to server STDIN: {data}")
            last_line = self.scrollback_buffer[-1]
            await self.protocol.write_process(data)

            # Wait for the last line in the scrollback buffer to change
            while self.scrollback_buffer[-1] == last_line:
                await asyncio.sleep(0.05)
            # Check the last line of output to see if it has an unknown command message
            line = self.scrollback_buffer[-1]
            if "unknown command" in line.lower():
                return (False, line)
            else:
                return (True, line)
        return (False, "Server protocol is not present... has the server been started?")

    async def proc_closed(self, exit_code):
        print(f"SERVER PROC CLOSED! {exit_code}")
        if self.exit_future is not None:
            await self.exit_future(exit_code)


class ProcessProtocol(SubprocessProtocol):
    """ Process Protocol that handles server process I/O """
    def __init__(self, exit_future: typing.Coroutine):
        # Exit future
        self.exit_future = exit_future

        self.loop = asyncio.get_event_loop()
        self.scrollback_buffer = LimitedList(maxlen=1000)

    def connection_made(self, transport: transports.BaseTransport):
        print("Connection with process established")
        self.transport = transport

        self.stdin = self.transport.get_pipe_transport(0)
        self.stdout = self.transport.get_pipe_transport(1)
        self.stderr = self.transport.get_pipe_transport(2)
        print("Saved references to STDIN/OUT/ERR")

    def pipe_data_received(self, fd: int, data: bytes):
        # Decode the data from the process and store it
        message = data.decode().strip()
        print(message)
        self.scrollback_buffer.append(message)

    def process_exited(self):
        code = self.transport.get_returncode()
        self.loop.create_task(self.exit_future(code))

    async def write_process(self, data: typing.Union[bytes, str]):
        if isinstance(data, str):
            data = data.encode()
        self.stdin.write(data + b"\n")

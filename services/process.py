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

        self.running = False

    async def start_server(self):
        # Get the java command
        java_cmd = self.build_java_command()
        # Build the process protocol
        self.protocol = ProcessProtocol(self.proc_closed)
        self.protocol.register_console_consumer(self.console_output)
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

        self.running = True

    def build_java_command(self) -> list:
        """ Builds a java command from the config """
        java_cmd = []
        mc_config = self.config["minecraft"]
        # Add the java path
        java_cmd.append(mc_config["java_path"])
        # Add java arguments
        if mc_config.get("jvm_args") is not None:
            java_cmd.extend(mc_config["jvm_args"])

        # Unsupported terminal
        java_cmd.append("-Djline.terminal=jline.UnsupportedTerminal")

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
            future = self.loop.create_future()
            self.protocol.register_console_consumer(future, temp=True)
            await self.protocol.write_process(data)
            await future
            line = future.result()
            return ('unknown command' not in line.lower(), line)

        return (False, "Server protocol is not present... has the server been started?")

    async def proc_closed(self, exit_code):
        print(f"SERVER PROC CLOSED! {exit_code}")
        self.running = False
        if self.exit_future is not None:
            await self.exit_future(exit_code)
    
    async def console_output(self, output: str):
        """ Callback used to handle output from the server console """
        print(output)


class ProcessProtocol(SubprocessProtocol):
    """ Process Protocol that handles server process I/O """
    def __init__(self, exit_future: typing.Coroutine):
        # Exit future
        self.exit_future = exit_future

        self.loop = asyncio.get_event_loop()
        self.scrollback_buffer = LimitedList(maxlen=1000)
        self._consumers = []
        self._temp_consumers = []

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
        self.scrollback_buffer.append(message)

        # Forward console output to all consumers
        for consumer in self._consumers:
            if asyncio.isfuture(consumer):
                consumer.set_result(message)
            else:
                self.loop.create_task(consumer(message))

        # Temporary consumers, get removed after one usage. 
        # Useful for some things like checking the result of a command execution
        for i in range(len(self._temp_consumers)):
            consumer = self._temp_consumers.pop()
            if asyncio.isfuture(consumer):
                consumer.set_result(message)
            else:
                self.loop.create_task(consumer(message))

    def process_exited(self):
        # Called when the java process exits
        code = self.transport.get_returncode()
        self.loop.create_task(self.exit_future(code))

    async def write_process(self, data: typing.Union[bytes, str]):
        # Write data to the process STDIN
        if isinstance(data, str):
            data = data.encode()
        self.stdin.write(data + b"\n")
    
    def register_console_consumer(self, callback: Union[typing.Coroutine, asyncio.Future], temp: bool=False):
        """
        Registers a console consumer coroutine.

        Args:
            callback (Coroutine, Future): A coroutine that handles output from the console.
            temp (bool, optional): Whether or not the callback is temporary (only run once). Defaults to False.

        Raises:
            ValueError: If `callback` is not a coroutine.
        """
        if not asyncio.iscoroutine(callback) or not asyncio.isfuture(callback):
            raise ValueError("Callback must be a coroutine or an awaitable future!")
        # Add the new consumer to the list of consumers
        if temp:
            self._temp_consumers.append(callback)
        else:
            self._consumers.append(callback)

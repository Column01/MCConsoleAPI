import asyncio
import os
import re
import typing
from asyncio import SubprocessProtocol, transports
from datetime import datetime
from typing import Optional, Union

from ..services.server_analytics import ServerAnalytics
from ..services.player_analytics import PlayerAnalytics
from ..utils.config import TomlConfig
from ..utils.logging import get_logger
from ..utils.sse import *
from ..utils.util import LimitedList, find_jar, generate_time_message


class Process:
    def __init__(
        self,
        server_path: str,
        server_name: str,
        exit_future: Optional[typing.Coroutine] = None,
    ):
        # Ensure we always get the absolute path to the server directory
        self.server_path = os.path.abspath(server_path)
        self.server_name = server_name
        self.exit_future = exit_future
        self.loop = asyncio.get_event_loop()
        self.logger = get_logger(self.server_name)

        # Load the config from the server_path directory
        config_path = os.path.join(self.server_path, "config.toml")
        try:
            self.config = TomlConfig(config_path)
        except FileNotFoundError:
            self.logger.info(
                "Error when loading the config file for the server as it was not found!"
            )

        self.server_analytics = ServerAnalytics(self.server_name)

        self.player_analytics = PlayerAnalytics()

        # List of connected players
        self.connected_players = []
        # List of connected console users, different from players (admins on console)
        self.connected_users = []
        # Player chat history
        self.chat_history = []
        # Server Sent Events Queue (excludes console output)
        self.sse_queue: dict[str, list[SSEEvent]] = {}
        self.last_sse_id = 0
        self.running = False

    async def start_server(self) -> bool:
        # Reload the config before using it
        await self.reload_config()

        # Empty connected players list
        self.connected_players.clear()
        # Empty chat_history list
        self.chat_history.clear()

        # Get the java command
        try:
            java_cmd = await self.build_java_command()
        except FileNotFoundError as e:
            self.logger.error(f"An error occurred when building the Java command: {e}")
            return False

        # Build the process protocol
        self.protocol = ProcessProtocol(self.server_name, self.proc_closed)
        self.protocol.register_console_consumer(self.console_output)
        self.scrollback_buffer = self.protocol.scrollback_buffer
        self.logger.info(
            f"Starting server with the following CMD: {' '.join(java_cmd)}"
        )
        # Start server process and connect our custom protocol to it
        self._transport, self._protocol = await self.loop.subprocess_exec(
            lambda: self.protocol,
            *java_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.server_path,  # start process in server dir
        )

        # Server started flag
        self.running = True
        # Server restarting flag
        self.restarting = False

        # Check the configuration for automatic restarts
        if self.config["minecraft"]["restarts"]["auto_restart"]:
            restart_interval = self.config["minecraft"]["restarts"]["restart_interval"]
            self.logger.info(
                f"Automatic server restarts enabled. Restart interval: {restart_interval} hours"
            )

            # Get the alert intervals from the configuration
            alert_intervals = self.config["minecraft"]["restarts"]["alert_intervals"]

            # Queue the restart reminders based on the alert intervals
            for interval in alert_intervals:
                if interval < restart_interval * 3600:
                    self.loop.call_later(
                        restart_interval * 3600 - interval,
                        self.loop.create_task,
                        self.send_restart_reminder(interval),
                    )

            # Queue the server restart after the specified interval
            self.loop.call_later(
                restart_interval * 3600, self.loop.create_task, self.restart_server()
            )

        return True

    async def add_sse_event(self, sse_event_class: SSEEvent, data: dict):
        """Creates an object of an Server Sent Event to be broadcast to any listeners"""
        timestamp = datetime.now().isoformat()
        data["timestamp"] = timestamp
        for user in self.sse_queue.keys():
            self.sse_queue[user].append(sse_event_class(data))

    async def register_sse_user(self, user: str):
        # Creates an entry in the SSE queue for the user to consume events from
        self.sse_queue[user] = []
        # Add the user attach event for this new user
        self.add_sse_event(
            UserAttach, {"message": "{user} attached to the console", "username": user}
        )

    async def unregister_sse_user(self, user: str):
        # Remove user from the SSE queue
        self.sse_queue.pop(user, None)
        # Add the user attach event for this new user
        self.add_sse_event(
            UserDetach,
            {"message": "{user} detached from the console", "username": user},
        )

    async def restart_server(self):
        await self.add_sse_event(
            ServerRestarting, {"message": f"{self.server_name} is being restarted."}
        )
        self.restarting = True
        if not self.running:
            self.logger.info(
                "Server is not currently running. Starting the server instead."
            )
            await self.start_server()
            return
        self.logger.info("Restarting the server...")
        # Send the 'stop' command to the server input
        await self.server_input("stop")
        # Wait for the server to stop
        while self.running:
            await asyncio.sleep(1)
        self.logger.info("Server stopped. Starting the server again...")
        # Start the server again
        await self.start_server()
        self.logger.info("Server restarted successfully.")
        self.restarting = False

    async def build_java_command(self) -> list:
        """Builds a java command from the config"""
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
        jar_path = find_jar(os.path.join(self.server_path, mc_config["server_jar"]))
        if jar_path is None:
            raise FileNotFoundError(
                f"Unable to find a minecraft jar in the server directory using the pattern: {mc_config["server_jar"]}"
            )
        java_cmd.append(jar_path)

        # No GUI
        java_cmd.append("nogui")

        return java_cmd

    def get_server_path(self) -> str:
        return self.server_path

    async def server_input(self, data: str) -> tuple[bool, str]:
        if self.protocol:
            self.logger.info(f"Sending input to server STDIN: {data}")
            future = self.loop.create_future()
            self.protocol.register_console_consumer(future)
            await self.protocol.write_process(data)
            await future
            line = future.result()
            await self.add_sse_event(ServerInput, {"message": data, "result": line})
            return ("unknown command" not in line.lower(), line)

        return (False, "Server protocol is not present... has the server been started?")

    async def proc_closed(self, exit_code: Union[int, None]):
        self.logger.info(f"Server Process closed with exit code: {exit_code}")
        self.running = False

        # 3221225786 is because for some odd reason, I think ctrl+c gets forwarded
        # to the minecraft server when done from the API console when it shouldn't
        if exit_code not in (0, 3221225786):
            self.logger.warning(
                "Server exited with a non-zero exit code. It may have crashed, restarting the server..."
            )
            await self.restart_server()
        else:
            self.logger.info("Server exited normally.")

        await self.server_analytics.log_player_count(0, [])
        await self.player_analytics.server_stopping()
        # Run exit future if it exists and server isn't restarting or running
        if self.exit_future is not None and not self.restarting and not self.running:
            await self.add_sse_event(
                ServerStopped,
                {
                    "message": f"{self.server_name} has stopped with exit code: {exit_code}"
                },
            )
            await self.exit_future(self.server_name, exit_code)

    async def send_restart_reminder(self, interval: int):
        time_to_restart = generate_time_message(interval)
        msg = f"say WARNING: PLANNED SERVER RESTART IN {time_to_restart}"
        await self.server_input(msg)

    async def reload_config(self):
        await self.config.reload()

        # Get the regular expression patterns from the configuration
        self.connect_pattern = re.compile(
            self.config["minecraft"]["console"]["player_connected"]
        )
        self.disconnect_pattern = re.compile(
            self.config["minecraft"]["console"]["player_disconnected"]
        )
        self.chat_pattern = re.compile(
            self.config["minecraft"]["console"]["player_chat"]
        )

    async def console_output(self, output: str):
        """Callback used to handle output from the server console"""
        self.logger.info(output)
        # Check for chat messages
        chat_match = self.chat_pattern.search(output)
        if chat_match:
            username = chat_match.group("username")
            message = chat_match.group("message")
            self.chat_history.append((username, message))
            await self.add_sse_event(
                PlayerChat, {"message": message, "username": username}
            )

        # Check for player connection
        connect_match = self.connect_pattern.search(output)
        if connect_match and not chat_match:
            username = connect_match.group("username")
            ip = connect_match.group("ip")
            self.logger.info(f"Player connected: {username} ({ip})")
            self.connected_players.append(username)
            await self.server_analytics.log_player_count(
                len(self.connected_players), self.connected_players
            )
            await self.player_analytics.on_player_connect(
                username, self.server_name, ip
            )
            await self.add_sse_event(PlayerList, {"players": self.connected_players})

        # Check for player disconnection
        disconnect_match = self.disconnect_pattern.search(output)
        if disconnect_match and not chat_match:
            username = disconnect_match.group("username")
            reason = disconnect_match.group("reason")
            self.logger.info(f"{username} lost connection: {reason}")
            if username in self.connected_players:
                self.connected_players.remove(username)
            await self.server_analytics.log_player_count(
                len(self.connected_players), self.connected_players
            )
            await self.player_analytics.on_player_disconnect(username)
            await self.add_sse_event(PlayerList, {"players": self.connected_players})


class ProcessProtocol(SubprocessProtocol):
    """Process Protocol that handles server process I/O"""

    def __init__(self, server_name: str, exit_future: typing.Coroutine):
        self.exit_future = exit_future
        self.server_name = server_name
        self.logger = get_logger(server_name)
        self.loop = asyncio.get_event_loop()
        self.scrollback_buffer = LimitedList(maxlen=1000)
        self._consumers: list[typing.Coroutine] = []
        self._temp_consumers: list[asyncio.Future] = []

    def connection_made(self, transport: transports.SubprocessTransport):
        self.logger.debug("Connection with minecraft server process established")
        self.transport = transport

        self.stdin = self.transport.get_pipe_transport(0)
        self.stdout = self.transport.get_pipe_transport(1)
        self.stderr = self.transport.get_pipe_transport(2)
        self.logger.debug("Saved references to STDIN/OUT/ERR")

    def pipe_data_received(self, fd: int, data: bytes):
        # Decode the data from the process and store it
        message = data.decode().strip()
        timestamp = datetime.now().isoformat()
        self.scrollback_buffer.append((message, timestamp))

        # stdout/stderr only
        if fd in (1, 2):
            # Forward console output to all consumers
            for consumer in self._consumers:
                self.loop.create_task(consumer(message))

            # Temporary consumers, get removed after one usage.
            for i in range(len(self._temp_consumers)):
                consumer = self._temp_consumers.pop()
                consumer.set_result(message)

    def process_exited(self):
        # Called when the java process exits
        code = self.transport.get_returncode()
        self.logger.debug(f"Minecraft Server Process Exited with code: {code}")
        self.loop.create_task(self.exit_future(code))

    async def write_process(self, data: typing.Union[bytes, str]):
        # Write data to the process STDIN
        if isinstance(data, str):
            data = data.encode()
        self.stdin.write(data + b"\n")

    def register_console_consumer(
        self, callback: Union[typing.Coroutine, asyncio.Future]
    ):
        """
        Registers a console consumer coroutine or future.

        Args:
            callback (Coroutine, Future): A coroutine or future that handles output from the console.

        Raises:
            ValueError: If `callback` is not a coroutine or a future.
        """
        if asyncio.iscoroutinefunction(callback):
            # If the callback is a coroutine, add it as a permanent consumer
            self._consumers.append(callback)
        elif asyncio.isfuture(callback):
            # If the callback is a future, add it as a temporary consumer
            self._temp_consumers.append(callback)
        else:
            raise ValueError("Callback must be a coroutine or a future!")

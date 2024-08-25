from enum import Enum
from functools import lru_cache
from fastapi import WebSocket
from pydantic import BaseModel
from typing import Callable, Dict
from mud.game.areas import Room1, Room2, get_direction

from mud.server.players import Player


class PlayerDisconnected(Exception):
    def __init__(self, session: WebSocket):
        super().__init__(self)
        self.session = session


class ConnState(str, Enum):
    CHOOSING_NAME = "name"
    GAME = "game"


class Connection(BaseModel):
    """represents the state of a connection.
    e.g. a connection may be choosing a name, or playing the game.
    """

    player: Player | None = None
    state: ConnState = ConnState.CHOOSING_NAME


class Mud:
    """the core MUD game service"""

    def __init__(self, connection_manager) -> None:
        self.manager = connection_manager
        self.players: Dict[str, Player] = {}
        self.connections: Dict[WebSocket, Connection] = {}

        # hardcoded list of rooms for now
        self.rooms = [Room1, Room2]

    async def add_player(self, name, session, conn) -> None:
        """add a player to the game, with a handle to their session"""
        player = Player(
            name=name, session=session, send_text=self.send_text_fn(session)
        )
        self.players[player.name] = player
        await player.send_text(f"Joining game as {player.name}")
        conn.player = player
        conn.state = ConnState.GAME

        # put player in the start zone
        await Room1.enter(player)

    async def new_player_prompt(self, session: WebSocket) -> None:
        """prompt a new player for a name"""
        await self.manager.send_text(session, "What is your name? ")

    async def connect(self, session: WebSocket) -> None:
        """handle a new connection"""
        self.connections[session] = Connection()
        await self.new_player_prompt(session)

    def disconnect(self, session: WebSocket) -> None:
        """handle a player disconnect"""
        if session in self.connections:
            self.connections.pop(session)

    async def handler(self, session: WebSocket, text: str) -> None:
        """handle incoming commands"""
        conn = self.connections[session]

        if conn.state == ConnState.CHOOSING_NAME:
            await self.add_player(text, session, conn)
            return

        player = conn.player
        assert player is not None

        match text.split():
            # Chat commands
            case ["say"]:
                await player.send_text("Say what?")
                return

            case ["s" | "say", *rest] if len(rest) > 0:
                text = " ".join(rest)
                await self.broadcast(f"{player.name} says {text}")
                return

            case ["w" | "t" | "whisp" | "whisper" | "tell", target, *rest] if len(
                rest
            ) > 0:
                text = " ".join(rest)
                target_player = self.players.get(target, None)

                if target_player is not None:
                    await target_player.send_text(f"{player.name} whispers: {text}")
                    await player.send_text(f"You whisper to {target}: {text}")
                    return
                else:
                    await player.send_text(f"No player named {target} online.")
                    return

            # List players
            case ["list"]:
                players = self.players.keys()
                await player.send_text(
                    "\nAdventurers\n-----------\n" + "\n".join(players)
                )
                return

            # Look at current room
            case ["l" | "look"]:
                if player.room is not None:
                    await player.send_text(player.room.format_room())
                    return

                await player.send_text("It's dark here.")

            # Movement
            case [("n" | "north" | "e" | "east" | "s" | "south" | "w" | "west") as dir]:
                await player.move(get_direction(dir))
                return

            case ["k" | "kill" | "attack", *rest]:
                target = " ".join(rest)
                await player.start_combat(target)

    async def update(self):
        for room in self.rooms:
            await room.update()

    async def broadcast(self, text: str) -> None:
        await self.manager.broadcast(text)

    def send_text_fn(self, session: WebSocket) -> Callable:
        """creates a function that can be used to send text to a session.
        Used to initialize players with a simple method to send text to their client."""

        async def fn(text: str):
            await self.manager.send_text(session, text)

        return fn


@lru_cache(maxsize=1)
def get_mud(connection_manager) -> Mud:
    return Mud(connection_manager)

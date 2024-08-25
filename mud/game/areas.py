from __future__ import annotations
import logging
import random
import asyncio
from textwrap import dedent
from enum import Enum
from typing import Dict, List
from uuid import UUID, uuid4
from pydantic import BaseModel
from mud.game.mobs import Mob, mob1

from mud.server.players import Player

logger = logging.getLogger(__name__)

rooms = {}


class Direction(str, Enum):
    N = "n"
    E = "e"
    S = "s"
    W = "w"

    def text(self):
        match self:
            case Direction.N:
                return "north"
            case Direction.E:
                return "east"
            case Direction.S:
                return "south"
            case Direction.W:
                return "west"


def get_direction(text: str) -> Direction:
    return Direction(text[0:1])


class SpawnedMobs(BaseModel):
    """a class to track mobs that should spawn in a room"""

    mob: Mob
    desired: int
    current: int = 0

    class Config:
        arbitrary_types_allowed = True


class Room(BaseModel):
    """a room in the game"""

    id: int
    title: str
    desc: str

    _lock: asyncio.Lock = asyncio.Lock()
    players: Dict[str, Player] = {}

    exits: Dict[Direction, int] = {}

    spawns: List[SpawnedMobs] = []
    spawn_cooldown: int = 10  # ticks
    spawn_lock: int = 0  # actual cooldown - value is ticks until we can spawn again

    mobs: Dict[UUID, Mob] = {}

    async def broadcast(self, text: str):
        """send some text to all players present in the room"""
        for player in self.players.values():
            await player.send_text(text)

    async def enter(self, player: Player):
        """add a player to the room"""
        async with self._lock:
            await self.broadcast(f"{player.name} enters.")
            self.players[player.name] = player

        # set a handle to the room on the player
        player.set_room(self)
        await player.send_text(self.format_room())

    async def leave(self, player: Player, dir: Direction):
        """have a player leave the room, and add them to the room located
        at the exit `dir`"""
        # check to make sure an exit exists in the chosen direction
        if dir not in self.exits:
            await player.send_text(
                f"You cannot go that way. Exits: {self.format_exits()}"
            )
            return

        async with self._lock:
            self.players.pop(player.name)

        # get handle to the next room, and have the player enter
        next_room = rooms[self.exits[dir]]
        await next_room.enter(player)
        await self.broadcast(f"{player.name} leaves.")

    async def add_mob(self, mob: Mob):
        """add a mob to the room, and announce that it has entered."""
        async with self._lock:
            self.mobs[mob.id] = mob
        mob.set_room(self)
        await self.broadcast(mob.format_enter_text())

    async def move_mob(self, mob: Mob, dir: Direction):
        """move a mob in the direction `dir`."""
        next_room = rooms[self.exits[dir]]
        async with self._lock:
            self.mobs.pop(mob.id)
        await next_room.add_mob(mob)

        await self.broadcast(f"{mob.format_leave_text()} {dir.text()}.")

    async def spawn(self):
        """attempt to spawn the mobs defined in self.spawns. Keeps track of
        how many spawned mobs exist, only spawning up to the `desired` limit
        for each entry (unless they die), even if the mob leaves the room."""
        for entry in self.spawns:
            if self.spawn_lock > 0:
                return
            if entry.current < entry.desired:

                def dec():
                    entry.current -= 1

                spawned_mob = entry.mob.copy(update={"id": uuid4(), "on_death": [dec]})
                await self.add_mob(spawned_mob)
                entry.current += 1
                logger.info(f"spawning {entry.mob.name}")
                self.spawn_lock += self.spawn_cooldown

    async def update(self):
        """update the room on a game clock tick"""
        if self.spawn_lock > 0:
            self.spawn_lock -= 1
        await self.spawn()

        for player in list(self.players.values()):
            await player.update()

        for mob in list(self.mobs.values()):
            await mob.update()

    def get_mob(self, target: str) -> Mob:
        for mob in self.mobs.values():
            if target == mob.name:
                return mob
        raise ValueError(f"There's nobody named {target} here.")

    def format_room(self):
        """return a string with a formatted room description, including exits, mobs
        and loot"""
        return dedent(
            f"""
            {self.title}

            {self.desc}

            Exits: {self.format_exits()}

            {self.format_mobs()}
            """
        )

    def format_exits(self):
        return f"[{', '.join(self.exits.keys())}]"

    def format_mobs(self):
        return "\n".join([m.format_present_text() for m in self.mobs.values()])

    def random_exit(self):
        exits = list(self.exits.keys())
        if len(exits) == 0:
            raise ValueError("there are no exits")

        if len(exits) == 1:
            return exits[0]

        return exits[random.randrange(0, len(self.exits))]

    class Config:
        arbitrary_types_allowed = True


# test rooms
Room2 = Room(
    id=2,
    title="A forest trail",
    desc="You are on a trail through a forest. Tall trees tower overhead.",
    exits={Direction.S: 1},
    spawns=[SpawnedMobs(mob=mob1, desired=2)],
)

Room1 = Room(
    id=1,
    title="Forest Clearing",
    desc="A clearing in the forest. A trail leads north.",
    exits={Direction.N: 2},
)


rooms.update({1: Room1, 2: Room2})

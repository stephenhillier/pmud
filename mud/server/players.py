import random
from typing import Any, Callable, Tuple
from fastapi import WebSocket
from pydantic import BaseModel

from mud.game.mobs import Mob
from mud.game.combat import Combat


class Player(BaseModel):
    """a player connected to the MUD game"""

    name: str
    session: WebSocket
    send_text: Callable
    room: Any | None = None

    health: int = 10

    attack_damage: Tuple[int, int] = (4, 6)

    combat: Combat | None = None

    def set_room(self, room):
        self.room = room

    async def move(self, dir):
        assert self.room is not None
        await self.room.leave(self, dir)

    async def die(self):
        if self.combat is not None:
            self.combat.target.in_combat = False

        self.combat = None
        await self.send_text("You die.")
        self.set_room(None)

    async def take_damage(self, damage: int):
        self.health -= damage
        if self.health < 0:
            await self.die()

    async def start_combat(self, target: str):
        if self.room is None:
            return
        try:
            mob = self.room.get_mob(target)
        except ValueError as e:
            await self.send_text(str(e))
        else:
            self.combat = Combat(target=mob)

    async def attack(self, mob: Mob):
        """calculate the damage done by an attack"""
        if self.combat is None:
            return

        dmg_to_mob = random.randrange(*self.attack_damage)
        dmg_to_player = random.randrange(*mob.attack_damage)

        if self.combat.player_initiative:
            await self.send_text(
                f"You attack {self.combat.target.name} for {dmg_to_mob} damage."
            )
            await mob.take_damage(dmg_to_mob)
            await self.send_text(
                f"{self.combat.target.name.capitalize()} attacks you"
                f" for {dmg_to_player} damage."
            )
            await self.take_damage(dmg_to_player)
        else:
            await self.send_text(
                f"{self.combat.target.name.capitalize()} attacks you "
                f"for {dmg_to_player} damage."
            )
            await self.take_damage(dmg_to_player)
            await self.send_text(
                f"You attack {self.combat.target.name} for {dmg_to_mob} damage."
            )
            await mob.take_damage(dmg_to_mob)

    async def update(self) -> None:
        if self.combat is not None:
            await self.attack(self.combat.target)

    class Config:
        arbitrary_types_allowed = True

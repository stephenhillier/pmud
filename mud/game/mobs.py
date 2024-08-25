import random
from typing import Any, Callable, List, Tuple
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class Mob(BaseModel):
    """a mob, or npc"""

    id: UUID = Field(default_factory=uuid4)
    name: str

    level: int

    strength: int
    constitution: int
    dexterity: int
    intelligence: int = 10

    health: int = 10
    attack_damage: Tuple[int, int] = (1, 2)

    move_cooldown: int = 20  # ticks
    move_lock: int = 0  # the actual cooldown counter
    move_chance: float = 0.1  # chance of moving, if eligible
    enter_text: str = "arrives"
    leave_text: str = "leaves"
    present_text: str = "is here"
    room: Any = None
    wanders: bool = False

    in_combat: bool = False

    on_death: List[Callable] = []

    async def die(self):
        """hook that is called when the mob dies.  on_death callbacks will be called."""
        await self.room.broadcast(f"{self.name} dies.")
        for f in self.on_death:
            f()
        self.set_room(None)

    async def take_damage(self, damage: int):
        self.health -= damage
        if self.health < 0:
            await self.die()

    def format_enter_text(self):
        """return a string to display when the mob enters the room"""
        return f"{self.name.capitalize()} {self.enter_text}."

    def format_leave_text(self):
        """return a string to display when the mob leaves a room."""
        return f"{self.name.capitalize()} {self.leave_text}"

    def format_present_text(self):
        """return a string that says the mob is here in the room.
        e.g. 'a rat is here'"""
        return f"{self.name.capitalize()} {self.present_text}."

    def set_room(self, room: Any):
        """set the room that the mob is currently in. This only updates
        the room that the mob thinks it is in, so it should not be called without
        also updating the room(s) that the mob is moving to or from."""
        self.room = room

    async def update(self):
        """perform actions that should happen on game ticks"""

        # if the mob is not placed in the game, skip updating it.
        if self.room is None:
            return

        # stop update here if in combat.  Anything below this will not
        # happen until combat ends (including decrementing move cooldowns,
        # to prevent mobs from always instantly leaving when combat ends).
        if self.in_combat:
            return

        # check if mob can move or if it needs to wait
        # move_chance is used to provide some randomness to mob
        # movements. If the move_chance check fails, the mob will
        # have another chance next tick.
        if self.move_lock > 0:
            self.move_lock -= 1
        elif (
            self.wanders
            and len(self.room.exits) > 0
            and random.random() <= self.move_chance
        ):
            # add the move cooldown
            self.move_lock += self.move_cooldown
            await self.room.move_mob(self, self.room.random_exit())


mob1 = Mob(
    name="a rat",
    level=1,
    wanders=True,
    strength=1,
    constitution=1,
    dexterity=2,
    intelligence=1,
    enter_text="crawls out from behind some rubble",
    leave_text="scurries",
)

from pydantic import BaseModel
from mud.game.mobs import Mob


class Combat(BaseModel):
    """represents an instance of combat between a player and an npc.
    the instance lasts until one party flees or dies."""

    target: Mob
    player_initiative: bool = True

    def turn(self):
        """runs a single turn of combat"""
        pass

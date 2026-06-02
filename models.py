from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Node:
    name: str
    path: Path
    is_entity: bool 
    level: int
    is_open: bool = False
    icon_path: Path = None
    stat_path: Path = None
    action_type: str = ""  
    children: list = field(default_factory=list)
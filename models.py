# models.py

""" 
Description:
Basic data models for representing transistors and their terminal placements in the gate matrix layout.
This module defines the Transistor class and a utility function to calculate terminal column positions based on gate
center and orientation. These models are foundational for the layout optimization process, enabling consistent handling 
of device attributes and terminal placements across the pipeline.
"""

class Transistor:
    """Represents a physical transistor device in a Gate Matrix Layout."""
    def __init__(self, name: str, drain: str, gate: str, source: str, device_type: str):
        self.name = name.upper()
        self.drain = drain.upper()
        self.gate = gate.upper()
        self.source = source.upper()
        self.device_type = device_type.upper()  # 'N' (NMOS) or 'P' (PMOS)

def calculate_terminal_columns(gate_center: int, is_flipped: bool) -> dict:
    """
    Computes the exact matrix columns occupied by Source (S), Gate (G), and Drain (D).
    Standard orientation: Source is Left (center - 1), Drain is Right (center + 1).
    Flipped orientation: Source is Right (center + 1), Drain is Left (center - 1).
    """
    if is_flipped:
        return {"S": gate_center + 1, "G": gate_center, "D": gate_center - 1}
    return {"S": gate_center - 1, "G": gate_center, "D": gate_center + 1}
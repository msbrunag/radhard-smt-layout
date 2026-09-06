# spice_parser.py
import re
from models import Transistor

"""
Description:
This module provides functionality to parse SPICE netlist files and extract transistor information.
The 'parse_spice_netlist' function reads a given SPICE netlist file, identifies NMOS and PMOS transistor 
instances using regular expressions, and collects all unique nets associated with these devices. 
The extracted data is returned as lists of Transistor objects for NMOS and PMOS devices, along with 
a list of unique nets. 
"""

def parse_spice_netlist(file_path: str) -> tuple[list[Transistor], list[Transistor], list[str]]:
    """
    Parses a SPICE netlist (.sp / .txt) to extract NMOS and PMOS devices and all unique nets.
    Uses regex to gracefully handle arbitrary whitespace, comments, and device parameters (W, L, etc.).
    """
    nmos_devices = []
    pmos_devices = []
    discovered_nets = set()
    
    # Regex pattern to match standard SPICE transistor cards: Mname Drain Gate Source Bulk Type
    instance_pattern = re.compile(r'^(m\w+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(\w+)', re.IGNORECASE)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as netlist_file:
        for line in netlist_file:
            line = line.strip() 
            match = instance_pattern.match(line) 
            if match:
                name, drain, gate, source, _, device_type = match.groups() 
                
                # Normalize type definition 
                cleaned_type = 'N' if 'N' in device_type.upper() else 'P' 
                device = Transistor(name, drain, gate, source, cleaned_type)
                
                if device.device_type == 'N':
                    nmos_devices.append(device)
                else:
                    pmos_devices.append(device)
                
                # Collects unique nets from the drain and source terminals of each device
                discovered_nets.update([device.drain, device.source]) 
                
                # Optional: Remove or uncomment these print statements for silent execution
                # print(f"Discovered nets: {device.drain}, {device.source} from device {device.name} ({device.device_type})\n")
                # print(f"Current unique nets: {discovered_nets}\n")

    return nmos_devices, pmos_devices, list(discovered_nets)
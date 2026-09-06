from typing import Optional

def calculate_minimum_achieved_distance(solution: dict, all_devices: list, net_a: str, net_b: str) -> Optional[int]:
    """
    Calculates the actual minimum physical distance observed between net_a and net_b in the generated layout.
    """
    if not solution or not net_a or not net_b:
        return None
    
    net_a_upper, net_b_upper = net_a.upper(), net_b.upper()
    placements = solution['placements']
    
    devs_a = [d for d in all_devices if net_a_upper in (d.source, d.drain)]
    devs_b = [d for d in all_devices if net_b_upper in (d.source, d.drain)]
    
    min_dist = float('inf')
    
    for da in devs_a:
        if da.name not in placements: continue
        p_a = placements[da.name]
        
        # Physical position of the terminal of interest in da
        # Logic: Source + Flipped -> +1, Source + Unflipped -> -1
        is_source_a = (da.source == net_a_upper)
        offset_a = 1 if is_source_a == p_a['is_flipped'] else -1
        col_a = p_a['gate_column'] + offset_a
        
        for db in devs_b:
            if db.name not in placements or da.name == db.name: continue
            
            # Must be on the same diffusion layer (N with N, P with P)
            if da.device_type != db.device_type: continue 
            
            p_b = placements[db.name]
            is_source_b = (db.source == net_b_upper)
            offset_b = 1 if is_source_b == p_b['is_flipped'] else -1
            col_b = p_b['gate_column'] + offset_b
            
            dist = abs(col_a - col_b)
            if dist < min_dist:
                min_dist = dist
                
    return int(min_dist) if min_dist != float('inf') else None


def extract_solution_with_metadata(smt_model, all_devices: list, gate_positions: dict, flip_states: dict, cell_width: int, optimality_proven: bool, spacing_constraints: list) -> dict:
    """
    Reads the solved SMT model, extracts positions and flip states, 
    and injects optimality metrics and achieved effective distances.
    """
    solution = {
        'cell_width': cell_width, 
        'optimality_proven': optimality_proven,
        'achieved_distance': None,
        'placements': {}
    }
    
    for device in all_devices:
        solution['placements'][device.name] = {
            'gate_column': smt_model[gate_positions[device.name]].as_long(),
            'is_flipped': bool(smt_model[flip_states[device.name]]),
            'device': device
        }
        
    # If there are spacing constraints (RHBD), calculate the actual achieved distance
    if spacing_constraints:
        # Assumes the first spacing constraint is the main one for reporting purposes
        net_a, net_b, _ = spacing_constraints[0]
        solution['achieved_distance'] = calculate_minimum_achieved_distance(solution, all_devices, net_a, net_b)
        
    return solution
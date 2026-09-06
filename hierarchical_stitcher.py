# hierarchical_stitcher.py
from solver_core import optimize_flat_layout
from models import Transistor

def get_node_column_absolute(placement: dict, device: Transistor, target_net: str) -> int:
    """Calculates the exact physical column of a specific node based on its final placement."""
    gate = placement['gate_column']
    is_flipped = placement['is_flipped']
    if device.source == target_net:
        return gate + 1 if is_flipped else gate - 1
    elif device.drain == target_net:
        return gate - 1 if is_flipped else gate + 1
    return gate

def optimize_hierarchical_layout(nmos_devices: list[Transistor], pmos_devices: list[Transistor], net_list: list[str], spacing_constraints: list = None, max_block_size: int = 14) -> dict:
    """
    Executes structural partitioning and intelligent stitching.
    Implements boundary compaction with net compatibility verification.
    """
    print(f"\n-> [Hierarchical Routing] Hierarchical Optimization Activated.")

    #LOCAL_TIMEOUT_SEC = 300.0  # Local timeout for each block optimization (3 minutes)
    constraints = spacing_constraints or []
    
    # 1. Logical grouping by Gate
    gate_groups = {}
    for d in nmos_devices + pmos_devices:
        if d.gate not in gate_groups: gate_groups[d.gate] = []
        gate_groups[d.gate].append(d)
    
    blocks = []
    current_block = []
    current_size = 0
    
    for gate, devices in gate_groups.items():
        if current_size + len(devices) > max_block_size and current_block:
            blocks.append(current_block)
            current_block = []
            current_size = 0
        current_block.extend(devices)
        current_size += len(devices)
    if current_block: blocks.append(current_block)

    print(f"-> [Hierarchical Routing] Partitioned into {len(blocks)} blocks.")
    
    aggregated_result = {'placements': {}, 'cell_width': 0}
    prev_block_placements = None

    # 2. Sequential Processing and Stitching
    for block_devices in blocks:  
        b_nmos = [d for d in block_devices if d.device_type == 'N']
        b_pmos = [d for d in block_devices if d.device_type == 'P']

        local_nets = set()
        for d in block_devices:
            local_nets.update([d.source, d.drain])

        local_constraints = [
            (na, nb, pitch) for na, nb, pitch in constraints 
            if na in local_nets and nb in local_nets
        ]
        
        block_result = optimize_flat_layout(b_nmos, b_pmos, net_list, local_constraints)
        if not block_result: return None
        local_placements = block_result['placements']

        offset_shift = 0

        if prev_block_placements:
            max_col_prev = max([p['gate_column'] for p in prev_block_placements.values()])
            min_col_curr = min([p['gate_column'] for p in local_placements.values()])


            # --- BOUNDARY COMPATIBILITY LOGIC ---
            can_share_diffusion = {'N': None, 'P': None}
            boundary_nets = {'N': None, 'P': None}
            diffusion_breaks = {'N': [], 'P': []}

            for layer in ['N', 'P']:
            
                prev_layer = [
                    p for p in prev_block_placements.values()
                    if p['device'].device_type == layer
                ]

                curr_layer = [
                    p for p in local_placements.values()
                    if p['device'].device_type == layer
                ]

                # If the block has no devices of this type,
                # skip compatibility check
                if not prev_layer or not curr_layer:
                    continue
                
                # NMOS and PMOS boundaries calculated separately
                p_prev = max(prev_layer, key=lambda p: p['gate_column'])
                p_curr = min(curr_layer, key=lambda p: p['gate_column'])

                d_prev = p_prev['device']
                d_curr = p_curr['device']

                # Diffusion node facing right in the previous block
                net_prev = (
                    d_prev.source
                    if p_prev['is_flipped']
                    else d_prev.drain
                )

                # Difussion node facing left in the current block
                net_curr = (
                    d_curr.drain
                    if p_curr['is_flipped']
                    else d_curr.source
                )

                boundary_nets[layer] = (net_prev, net_curr)
                can_share_diffusion[layer] = (net_prev == net_curr)

                if not can_share_diffusion[layer]:
                    diffusion_breaks[layer].append((net_prev, net_curr))

            # If any existing layer has incompatible nets,
            # a diffusion break is required.
            needs_diffusion_break = any(
                can_share_diffusion[layer] is False
                for layer in ['N', 'P']
            )

            base_distance = 4 if needs_diffusion_break else 2

            offset_shift = (
                max_col_prev + base_distance
            ) - min_col_curr    

            # --- RADIATION SPACING ADJUSTMENT (RHBD) ---
            
            for net_a, net_b, min_pitch in constraints:

                for p_global in aggregated_result['placements'].values():
                    d_global = p_global['device']
            
                    for p_curr in local_placements.values():
                        d_curr = p_curr['device']
            
                        # net_a in previous block and net_b in current block
                        if (
                            net_a in (d_global.source, d_global.drain)
                            and net_b in (d_curr.source, d_curr.drain)
                            and d_global.device_type == d_curr.device_type
                        ):
                            col_a = get_node_column_absolute(
                                p_global, d_global, net_a
                            )
            
                            col_b_rel = get_node_column_absolute(
                                p_curr, d_curr, net_b
                            )
            
                            required = (col_a + min_pitch) - col_b_rel
                            offset_shift = max(offset_shift, required)
            
                        # net_b in previous block and net_a in current block
                        elif (
                            net_b in (d_global.source, d_global.drain)
                            and net_a in (d_curr.source, d_curr.drain)
                            and d_global.device_type == d_curr.device_type
                        ):
                            col_b = get_node_column_absolute(
                                p_global, d_global, net_b
                            )
            
                            col_a_rel = get_node_column_absolute(
                                p_curr, d_curr, net_a
                            )
            
                            required = (col_b + min_pitch) - col_a_rel
                            offset_shift = max(offset_shift, required)

        # Apply the final calculated shift to local placements
        shifted_local_placements = {}
        for name, placement in local_placements.items():
            shifted_placement = placement.copy()
            shifted_placement['gate_column'] += offset_shift
            aggregated_result['placements'][name] = shifted_placement
            shifted_local_placements[name] = shifted_placement
        
        prev_block_placements = shifted_local_placements

    aggregated_result['cell_width'] = max([p['gate_column'] for p in aggregated_result['placements'].values()]) + 2
    return aggregated_result
# solver_core.py
# The mathematical SMT engine utilizing Z3 for local flat layout optimization

import time
from z3 import Solver, Optimize, Int, Bool, If, Sum, sat, unsat
from models import Transistor
from extract_solution_with_metadata import extract_solution_with_metadata
import layout_constraints as lc

def estimate_minimum_width(nmos_devices: list[Transistor], pmos_devices: list[Transistor]) -> int:
    """Calculates the theoretical minimum column count based on diffusion sharing."""
    estimated_widths = {}
    for layer_type, devices in [('N', nmos_devices), ('P', pmos_devices)]:
        count = len(devices)
        if count == 0:
            return 0
        unique_diffusion_nets = {d.source for d in devices} | {d.drain for d in devices}
        base_width = (2 * count) + 1
        diffusion_breaks = max(0, len(unique_diffusion_nets) - (count + 1))
        estimated_widths[layer_type] = base_width + (diffusion_breaks * 2)
    return max(estimated_widths.get('N', 0), estimated_widths.get('P', 0))

def optimize_flat_layout(nmos_devices: list[Transistor], pmos_devices: list[Transistor], net_list: list[str], spacing_constraints: list = None, global_timeout_sec: float = 90.0, use_optimize=False) -> dict:
    """
    Performs exact physical synthesis using Z3.
    Gate placement remains shared between PMOS and NMOS so that CMOS gates are
    vertically aligned. Diffusion connectivity is modeled independently for each layer.
    """
            
    all_devices = nmos_devices + pmos_devices
    shared_gates = {d.gate for d in nmos_devices}.intersection({d.gate for d in pmos_devices})

    min_theoretical_width = estimate_minimum_width(nmos_devices, pmos_devices)
    max_required_pitch = max([pitch for _, _, pitch in spacing_constraints]) if spacing_constraints else 0
    min_width = max(min_theoretical_width, max_required_pitch + 1)
    
    solver = Solver()
    gate_positions = {d.name: Int(f'pos_{d.name}') for d in all_devices}
    flip_states = {d.name: Bool(f'flip_{d.name}') for d in all_devices}
    
    # Apply modular constraints
    lc.apply_boundary_constraints(solver, gate_positions, all_devices)
    
    sharing_conditions, chain_conditions, routing_affinity_conditions = lc.apply_pitch_and_abutment_constraints(
        solver, gate_positions, flip_states, nmos_devices, pmos_devices
    )
    
    lc.apply_vertical_alignment_constraints(
        solver, gate_positions, shared_gates, nmos_devices, pmos_devices
    )
    
    tracking_vars = lc.apply_rhbd_spacing_constraints(
        solver, gate_positions, flip_states, all_devices, spacing_constraints
    )

    diffusion_breaks = lc.setup_diffusion_break_trackers(
        solver, gate_positions, nmos_devices, pmos_devices
    )

    # =========================================================================
    # STAGE 1 - FIND MINIMUM WIDTH (INCREMENTAL UNBOUNDED SEARCH)
    # =========================================================================
    best_model = None
    best_width = None
    optimality_proven = False
    all_previous_unsat = True
    
    LOCAL_TIMEOUT_MS = 30000  # 30 seconds per Z3 call

    start_time = time.perf_counter()
    
    current_width_target = min_width
    
    print(
        f"      [Z3] Starting incremental search "
        f"from Width {min_width} (unbounded)..."
    )
    
    while True:
    
        elapsed_global = time.perf_counter() - start_time
        remaining_global = global_timeout_sec - elapsed_global
    
        if remaining_global <= 0:
            print(
                f"      [Z3] Global timeout reached "
                f"({global_timeout_sec:.0f}s)."
            )
            break
        
        solver.push()
    
        for device in all_devices:
            solver.add(
                gate_positions[device.name]
                <= current_width_target - 2
            )
    
        current_timeout_ms = min(
            LOCAL_TIMEOUT_MS,
            max(1, int(remaining_global * 1000))
        )
    
        solver.set("timeout", current_timeout_ms)
    
        attempt_start = time.perf_counter()
    
        if tracking_vars:
            res = solver.check(*tracking_vars)
        else:
            res = solver.check()
    
        attempt_time = time.perf_counter() - attempt_start
    
        print(
            f"[Z3] Width={current_width_target} | "
            f"Result={res} | Time={attempt_time:.2f}s"
        )
    
        if res == sat:
            best_model = solver.model()
            best_width = current_width_target
            optimality_proven = all_previous_unsat
            solver.pop()
            break
        
        elif res == unsat:
            print(
                f"      [Z3] Width {current_width_target}: UNSAT"
            )
            solver.pop()
            current_width_target += 1
    
        else:
            print(
                f"      [Z3] Width {current_width_target}: UNKNOWN "
                f"({solver.reason_unknown()})"
            )
    
            all_previous_unsat = False
            solver.pop()
            current_width_target += 1
    
        if best_model is None:
            print("      [Z3 Error] Failed to generate layout solution before global timeout.")
            return None
    
        print(f"[DEBUG] Width found by Stage 1: {best_width}")

    if use_optimize:
        # =========================================================================
        # STAGE 2 - OPTIMIZE TOPOLOGY WITHIN MINIMUM WIDTH (OPTIONAL)
        # =========================================================================
        compactor = Optimize()
        compactor.set("timeout", min(LOCAL_TIMEOUT_MS, max(1, int(remaining_global * 1000))))
        compactor.add(solver.assertions())
        
        for tv in tracking_vars:
            compactor.add(tv)
    
        for device in all_devices:
            compactor.add(gate_positions[device.name] <= best_width - 2) # limit the width of each device
    
        # Objective Function: Maximize actual diffusion sharing
        sharing_rewards = [If(condition, 1.5, 0) for condition in sharing_conditions] # reward 1 for each diffusion sharing condition satisfied
        chain_rewards = [If(condition, 1, 0) for condition in chain_conditions] # reward 1 for each chain condition satisfied
        
        compactor.maximize(Sum(sharing_rewards))
        compactor.maximize(Sum(chain_rewards))
    
        if compactor.check() == sat:
            best_model = compactor.model()
    
        solution = extract_solution_with_metadata(
            best_model, all_devices, gate_positions, flip_states, 
            best_width, optimality_proven, spacing_constraints
        )
    
        elapsed_time = time.time() - start_time
        solution["runtime_seconds"] = elapsed_time
    
        print(f"      [Z3] Total runtime: {elapsed_time:.3f} s")
    
    
        # Process the custom diffusion breaks format seamlessly
        solution['diffusion_breaks'] = {'P': [], 'N': []}
        for layer_type in ('P', 'N'):
            for item in diffusion_breaks[layer_type]:
                # Evaluates the Z3 Bool variable configured in the constraints
                if bool(best_model[item['var']]):
                    dev_a = item['dev_a']
                    dev_b = item['dev_b']
                    pos_a = best_model[gate_positions[dev_a.name]].as_long()
                    pos_b = best_model[gate_positions[dev_b.name]].as_long()
                    
                    # Column is placed exactly between the two gates
                    solution['diffusion_breaks'][layer_type].append({
                        'between': (dev_a.name, dev_b.name),
                        'column': (pos_a + pos_b) // 2,
                    })
    
        #print(f"[DEBUG] Width found by Stage 2: {best_width}")

    else:
        solution = extract_solution_with_metadata(
            best_model, all_devices, gate_positions, flip_states, 
            best_width, optimality_proven, spacing_constraints
        )

    return solution
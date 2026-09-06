# main.py
import os
import sys
import time
import glob
import argparse
from spice_parser import parse_spice_netlist
from solver_core import optimize_flat_layout
from hierarchical_stitcher import optimize_hierarchical_layout
from layout_viewer_pdf import render_terminal_grid, generate_layout_plot

# =========================================================================
# PIPELINE CONFIGURATIONS
# =========================================================================
GLOBAL_TIMEOUT_SEC = 300.0  
HIERARCHICAL_THRESHOLD = 25 

def select_input_file(arg_filepath: str) -> str:
    """
    Provides a terminal user interface to select a SPICE file 
    if not explicitly provided via command line arguments.
    """
    if arg_filepath and os.path.exists(arg_filepath):
        return arg_filepath

    search_paths = glob.glob('circuits/*.txt') + glob.glob('circuits/*.sp')
    
    # Fallback to current directory if no files found in 'circuits/'
    if not search_paths:
        search_paths = glob.glob('*.txt') + glob.glob('*.sp')

    if not search_paths:
        print("[Error] No SPICE files found in './circuits/' or current directory.")
        sys.exit(1)

    print("\n--- Available SPICE Netlists ---")
    for i, path in enumerate(search_paths):
        print(f"[{i + 1}] {path}")
    
    while True:
        try:
            choice = input("\nSelect the circuit number to process (or press Ctrl+C to abort): ")
            index = int(choice) - 1
            if 0 <= index < len(search_paths):
                return search_paths[index]
            else:
                print("[Error] Invalid selection. Try again.")
        except ValueError:
            print("[Error] Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nExecution aborted by user.")
            sys.exit(0)

def configure_radiation_rules() -> list:
    """
    Interactive prompt allowing the user to define Radiation-Hardening by Design (RHBD)
    node-pair separation rules and pitch distances.
    """
    rules = []
    print("\n--- Radiation Hardening Rules (RHBD) ---")
    print("Do you want to add node spacing constraints?")
    print("[1] No constraints (standard synthesis)")
    print("[2] Enter custom node pairs interactively")
    
    choice = input("\nSelect option (default: 1): ").strip()
    if choice != '2':
        return rules

    print("\nEnter node pairs and minimum pitch distance. Type '0' when finished.")

    rule_index = 1

    while True:
        try:
            print(f"\n--- Rule #{rule_index} ---")
            net_a = input("Enter Net A name (e.g., OUT, CLK_BAR, or '0' to stop): ").strip()
            if net_a == '0':
                break
            if not net_a:
                print("[Warning] Net name cannot be empty.")
                continue

            net_b = input("Enter Net B name (e.g., GND, VSS, CLK): ").strip()
            if not net_b:
                print("[Warning] Net name cannot be empty.")
                continue

            pitch_str = input("Enter minimum pitch distance (integer columns, e.g., 4, 6, 10): ").strip()
            min_pitch = int(pitch_str)

            rules.append((net_a, net_b, min_pitch))
            print(f"-> Added Constraint: {net_a.upper()} vs {net_b.upper()} >= {min_pitch} pitch columns.")
            rule_index += 1
            
        except ValueError:
            print("[Error] Pitch distance must be a valid integer. Rule discarded. Try again.")
        except KeyboardInterrupt:
            print("\nConstraint definition finished.")
            break

    return rules

def main():
    parser = argparse.ArgumentParser(description="Automated Rad-Hard EDA Pipeline")
    parser.add_argument("-i", "--input", type=str, help="Path to the SPICE netlist file", default=None)
    args = parser.parse_args()

    # 1. Input file selection via CLI or interactive prompt
    input_file = select_input_file(args.input)

    # 2. Hardening Constraints Definition (Interactive prompt)
    radiation_spacing_rules = configure_radiation_rules()

    print("\n==================================================")
    print("      AUTOMATED RAD-HARD EDA PIPELINE ACTIVE      ")
    print("==================================================")
    execution_start = time.perf_counter()

    # 3. SPICE Extraction
    nmos_devices, pmos_devices, net_list = parse_spice_netlist(input_file)
    total_device_count = len(nmos_devices) + len(pmos_devices)
    
    print(f"-> Selected circuit: {input_file}")
    print(f"-> Netlist extracted: {len(nmos_devices)} NMOS, {len(pmos_devices)} PMOS ({total_device_count} total).")
    
    if radiation_spacing_rules:
        max_pitch_requested = max([pitch for _, _, pitch in radiation_spacing_rules])
        print(f"-> Loaded {len(radiation_spacing_rules)} Rad-Hard rule(s). Maximum pitch requested: {max_pitch_requested} columns.")
    
    # 4. Optimization Routing Engine Selection
    layout_result = None
    
    if total_device_count > HIERARCHICAL_THRESHOLD:
        print(f"-> Device count exceeds flat threshold ({HIERARCHICAL_THRESHOLD}). Using Hierarchical Stitcher.")
        layout_result = optimize_hierarchical_layout(
            nmos_devices, pmos_devices, net_list, 
            spacing_constraints=radiation_spacing_rules
        )
    else:
        print("-> Using Flat Layout SMT Optimizer.")
        layout_result = optimize_flat_layout(
            nmos_devices, pmos_devices, net_list, 
            spacing_constraints=radiation_spacing_rules,
            global_timeout_sec=GLOBAL_TIMEOUT_SEC
        )

    # 5. Display & Verification Output
    if layout_result:
        circuit_name = os.path.splitext(os.path.basename(input_file))[0]
        
        print("\n-> Layout synthesis completed successfully!")
        
        # Render output formats
        render_terminal_grid(layout_result, nmos_devices, pmos_devices)
        generate_layout_plot(layout_result, nmos_devices, pmos_devices, circuit_name)
        
        duration = time.perf_counter() - execution_start
        print(f"\n[Success] Pipeline finished in {duration:.4f} seconds ({duration / 60:.2f} minutes).")
    else:
        print("\n[Error] SMT Solver failed (UNSAT) or timed out.")
        print("-> Consider expanding physical boundaries or easing constraints for the next attempt.")

if __name__ == '__main__':
    main()
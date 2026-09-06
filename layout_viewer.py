# layout_viewer.py
import os
import matplotlib.pyplot as plt
from models import Transistor

def _get_diffusion_break_positions(layout_result: dict, layer_type: str):
    """Return diffusion-break columns for one layer (P or N)."""
    breaks = layout_result.get("diffusion_breaks", {}) or {}
    return {
        item["column"]
        for item in breaks.get(layer_type, [])
        if isinstance(item, dict) and "column" in item
    }

def render_terminal_grid(layout_result: dict, nmos_devices: list[Transistor], pmos_devices: list[Transistor]):
    """Render a readable text representation, including P/N-specific diffusion breaks."""
    columns = layout_result["cell_width"]
    placements = layout_result["placements"]

    display_grid = [["   .   " for _ in range(columns)] for _ in range(2)]

    for row_idx, (layer_type, layer) in enumerate([("P", pmos_devices), ("N", nmos_devices)]):
        column_occupancy = [False] * columns
        grid_data = {}
        break_columns = _get_diffusion_break_positions(layout_result, layer_type)

        for device in layer:
            if device.name not in placements:
                continue

            p_data = placements[device.name]
            center = p_data["gate_column"]
            left, right = ((device.source, device.drain) if not p_data["is_flipped"] else (device.drain, device.source))

            if center - 1 < 0 or center + 1 >= columns:
                continue

            column_occupancy[center - 1] = True
            column_occupancy[center] = True
            column_occupancy[center + 1] = True

            grid_data[center - 1] = left
            grid_data[center] = device.gate
            grid_data[center + 1] = right

        active_columns = [c for c, occupied in enumerate(column_occupancy) if occupied]

        if active_columns:
            for c in range(columns):
                if c in break_columns:
                    display_grid[row_idx][c] = f"{'[BRK]':^7}"
                elif c in grid_data:
                    display_grid[row_idx][c] = f"{grid_data[c]:^7}"
                elif (min(active_columns) <= c <= max(active_columns) and not column_occupancy[c]):
                    display_grid[row_idx][c] = f"{'[GAP]':^7}"

    print(f"\nPHYSICAL SYNTHESIS RESULTS (Total Track Width: {columns})")
    print("-" * (columns * 7))
    print("PMOS: " + "".join(display_grid[0]))
    print("NMOS: " + "".join(display_grid[1]))
    print("-" * (columns * 7))

def generate_layout_plot(layout_result: dict, nmos_devices: list[Transistor], pmos_devices: list[Transistor], circuit_name: str, spacing_constraints: list = None):
    """Draw and save a 2D layout, showing P/N diffusion breaks independently."""
    columns = layout_result["cell_width"]
    placements = layout_result["placements"]

    protected_nets = set()
    rhbd_subtitle = ""

    if spacing_constraints:
        for net_a, net_b, pitch in spacing_constraints:
            protected_nets.add(net_a.upper())
            protected_nets.add(net_b.upper())
            rhbd_subtitle = f"RHBD Protected Nets: [{net_a} <-> {net_b}] (Target Pitch: {pitch})"

    p_breaks = _get_diffusion_break_positions(layout_result, "P")
    n_breaks = _get_diffusion_break_positions(layout_result, "N")

    fig, ax = plt.subplots(figsize=(max(columns * 0.8, 6), 5))
    color_map = {"N": "blue", "P": "red", "G": "green", "GAP": "gray"}

    if rhbd_subtitle:
        ax.set_title(
            f"Physical Layout Synthesis - {circuit_name.upper()} ({columns} Columns)\n{rhbd_subtitle}",
            fontsize=11, fontweight="bold", pad=12, color="darkred",
        )
    else:
        ax.set_title(f"Physical Layout Synthesis - {circuit_name.upper()} ({columns} Columns)", fontsize=12, fontweight="bold", pad=15)

    for layer_type, device_list, y_offset, break_columns in [("P", pmos_devices, 3, p_breaks), ("N", nmos_devices, 1, n_breaks)]:
        occupied_columns = set()
        column_nets = {}  # Dictionary to track which node is in which column

        for device in device_list:
            if device.name not in placements:
                continue

            p_data = placements[device.name]
            gate_col = p_data["gate_column"]
            is_flipped = p_data["is_flipped"]

            occupied_columns.update([gate_col - 1, gate_col, gate_col + 1])

            ax.add_patch(plt.Rectangle((gate_col - 1.1, y_offset + 0.2), 2.2, 0.6, color=color_map[layer_type], alpha=0.2))
            ax.add_patch(plt.Rectangle((gate_col - 0.15, y_offset - 0.5), 0.3, 2.0, color=color_map["G"], alpha=0.6))

            left_net, right_net = ((device.source, device.drain) if not is_flipped else (device.drain, device.source))
            
            # Tracks nodes in the columns adjacent to the gate
            column_nets[gate_col - 1] = left_net
            column_nets[gate_col + 1] = right_net

            def format_net_text(net_name):
                if net_name.upper() in protected_nets:
                    return {
                        "color": "darkred", "fontweight": "bold", "fontsize": 8,
                        "bbox": dict(boxstyle="round,pad=0.15", facecolor="yellow", alpha=0.8, edgecolor="orange"),
                    }
                return {"color": "black", "fontweight": "normal", "fontsize": 7}

            ax.text(gate_col - 0.8, y_offset + 0.4, left_net, ha="center", **format_net_text(left_net))
            ax.text(gate_col + 0.8, y_offset + 0.4, right_net, ha="center", **format_net_text(right_net))
            ax.text(gate_col, y_offset + 1.6, device.gate, ha="center", fontweight="bold", color="darkgreen")
            ax.text(gate_col, y_offset - 0.8, device.name, fontsize=6, ha="center", style="italic")

        # Explicit diffusion breaks
        for break_col in sorted(break_columns):
            ax.add_patch(
                plt.Rectangle(
                    (break_col - 0.12, y_offset + 0.15), 0.24, 0.7,
                    facecolor="white", edgecolor="black", hatch="//", linewidth=1.0, alpha=0.95, zorder=5
                )
            )
            ax.text(break_col, y_offset + 0.5, "B", ha="center", va="center", fontsize=6, fontweight="bold", zorder=6)

        # Conventional empty-column gaps OR Diffusion Bridges
        if occupied_columns:
            start_col = min(occupied_columns)
            end_col = max(occupied_columns)

            for c in range(start_col, end_col + 1):
                if c not in occupied_columns:
                    net_left = column_nets.get(c - 1)
                    net_right = column_nets.get(c + 1)
                    
                    # If there is a 1-column gap but adjacent nodes match, stretch the diffusion to merge them
                    if net_left and net_right and net_left == net_right:
                        ax.add_patch(
                            plt.Rectangle(
                                (c - 0.9, y_offset + 0.2), # Starts exactly at the end of the previous diffusion
                                1.8,                       # Fills the exact gap without overlapping
                                0.6,
                                color=color_map[layer_type], alpha=0.2,
                                edgecolor="none"           # Removes edges for a seamless merge
                            )
                        )
                    else:
                        # GAP logic
                        ax.add_patch(plt.Rectangle((c - 0.4, y_offset + 0.2), 0.8, 0.6, color=color_map["GAP"], alpha=0.6, edgecolor="black", linestyle="--"))
                        ax.text(c, y_offset + 0.5, "GAP", ha="center", va="center", fontsize=5, fontweight="bold")

    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=color_map["P"], alpha=0.2, label="PMOS diffusion"),
        Patch(facecolor=color_map["N"], alpha=0.2, label="NMOS diffusion"),
        Patch(facecolor=color_map["G"], alpha=0.6, label="Gate"),
        Patch(facecolor=color_map["GAP"], alpha=0.6, label="Empty-column gap")
    ]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=2)

    ax.set_xlim(-1, columns)
    ax.set_ylim(-1, 6)
    ax.set_xticks(range(columns))
    ax.set_yticks([])
    ax.grid(True, axis="x", linestyle=":", alpha=0.4)


    os.makedirs("output_results", exist_ok=True)
    output_filename = f"output_results/{circuit_name.lower()}_layout_w{columns}.png"

    plt.tight_layout()
    fig.savefig(output_filename, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Layout plot saved to: {output_filename}")
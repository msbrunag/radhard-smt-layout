# test_runner_v2.py
import os
import csv
import time
import glob
import concurrent.futures

# Import the project modules
from spice_parser import parse_spice_netlist
from solver_core import optimize_flat_layout
from hierarchical_stitcher import optimize_hierarchical_layout
from layout_validator import verify_physical_constraints
from layout_viewer import generate_layout_plot


def _is_same_device_pair(net_x: str, net_y: str, all_devices: list) -> bool:
    """
    Verifica se dois nós correspondem, simultaneamente, aos terminais de fonte
    e dreno de um MESMO transistor físico.

    Essa checagem existe porque, nesse caso, os dois nós não representam
    dispositivos de armazenamento independentes -- são apenas as duas
    extremidades de um único caminho de corrente -- e portanto não fazem
    sentido semântico como par de proteção RHBD. Fisicamente, a distância
    entre eles é fixa (a folga intrínseca do modelo geométrico, 2 colunas)
    e não pode ser alterada por nenhuma restrição de distanciamento imposta
    ao solver, o que levaria a uma violação de DRC espúria e sistemática.
    """
    return any({d.source, d.drain} == {net_x, net_y} for d in all_devices)

def _has_separable_device_pair(net_x: str, net_y: str, all_devices: list) -> bool:
    devices_x = [
        d for d in all_devices
        if net_x in (d.source, d.drain)
    ]

    devices_y = [
        d for d in all_devices
        if net_y in (d.source, d.drain)
    ]

    for dev_x in devices_x:
        for dev_y in devices_y:

            # Não comparar um transistor consigo mesmo
            if dev_x.name == dev_y.name:
                continue

            # A formulação RHBD compara dispositivos da mesma camada
            if dev_x.device_type != dev_y.device_type:
                continue

            return True

    return False

def identify_nodes_for_rhbd(circuit_name, net_list, all_devices):
    """
    Every critical candidate pair is validated against 
    "_has_separable_device_pair" before being returned.
    If the proposed pair corresponds to the terminals of a single transistor,
    the function discards that candidate and tries the next available internal node,
    avoiding the selection of physically inappropriate pairs. 
    """
    name_upper = circuit_name.upper()

    # 1. Remove global power and control nets
    ignore_nets = {'VDD', 'GND', '0', 'VSS', 'VD', 'CLK', 'CLKN', 'CLKP'}

    # 2. Remove typical input nets (gate)
    inputs = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'S', 'D'}
    ignore_nets.update(inputs)

    available_nets = set(net_list) - ignore_nets

    # Sequential cells
    if 'DFF' in name_upper:
        for a, b in [('n_m3', 'MUX_OUT'), ('n_m1', 'SI')]:
            if a in available_nets and b in available_nets and not _has_separable_device_pair(a, b, all_devices):
                return a, b

    if 'LH' in name_upper or 'LL' in name_upper:
        if 'N1' in available_nets and 'N2' in available_nets:
            if not _has_separable_device_pair('N1', 'N2', all_devices):
                return 'N1', 'N2'

    # Combinational cells with multiple stages (AO, OA)
    if 'n_p1' in available_nets and 'OA_OUT' in available_nets:
        if not _has_separable_device_pair('n_p1', 'OA_OUT', all_devices):
            return 'n_p1', 'OA_OUT'
        
    if 'INT' in available_nets and 'OUT' in available_nets:
            if not _has_separable_device_pair('INT', 'OUT', all_devices):
                return 'INT', 'OUT'

    # Simple and complex combinational cells (AOI, OAI)
    if 'Z' in available_nets or 'N1' in available_nets:
        main_out = 'Z' if 'Z' in available_nets else 'N1'
        internal_nets = sorted(n for n in available_nets if n != main_out)
        for candidate in internal_nets:
                    if not _has_separable_device_pair(main_out, candidate, all_devices):
                        return main_out, candidate

    # NAND, OR, NOR
    if 'OUT' in available_nets or 'GND' in available_nets:
        nodes = 'OUT' if 'OUT' in available_nets else 'GND'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate
    
    # AND
    if 'N2' in available_nets or 'Z' in available_nets:
        nodes = 'N2' if 'N2' in available_nets else 'Z'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate

    # HALF ADDER
    if 'N1' in available_nets or 'N6' in available_nets:
        nodes = 'N1' if 'N1' in available_nets else 'N6'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate

    # MUX
    if 'N3' in available_nets or 'Z' in available_nets:
        nodes = 'N3' if 'N3' in available_nets else 'Z'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate

    # FULL ADDER
    if 'N1' in available_nets or 'N5' in available_nets:
        nodes = 'N1' if 'N1' in available_nets else 'N5'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate

    # TMR
    if 'out1' in available_nets or 'out2' in available_nets:
        nodes = 'out1' if 'out1' in available_nets else 'out2'
        internal_nets = sorted(n for n in available_nets if n != nodes)
        for candidate in internal_nets:
            if not _has_separable_device_pair(nodes, candidate, all_devices):
                return nodes, candidate


    valid_fallback = sorted(available_nets)

    for i in range(len(valid_fallback)):
        for j in range(i + 1, len(valid_fallback)):

            net_a = valid_fallback[i]
            net_b = valid_fallback[j]

            if not _has_separable_device_pair(
                net_a, net_b, all_devices
            ):
                return net_a, net_b

    return "N/A", "N/A"

def process_single_circuit(file_path, target_distances):
    """
    Worker function to allow the parallel execution of multiple circuits using ProcessPoolExecutor.
    """
    circuit_results = []
    circuit_name = os.path.basename(file_path).replace(".txt", "")

    nmos, pmos, net_list = parse_spice_netlist(file_path)
    total_tr = len(nmos) + len(pmos)

    if total_tr == 0:
        return circuit_results

    engine_mode = "Hierarchical" if total_tr > 50 else "Flat"

    # Automatic Nodes Selection for RHBD
    all_devices = nmos + pmos
    net_a, net_b = identify_nodes_for_rhbd(circuit_name, net_list, all_devices)

    # =========================================================
    # TEST 1: BASELINE (without RHBD constraints)
    # =========================================================
    start_time = time.perf_counter()
    if engine_mode == "Hierarchical":
        result = optimize_hierarchical_layout(nmos, pmos, net_list, spacing_constraints=None)
    else:
        result = optimize_flat_layout(nmos, pmos, net_list, spacing_constraints=None)
    runtime = time.perf_counter() - start_time

    if result:
        status, width = "SUCCESS", result['cell_width']
        violations = verify_physical_constraints(result, nmos, pmos, spacing_constraints=None)
        v_count = len(violations)
        drc_log = " | ".join(violations) if v_count > 0 else "PASSED"

        # Gera a imagem usando a sua função do layout_viewer.py
        baseline_name = f"{circuit_name}_baseline"
        generate_layout_plot(result, nmos, pmos, baseline_name, spacing_constraints=None)
    else:
        status, width, v_count, drc_log = "UNSAT", "-", 0, "N/A"

    circuit_results.append([circuit_name, total_tr, "None", "None", 0, engine_mode, status, width, f"{runtime:.4f}", v_count, drc_log])

    # =========================================================
    # TEST 2: RAD-HARD (with incremental spacing constraints)
    # =========================================================
    if net_a != "N/A" and net_b != "N/A":
        for dist in target_distances:
            spacing_rules = [(net_a, net_b, dist)]

            start_time = time.perf_counter()
            if engine_mode == "Hierarchical":
                result = optimize_hierarchical_layout(nmos, pmos, net_list, spacing_constraints=spacing_rules)
            else:
                result = optimize_flat_layout(nmos, pmos, net_list, spacing_constraints=spacing_rules)
            runtime = time.perf_counter() - start_time

            if result:
                status, width = "SUCCESS", result['cell_width']
                violations = verify_physical_constraints(result, nmos, pmos, spacing_constraints=spacing_rules)
                v_count = len(violations)
                drc_log = " | ".join(violations) if v_count > 0 else "PASSED"

                # Gera a imagem do layout protegido
                radhard_name = f"{circuit_name}_radhard_d{dist}"
                generate_layout_plot(result, nmos, pmos, radhard_name, spacing_constraints=spacing_rules)
            else:
                status, width, v_count, drc_log = "UNSAT/TIMEOUT", "-", 0, "N/A"

            circuit_results.append([circuit_name, total_tr, net_a, net_b, dist, engine_mode, status, width, f"{runtime:.4f}", v_count, drc_log])

    return circuit_results


def run_automated_benchmark():
    circuit_files = glob.glob(os.path.join("circuits", "*.txt"))
    #circuit_files = [f for f in circuits if os.path.exists(f)]
    if not circuit_files:
        print("Erro: Nenhum arquivo .txt encontrado na pasta 'circuits/'.")
        return

    target_distances = [2, 4, 6, 8, 10]

    output_dir = "results_metrics"
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "benchmark_synthesis_results.csv")

    print("==================================================")
    print(f" INICIANDO EXTRAÇÃO PARALELA DE {len(circuit_files)} CIRCUITOS ")
    print("==================================================")

    with open(csv_path, mode='w', newline='', encoding='utf-8' ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow([
            "Circuit", "Total_Transistors", "Target_Net_A", "Target_Net_B",
            "Required_Distance", "Engine_Mode", "Status", "Cell_Width",
            "Runtime_Seconds", "DRC_Violations_Count", "DRC_Log"
        ])

        csv_file.flush()

        with concurrent.futures.ProcessPoolExecutor() as executor:

            futures = {
                executor.submit(process_single_circuit, fp, target_distances ):
                fp for fp in circuit_files
            }

            for future in concurrent.futures.as_completed(futures):

                try:
                    res = future.result()

                    if res:

                        writer.writerows(res)
                        csv_file.flush()

                        circuit_name = res[0][0]

                        target_a = (
                            res[-1][2]
                            if len(res) > 1
                            else "N/A"
                        )

                        target_b = (
                            res[-1][3]
                            if len(res) > 1
                            else "N/A"
                        )

                        print(
                            f"-> Concluído: {circuit_name} | "
                            f"Testes: {len(res)} | "
                            f"Alvos: {target_a} & {target_b} "
                            f"| CSV salvo"
                        )

                except Exception as exc:
                    print(
                        f"Erro processando um arquivo: {exc}"
                    )

    print(f"\n==================================================")
    print(f" BENCHMARK CONCLUÍDO! Planilha salva em: {csv_path}")
    print(f"==================================================")


if __name__ == "__main__":
    run_automated_benchmark()
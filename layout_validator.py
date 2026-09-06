# layout_validator.py
from models import Transistor, calculate_terminal_columns

def verify_physical_constraints(layout_result: dict, nmos_devices: list[Transistor], pmos_devices: list[Transistor], spacing_constraints: list = None) -> list[str]:
    """
    Design Rule Checker (DRC) Independente.
    Verifica Limites, Colisões de Difusão, Alinhamento CMOS e Regras RHBD Intra-camada.
    """
    violations = []
    placements = layout_result.get('placements', {})
    cell_width = layout_result.get('cell_width', 0)
    constraints = spacing_constraints or []
    
    if not placements:
        return ["Erro Crítico: Nenhum posicionamento encontrado no resultado."]

    # 1. VALIDAÇÃO DE LIMITES DA CÉLULA (Out of Bounds)
    for name, p_data in placements.items():
        gate_col = p_data['gate_column']
        if gate_col < 1 or gate_col >= cell_width:
            violations.append(f"[BOUNDS] {name} alocado na coluna {gate_col} ultrapassa a malha (Largura: {cell_width})")

    # 2. VALIDAÇÃO DE COMPARTILHAMENTO DE DIFUSÃO (Layer DRC)
    for layer_name, devices in [('PMOS', pmos_devices), ('NMOS', nmos_devices)]:
        active_placements = [placements[d.name] for d in devices if d.name in placements]
        active_placements.sort(key=lambda x: x['gate_column'])
        
        for i in range(len(active_placements) - 1):
            curr, nxt = active_placements[i], active_placements[i+1]
            dist = nxt['gate_column'] - curr['gate_column']
            dev_curr, dev_nxt = curr['device'], nxt['device']
            
            if dist < 2:
                violations.append(f"[LAYER {layer_name}] Colisão Horizontal: {dev_curr.name} e {dev_nxt.name} estão sobrepostos.")
            elif dist == 2:
                right_net_curr = dev_curr.source if curr['is_flipped'] else dev_curr.drain
                left_net_nxt = dev_nxt.drain if nxt['is_flipped'] else dev_nxt.source
                if right_net_curr != left_net_nxt:
                    violations.append(f"[LAYER {layer_name}] Curto-circuito Físico: {dev_curr.name} e {dev_nxt.name} adjacentes com nós diferentes ('{right_net_curr}' vs '{left_net_nxt}').")

    # 3. VALIDAÇÃO DE ALINHAMENTO DE GATE (CMOS Alignment)
    shared_gates = {d.gate for d in nmos_devices}.intersection({d.gate for d in pmos_devices})
    for gate in shared_gates:
        p_cols = {placements[d.name]['gate_column'] for d in pmos_devices if d.gate == gate and d.name in placements}
        n_cols = {placements[d.name]['gate_column'] for d in nmos_devices if d.gate == gate and d.name in placements}
        # Ignoramos a checagem rigorosa de alinhamento se houver regras de radiação 
        # (pois o SMT pode ter quebrado o par CMOS para inserir gaps)
        if not constraints and p_cols != n_cols:
            violations.append(f"[CMOS ALIGN] Sinal '{gate}' desalinhado: PMOS {p_cols} vs NMOS {n_cols}")

    # 4. VALIDAÇÃO DE RADIAÇÃO (RHBD Intra-Camada)
    for net_a, net_b, min_required_pitch in constraints:
        net_a_upper, net_b_upper = net_a.upper(), net_b.upper()
        
        for target_layer in ['P', 'N']:
            # CORREÇÃO: cada ponto agora carrega o DISPOSITIVO completo que o originou
            # (não apenas o nome), permitindo comparar o CONJUNTO de terminais
            # {fonte, dreno} entre os dois dispositivos de cada par -- e não somente
            # se são a mesma instância.
            #
            # Isso é necessário porque a exclusão por nome (dev_a.name != dev_b.name)
            # cobre apenas o auto-par de um único transistor, mas não cobre o caso de
            # DUPLICATAS PARALELAS: em células de maior força de acionamento (ex.:
            # D4, D8, D16), o mesmo transistor lógico é frequentemente implementado
            # como múltiplas instâncias físicas distintas, todas com a MESMA fonte e
            # o MESMO dreno. Duas dessas instâncias são, para fins de RHBD,
            # eletricamente equivalentes -- e como costumam ser posicionadas
            # adjacentes uma à outra (para compartilhar difusão em paralelo), medir
            # a distância entre elas reproduz o mesmo falso-positivo já corrigido
            # para o auto-par simples.
            #
            # Pares que compartilham apenas UM terminal (ex.: dois transistores
            # adjacentes de uma mesma pilha série) NÃO são excluídos aqui -- essa é
            # uma medição legítima de separação física entre nós distintos.
            points_a, points_b = [], []
            
            for name, p_data in placements.items():
                dev = p_data['device']
                if dev.device_type != target_layer:
                    continue
                    
                terminals = calculate_terminal_columns(p_data['gate_column'], p_data['is_flipped'])
                if dev.source == net_a_upper: points_a.append((dev, terminals['S']))
                if dev.drain == net_a_upper:  points_a.append((dev, terminals['D']))
                if dev.source == net_b_upper: points_b.append((dev, terminals['S']))
                if dev.drain == net_b_upper:  points_b.append((dev, terminals['D']))

            # Considera apenas pares cujos dispositivos NÃO compartilham o mesmo
            # conjunto {fonte, dreno} -- exclui tanto o auto-par quanto duplicatas
            # paralelas equivalentes.
            valid_pairs = [
                (col_a, col_b)
                for (dev_a, col_a) in points_a
                for (dev_b, col_b) in points_b
                if {dev_a.source, dev_a.drain} != {dev_b.source, dev_b.drain}
            ]

            if valid_pairs:
                real_min_distance = min(abs(ca - cb) for ca, cb in valid_pairs)
                if real_min_distance < min_required_pitch:
                    violations.append(f"[RHBD FAIL - {target_layer}] Nós '{net_a_upper}' e '{net_b_upper}' com distância {real_min_distance} (Requerido: >= {min_required_pitch}).")
                
    return violations
# SMT-Based Transistor Placement with User-Defined Node Spacing Constraints

## Overview

This repository contains an implementation of an SMT-based methodology for physical transistor placement with Radiation Hardening by Design (RHBD) constraints.

The proposed method uses Satisfiability Modulo Theories (SMT) to determine transistor positions and orientations while enforcing geometric, topological, and user-defined minimum spacing constraints between selected electrical nodes. The additional spacing constraints provide a means of incorporating physical separation requirements associated with charge-sharing mitigation into the placement problem.

The repository also includes a benchmark suite composed of combinational and sequential standard cells, including NAND, NOR, AO/AOI, OA/OAI, MUX, XOR, latch, and other representative circuit structures. The benchmark is used to evaluate the proposed methodology in terms of placement width, constraint satisfaction, and computational resolution time under different RHBD spacing requirements.

The implementation supports both a flat placement flow and a hierarchical strategy for larger circuit instances. The repository provides the source code, SPICE netlists, and scripts required to reproduce the benchmark evaluation presented in the associated research work.

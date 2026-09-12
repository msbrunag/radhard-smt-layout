# SMT-Based Transistor Placement with User-Defined Node Spacing Constraints

## Overview

This repository contains an implementation of an SMT-based methodology for physical transistor placement with Radiation Hardening by Design (RHBD) constraints.

The proposed method uses Satisfiability Modulo Theories (SMT) to determine transistor positions and orientations while enforcing geometric, topological, and user-defined minimum spacing constraints between selected electrical nodes. The additional spacing constraints provide a means of incorporating physical separation requirements associated with charge-sharing mitigation into the placement problem.

The repository also includes a benchmark suite composed of combinational and sequential standard cells, including NAND, NOR, AO/AOI, OA/OAI, MUX, XOR, latch, and other representative circuit structures. The benchmark is used to evaluate the proposed methodology in terms of placement width, constraint satisfaction, and computational resolution time under different RHBD spacing requirements.

The implementation supports both a flat placement flow and a hierarchical strategy for larger circuit instances. The repository provides the source code, SPICE netlists, and scripts required to reproduce the benchmark evaluation presented in the associated research work.

## Prerequisites

Before running this project, you need to have **Python 3.8+** installed on your machine. 

### Installing Z3 Solver

You can install the Z3 Theorem Prover and its Python bindings using `pip`. Run the following command in your terminal:

```bash
pip install z3-solver
```

#### For Linux (Ubuntu/Debian) users
If you also need the system-level binaries, you can install them via APT:
```bash
sudo apt-get install z3
```

#### For macOS users
If you use Homebrew, you can install it by running:
```bash
brew install z3
```

## References

This project uses the **Z3 Theorem Prover**, developed and maintained by **Microsoft Research**.

* **Official Repository:** [GitHub - Z3Prover/z3]([https://github.com](https://github.com/Z3Prover/doc))
* **Official Documentation:** [Z3 API Documentation]([https://github.io](https://z3prover.github.io/api/html/))
* **Academic Citation:** 
  > de Moura, L., Bjørner, N. (2008). Z3: An Efficient SMT Solver. In: Ramakrishnan, C.R., Rehof, J. (eds) Tools and Algorithms for the Construction and Analysis of Systems. TACAS 2008. Lecture Notes in Computer Science, vol 4963. Springer, Berlin, Heidelberg.

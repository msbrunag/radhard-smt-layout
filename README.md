# SMT-Based Symbolic Transistor Placement with User-Defined Node Spacing Constraints

**An open-source EDA framework for Radiation Hardening by Design (RHBD) using Satisfiability Modulo Theories (SMT).**

## Overview

This repository contains an open-source EDA framework for Radiation Hardening by Design (RHBD). The framework leverages Satisfiability Modulo Theories (SMT) to automate symbolic transistor placement while enforcing user-defined minimum spacing constraints between selected transistor nodes. These constraints are intended to reduce charge sharing between physically adjacent sensitive nodes, thereby mitigating the likelihood of Multiple Bit Upsets (MBUs).

To ensure reproducibility, the repository also includes a benchmark suite of combinational and sequential standard cells (e.g., NAND, NOR, MUX, DFF, and Full Adder) used to validate the proposed placement methodology.

The proposed methodology focuses on single-row standard-cell layouts and provides a reproducible research framework for RHBD-aware transistor placement using symbolic layout generation.

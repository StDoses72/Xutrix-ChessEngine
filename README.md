# Xustrix Chess Engine

**Xustrix** is a lightweight, high-performance chess engine prototype developed as a passion project by a first-year Statistics & Machine Learning student. It combines classic search algorithms with optimized evaluation techniques and hardware-level speed enhancements via Cython.

---

## 🚀 Features

* **Engine Core**: Built on a Minimax search framework with **Alpha-Beta pruning**.
* **Performance Optimized**: Critical components like move generation (`movegen.pyx`) and attack detection (`isSquareAttacked.pyx`) are implemented in **Cython** for near-C execution speeds.
* **Advanced Evaluation**:
    * **PeSTO’s Piece-Square Tables (PST)**: Dynamically adjusts piece values based on the game phase (Middle-game vs. End-game).
    * **SEE (Static Exchange Evaluation)**: Used for move ordering to prioritize tactically sound captures.
* **Memory Efficiency**: Implements **Zobrist Hashing** and a **Transposition Table (TT)** to cache and reuse search results, significantly reducing redundant calculations.
* **Opening Book**: Includes a lightweight `opening.py` module to handle initial theory moves.
* **Interactive CLI**: A simple command-line interface for human-vs-engine or engine-vs-engine matchups.

---

## 🛠 Project Structure

.
├── engine.py                # Main game loop and engine logic
├── movegen.pyx              # Cythonized move generation
├── isSquareAttacked.pyx     # Cythonized attack logic
├── pesto.py                 # PeSTO evaluation tables and logic
├── opening.py               # Lightweight opening library
├── setup.py                 # Compilation script for Cython modules
├── piecePosition/           # PST JSON files (p_table_adjusted.json, etc.)
└── README.md                # Project documentation


## 📦 Installation & Setup

Prerequisites
    Python 3.8+

    NumPy: pip install numpy

    Cython(if the existing cython file does not work): Required to compile the .pyx files for performance.

    You MUST run the compilation command python setup.py build_ext --inplace before starting the engine for the first time.

## 🎮 How to Play

Run the main script to start the interface:

python engine.py

Select Mode: Choose whether the engine plays as White, Black, Both, or None.
Input Moves: Use standard algebraic notation (start square to end square), for example:
e2 e4

g1 f3

Quit: Type q at any time to exit the game.
Note: This version is a prototype. It currently does not strictly enforce move legality for human input—it is designed for users who follow standard chess rules.

## 🔬 Technical Highlights

### 1. Hybrid Search Architecture
Xustrix employs a sophisticated search strategy to navigate the vast game tree of chess:
* **Minimax with Alpha-Beta Pruning**: The core decision-making algorithm, optimized to discard branches that cannot possibly influence the final decision.
* **Beam Search (Root Heuristic)**: To manage search complexity at the root, the engine utilizes a beam search approach, focusing only on the top 15–25 most promising moves based on initial evaluations.
* **Quiescence Search**: To combat the "horizon effect," the engine performs an additional search on capture sequences beyond the fixed depth. This ensures the engine doesn't make a move that looks good at depth $N$ but leads to an immediate material loss at $N+1$.

### 2. Cython-Accelerated Core
Unlike standard Python engines, Xustrix offloads its most computationally expensive tasks to C-extension modules:
* **Move Generation**: Logic for pawn, knight, and sliding piece moves is handled in `movegen.pyx`.
* **Square Attack Logic**: The `isSquareAttacked.pyx` module allows for rapid checks of king safety and board control.
* **Performance**: By compiling these critical paths into machine code via Cython, the engine achieves a significant increase in Nodes Per Second (NPS).

### 3. Memory & Efficiency
* **Transposition Tables (TT)**: Uses **Zobrist Hashing** to store previously evaluated positions. If the engine encounters the same position via a different move order, it retrieves the result from memory instead of re-calculating.
* **Move Ordering**: Moves are sorted using **SEE (Static Exchange Evaluation)** and **MVV-LVA** (Most Valuable Victim - Least Valuable Attacker) to ensure the strongest moves are searched first, maximizing Alpha-Beta pruning efficiency.

### 4. Evaluation Phase
The engine calculates a score based on material and position. By utilizing the **PeSTO evaluation method**, the engine transitions its behavior smoothly from aggressive middle-game positioning to optimized end-game king activity.


## 🎓 About the Author

Created by XiangCheng Xu (StDoses72), a Statistics & Machine Learning university students in its first term as freshman. This project serves as a practical exploration of search complexity, heuristic evaluation, and Python-C interoperability.




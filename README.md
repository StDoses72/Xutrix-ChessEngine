# Xutrix Chess Engine

一个使用 C11 编写、支持 UCI、命令行对弈和本地 Web 界面的国际象棋引擎。
A C11 chess engine with UCI support, command-line play, and a local web interface.

[中文](#中文) · [English](#english)

---

## 中文

### 项目简介

Xutrix 是一个面向实战、引擎开发和搜索算法实验的国际象棋引擎。核心引擎使用 C11 编写，可以直接在终端运行，也可以作为 UCI 引擎接入图形界面，或通过仓库自带的浏览器界面和 Lichess Bot 桥接程序使用。

项目默认使用经典局面评估，同时支持从外部权重文件加载可选的 NNUE 评估器。仓库还包含走法生成验证、战术回归、基准测试以及 NNUE 数据准备和训练工具。

### 核心能力

- 完整合法走法生成，包括王车易位、吃过路兵和升变
- FEN 读入、UCI 走法解析以及 make/undo 走法栈
- Zobrist 哈希和可配置的置换表
- 迭代加深、Alpha-Beta/PVS、静态搜索、杀手走法、历史启发、空步裁剪、LMR 和 aspiration window
- 单线程与根节点并行搜索，以及并行 perft
- 经典评估器和可选 NNUE 推理
- 内置开局库及基于时钟的 UCI 时间管理
- 命令行对弈、本地 Web 棋盘和 Lichess Bot 集成
- perft、战术回归、引擎对比和 NNUE 训练工具

Xutrix 目前更适合作为可运行、可验证、可扩展的引擎项目使用。实际棋力取决于搜索深度、线程数、时间控制和所加载的评估权重。

### 快速开始

#### 环境要求

- C11 编译器：MSVC、GCC 或 Clang
- Windows 快速构建脚本需要 PowerShell
- CMake 3.16 或更高版本（可选，适用于通用构建流程）
- Python 3（仅 Web 界面、Lichess Bot 和训练工具需要）

#### Windows / PowerShell

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\c_engine\build.ps1
```

脚本会选择可用的 MSVC、GCC 或 Clang，并生成：

```text
c_engine\xutrix.exe
```

运行一次搜索确认引擎可用：

```powershell
.\c_engine\xutrix.exe best 6
```

#### CMake

```powershell
cmake -S .\c_engine -B .\c_engine\build -DCMAKE_BUILD_TYPE=Release
cmake --build .\c_engine\build --config Release
```

CMake 会把 `xutrix` 可执行文件生成在构建目录中；具体路径取决于所使用的生成器和平台。

### 使用引擎

#### 直接对弈

不带参数双击或启动 Windows 可执行文件，会进入交互菜单。也可以直接指定搜索深度和执棋方：

```powershell
.\c_engine\xutrix.exe play 6 white
```

走法使用 UCI 格式输入，例如 `e2e4`、`g1f3` 或 `e7e8q`；输入 `q` 退出。

#### 常用命令

| 命令 | 用途 |
| --- | --- |
| `xutrix best <depth> [fen]` | 使用可用逻辑核心并行搜索最佳走法 |
| `xutrix best-single <depth> [fen]` | 单线程迭代加深搜索 |
| `xutrix best-par <depth> [threads] [fen]` | 指定线程数进行并行搜索 |
| `xutrix best-direct <depth> [fen]` | 不使用迭代加深的直接搜索 |
| `xutrix eval [fen]` | 输出经典评估、NNUE 状态和当前评估器 |
| `xutrix moves [fen]` | 列出当前局面的全部合法 UCI 走法 |
| `xutrix perft <depth> [fen]` | 运行走法生成节点测试 |
| `xutrix perft-par <depth> [threads] [fen]` | 并行运行 perft |
| `xutrix divide <depth> [fen]` | 按根走法拆分 perft 节点 |
| `xutrix play [depth] [white\|black] [fen]` | 在终端中与引擎对弈 |
| `xutrix uci` | 启动 UCI 协议循环 |

如果提供 FEN，请把完整字符串放在引号中：

```powershell
.\c_engine\xutrix.exe best 8 "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
```

#### 接入 UCI 图形界面

在支持 UCI 的国际象棋图形界面中，将引擎路径设置为 `c_engine\xutrix.exe`。Xutrix 暴露以下选项：

| UCI 选项 | 范围 | 说明 |
| --- | --- | --- |
| `Threads` | 1–64 | 搜索线程数；默认使用检测到的逻辑核心数 |
| `Hash` | 1–4096 MB | 置换表大小 |
| `OwnBook` | `true` / `false` | 是否启用内置开局库 |
| `BookMaxPly` | 0–40 | 开局库允许使用的最大半回合数；`0` 表示禁用 |

也可以手动启动协议模式：

```powershell
.\c_engine\xutrix.exe uci
```

### 本地 Web 界面

先构建引擎，然后在仓库根目录运行：

```powershell
python .\webui\server.py
```

打开终端打印的地址，默认是 [http://127.0.0.1:8765](http://127.0.0.1:8765)。如果端口被占用，服务器会自动尝试后续端口。

Web 界面支持点击走子、合法落点提示、选择执白或执黑、搜索深度调节、FEN 载入、翻转棋盘、悔棋和对局记录。服务仅监听本机地址，并通过 `c_engine\xutrix.exe` 完成走法生成和搜索。

更多信息见 [`webui/README.md`](webui/README.md)。

### 可选 NNUE 评估器

Xutrix 默认使用经典评估器。要启用 NNUE，请把 `XUTRIX_NNUE` 环境变量指向兼容的 `.nnue` 权重文件，然后启动引擎：

```powershell
$env:XUTRIX_NNUE = (Resolve-Path .\c_engine\weights\your-model.nnue).Path
.\c_engine\xutrix.exe eval
```

`eval` 输出中的 `active evaluator nnue` 表示加载成功。未设置或未成功加载权重时，引擎继续使用经典评估器。

仓库不内置可用于实战的训练权重；`c_engine/tools` 提供从 PGN 提取局面、使用 Stockfish 标注、训练和导出 Xutrix NNUE 文件的完整工具链。安装训练依赖：

```powershell
python -m pip install -r .\c_engine\tools\requirements-training.txt
```

详细流程见 [`c_engine/README.md`](c_engine/README.md)。

### Lichess Bot

`bot` 目录提供基于开源 `lichess-bot` 的本地桥接。使用前需要一个 Lichess BOT 账号及其 API Token；不要把真实 Token 提交到 Git。

基本设置流程：

```powershell
git clone https://github.com/lichess-bot-devs/lichess-bot.git .\bot\lichess-bot
python -m venv .\bot\venv
.\bot\venv\Scripts\python.exe -m pip install -r .\bot\lichess-bot\requirements.txt
Copy-Item .\bot\config.xutrix.example.yml .\bot\config.yml
```

编辑 `bot\config.yml`，填入 Token，并把 `engine.dir` 和 `engine.working_dir` 改为本机仓库中的 `c_engine` 绝对路径。构建引擎后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\bot\run.ps1
```

后台启动、状态检查和停止脚本分别是 `bot\start.ps1`、`bot\status.ps1` 和 `bot\stop.ps1`。更多信息见 [`bot/README.md`](bot/README.md)。

### 验证

Windows 验证脚本会重新构建引擎，检查起始局面和 Kiwipete 的 perft 结果，对比两种走法生成路径，并运行单线程和并行搜索冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\c_engine\verify.ps1
```

可选的战术回归测试：

```powershell
python .\c_engine\tools\run_tactical_regression.py
```

### 项目结构

```text
.
├── c_engine/
│   ├── src/                 C11 引擎源码
│   ├── tools/               数据、训练、回归和基准测试工具
│   ├── data/                测试夹具、战术题和基准结果
│   ├── CMakeLists.txt       CMake 构建入口
│   ├── build.ps1            Windows 快速构建脚本
│   └── verify.ps1           核心验证脚本
├── webui/                   本地浏览器棋盘和 Python HTTP 服务
├── bot/                     Lichess Bot 配置模板与运行脚本
├── LICENSE                  MIT 许可证
└── README.md                项目总览与使用说明
```

### 许可证

本项目使用 [MIT License](LICENSE)。

---

## English

### Overview

Xutrix is a chess engine for play, engine development, and search experimentation. Its core is written in C11 and can run directly in a terminal, act as a UCI engine inside a chess GUI, or power the included browser interface and Lichess Bot bridge.

The engine uses a classical evaluator by default and can optionally load an NNUE evaluator from an external weight file. The repository also includes move-generation validation, tactical regression, benchmarking, and NNUE data preparation and training tools.

### Highlights

- Fully legal move generation, including castling, en passant, and promotion
- FEN loading, UCI move parsing, and a make/undo move stack
- Zobrist hashing and a configurable transposition table
- Iterative deepening, Alpha-Beta/PVS, quiescence search, killer moves, history heuristics, null-move pruning, LMR, and aspiration windows
- Single-threaded and root-parallel search, plus parallel perft
- Classical evaluation and optional NNUE inference
- A built-in opening book and clock-aware UCI time management
- Command-line play, a local web board, and Lichess Bot integration
- Perft, tactical regression, engine comparison, and NNUE training tools

Xutrix is best treated as a runnable, testable, and extensible engine project. Playing strength depends on search depth, thread count, time control, and the evaluation weights in use.

### Quick start

#### Requirements

- A C11 compiler: MSVC, GCC, or Clang
- PowerShell for the Windows convenience scripts
- CMake 3.16 or newer for the optional general-purpose build
- Python 3 only for the web UI, Lichess Bot, and training tools

#### Windows / PowerShell

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\c_engine\build.ps1
```

The script selects an available MSVC, GCC, or Clang compiler and produces:

```text
c_engine\xutrix.exe
```

Run a search to confirm the engine works:

```powershell
.\c_engine\xutrix.exe best 6
```

#### CMake

```powershell
cmake -S .\c_engine -B .\c_engine\build -DCMAKE_BUILD_TYPE=Release
cmake --build .\c_engine\build --config Release
```

CMake places the `xutrix` executable somewhere under the build directory; the exact path depends on the generator and platform.

### Using the engine

#### Play directly

Launching the Windows executable without arguments opens an interactive menu. You can also choose the search depth and your side explicitly:

```powershell
.\c_engine\xutrix.exe play 6 white
```

Enter moves in UCI notation, such as `e2e4`, `g1f3`, or `e7e8q`. Enter `q` to quit.

#### Common commands

| Command | Purpose |
| --- | --- |
| `xutrix best <depth> [fen]` | Search for the best move in parallel using available logical cores |
| `xutrix best-single <depth> [fen]` | Run single-threaded iterative deepening |
| `xutrix best-par <depth> [threads] [fen]` | Run parallel search with an explicit thread count |
| `xutrix best-direct <depth> [fen]` | Search directly without iterative deepening |
| `xutrix eval [fen]` | Show classical evaluation, NNUE status, and the active evaluator |
| `xutrix moves [fen]` | List all legal UCI moves in the position |
| `xutrix perft <depth> [fen]` | Run a move-generation node-count test |
| `xutrix perft-par <depth> [threads] [fen]` | Run perft in parallel |
| `xutrix divide <depth> [fen]` | Split perft counts by root move |
| `xutrix play [depth] [white\|black] [fen]` | Play against the engine in the terminal |
| `xutrix uci` | Start the UCI protocol loop |

When supplying a FEN, quote the complete string:

```powershell
.\c_engine\xutrix.exe best 8 "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
```

#### Connect a UCI GUI

In any UCI-compatible chess GUI, set the engine executable to `c_engine\xutrix.exe`. Xutrix exposes these options:

| UCI option | Range | Description |
| --- | --- | --- |
| `Threads` | 1–64 | Search threads; defaults to the detected logical-core count |
| `Hash` | 1–4096 MB | Transposition-table size |
| `OwnBook` | `true` / `false` | Enable or disable the built-in opening book |
| `BookMaxPly` | 0–40 | Maximum half-move count for book use; `0` disables it |

You can also start protocol mode manually:

```powershell
.\c_engine\xutrix.exe uci
```

### Local web interface

Build the engine, then run this from the repository root:

```powershell
python .\webui\server.py
```

Open the URL printed in the terminal, normally [http://127.0.0.1:8765](http://127.0.0.1:8765). If that port is occupied, the server automatically tries subsequent ports.

The web UI provides click-to-move play, legal-move highlights, a White/Black selector, search-depth control, FEN loading, board flipping, undo, and a match record. The service listens only on localhost and delegates move generation and search to `c_engine\xutrix.exe`.

See [`webui/README.md`](webui/README.md) for more details.

### Optional NNUE evaluator

Xutrix uses its classical evaluator by default. To enable NNUE, point the `XUTRIX_NNUE` environment variable to a compatible `.nnue` file before starting the engine:

```powershell
$env:XUTRIX_NNUE = (Resolve-Path .\c_engine\weights\your-model.nnue).Path
.\c_engine\xutrix.exe eval
```

The line `active evaluator nnue` confirms that the model loaded. If no model is configured or loaded successfully, the engine continues with classical evaluation.

The repository does not include playing-strength weights. The tools under `c_engine/tools` provide a complete workflow for extracting positions from PGNs, labeling them with Stockfish, and training and exporting Xutrix NNUE files. Install the training dependencies with:

```powershell
python -m pip install -r .\c_engine\tools\requirements-training.txt
```

See [`c_engine/README.md`](c_engine/README.md) for the full workflow.

### Lichess Bot

The `bot` directory provides a local bridge based on the open-source `lichess-bot` project. You need a Lichess BOT account and API token. Never commit the real token to Git.

Basic setup:

```powershell
git clone https://github.com/lichess-bot-devs/lichess-bot.git .\bot\lichess-bot
python -m venv .\bot\venv
.\bot\venv\Scripts\python.exe -m pip install -r .\bot\lichess-bot\requirements.txt
Copy-Item .\bot\config.xutrix.example.yml .\bot\config.yml
```

Edit `bot\config.yml`, add the token, and change `engine.dir` and `engine.working_dir` to the absolute path of this checkout's `c_engine` directory. After building Xutrix, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bot\run.ps1
```

For background operation, use `bot\start.ps1`, `bot\status.ps1`, and `bot\stop.ps1`. See [`bot/README.md`](bot/README.md) for more details.

### Verification

The Windows verification script rebuilds the engine, checks start-position and Kiwipete perft results, compares both move-generation paths, and runs single-threaded and parallel search smoke tests:

```powershell
powershell -ExecutionPolicy Bypass -File .\c_engine\verify.ps1
```

An optional tactical regression suite is also available:

```powershell
python .\c_engine\tools\run_tactical_regression.py
```

### Repository layout

```text
.
├── c_engine/
│   ├── src/                 C11 engine source
│   ├── tools/               Data, training, regression, and benchmark tools
│   ├── data/                Fixtures, tactical cases, and benchmark results
│   ├── CMakeLists.txt       CMake build entry point
│   ├── build.ps1            Windows convenience build
│   └── verify.ps1           Core verification suite
├── webui/                   Local browser board and Python HTTP server
├── bot/                     Lichess Bot configuration and runner scripts
├── LICENSE                  MIT license
└── README.md                Project overview and usage guide
```

### License

Xutrix is available under the [MIT License](LICENSE).

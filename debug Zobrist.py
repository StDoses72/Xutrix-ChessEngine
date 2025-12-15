import sys
import copy
import numpy as np

# ==========================================
# 1. 适配你的 engine.py 导入
# ==========================================
try:
    # ⚠️ 关键修改：
    # 1. 不导入 board/piecePositionMap (因为它们不是全局的)
    # 2. 导入 initializeBoard (而不是 initBoard)
    # 3. 导入 TRANSPOSITION_TABLE (全大写)
    from engine import (
        initializeBoard, doMove, undoMove, 
        TRANSPOSITION_TABLE, minimax,
        importPositionMap,
        algebraicToIndex, indexToAlgebraic,
        currentHash, computeHash,
        pawnPosition, castling_rights, moveHistory
    )
    # 尝试导入全局变量 ZOBRIST_TABLE 等用于调试（可选）
    from engine import ZOBRIST_TABLE, ZOBRIST_BLACK_TURN
    
    print("✅ 成功导入 engine.py")

except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保 engine.py, movegen.py, isSquareAttacked.py 都在同一目录下。")
    sys.exit(1)

# ==========================================
# 2. 辅助：获取当前的全局 Hash
# ==========================================
def get_engine_hash():
    # 因为 currentHash 是 engine 里的全局变量，且是 numpy 类型
    # 我们通过 sys.modules 确保取到的是最新的值
    return sys.modules['engine'].currentHash

# ==========================================
# 🧪 测试 1: 殊途同归 (Transposition Check)
# ==========================================
def test_path_transposition():
    print("\n[Test 1] 殊途同归测试 (Transposition Check)...")
    
    # 1. 初始化
    board = initializeBoard() 
    # 注意：initializeBoard 会重置全局的 currentHash, pawnPosition 等
    
    # 路径 A: e2e4 -> b8c6 -> g1f3
    # 注意：你的 doMove 需要 algebraic string ('e2', 'e4')
    doMove(board, 'e2', 'e4')
    doMove(board, 'b8', 'c6')
    doMove(board, 'g1', 'f3')
    hash_A = get_engine_hash()
    print(f"  Path A (e4, Nc6, Nf3) Hash: {hash_A}")
    
    # 重置
    board = initializeBoard()
    
    # 路径 B: g1f3 -> b8c6 -> e2e4 (顺序不同，局面相同)
    doMove(board, 'g1', 'f3')
    doMove(board, 'b8', 'c6')
    doMove(board, 'e2', 'e4')
    hash_B = get_engine_hash()
    print(f"  Path B (Nf3, Nc6, e4) Hash: {hash_B}")
    
    if hash_A == hash_B:
        print("  ✅ 成功: 两个路径到达同一局面，Hash 值一致！")
        return True
    else:
        print(f"  ❌ 失败: 局面相同但 Hash 不同！")
        print(f"     Hash A: {hash_A}")
        print(f"     Hash B: {hash_B}")
        print(f"     XOR 差值: {hash_A ^ hash_B}")
        return False

# ==========================================
# 🧪 测试 2: 悔棋一致性 (Undo Consistency)
# ==========================================
def test_undo_consistency():
    print("\n[Test 2] 悔棋一致性测试 (Undo Consistency)...")
    
    board = initializeBoard()
    start_hash = get_engine_hash()
    print(f"  初始 Hash: {start_hash}")
    
    # 测试一个包含吃子和兵推进的序列
    # 1. e2-e4
    # 2. d7-d5
    # 3. e4-d5 (吃子)
    # 4. d8-d5 (吃子)
    moves = [('e2', 'e4'), ('d7', 'd5'), ('e4', 'd5'), ('d8', 'd5')] 
    print(f"  执行走法序列: {moves}")
    
    for start, end in moves:
        doMove(board, start, end)
        
    mid_hash = get_engine_hash()
    print(f"  中间 Hash: {mid_hash}")
    
    print("  正在悔棋 (Undo)...")
    for _ in range(len(moves)):
        undoMove(board)
        
    end_hash = get_engine_hash()
    print(f"  结束 Hash: {end_hash}")
    
    if start_hash == end_hash:
        print("  ✅ 成功: 悔棋后 Hash 完美还原！")
        return True
    else:
        print(f"  ❌ 失败: 悔棋后 Hash 不匹配！")
        print(f"     Diff: {start_hash ^ end_hash}")
        return False

# ==========================================
# 🧪 测试 3: 搜索稳定性 (Search Stability)
# ==========================================
def test_search_stability():
    print("\n[Test 3] 搜索稳定性测试 (Search Stability with TT)...")
    
    # 1. 准备环境
    board = initializeBoard()
    piecePositionMap = importPositionMap() # 你的函数名是这个
    
    # 走成意大利开局
    setup_moves = [('e2','e4'), ('e7','e5'), ('g1','f3'), ('b8','c6'), ('f1','c4')]
    for s, e in setup_moves:
        doMove(board, s, e)
        
    depth = 3
    print(f"  当前局面: Italian Game. 搜索深度: {depth}")
    
    # 第 1 次搜索：清空 TT
    TRANSPOSITION_TABLE.clear()
    print("  运行第 1 次搜索 (Fresh TT)...")
    # 注意：你的 minimax 参数是 (board, depth, alpha, beta, maximizingPlayer, piecePositionMap, isRoot)
    # 这里 white 是 maximizing (True), isRoot=True
    score_1 = minimax(board, depth, -float('inf'), float('inf'), True, piecePositionMap, True)
    print(f"  Score 1: {score_1}")
    
    # 第 2 次搜索：不清理 TT，直接再次运行
    # 理论上应该非常快，且分数完全一样
    print("  运行第 2 次搜索 (Dirty TT)...")
    score_2 = minimax(board, depth, -float('inf'), float('inf'), True, piecePositionMap, True)
    print(f"  Score 2: {score_2}")
    
    # 第 3 次搜索：再次清空 TT，确保不是偶然
    TRANSPOSITION_TABLE.clear()
    print("  运行第 3 次搜索 (Cleared TT)...")
    score_3 = minimax(board, depth, -float('inf'), float('inf'), True, piecePositionMap, True)
    print(f"  Score 3: {score_3}")

    # 浮点数比较允许微小误差
    if abs(score_1 - score_2) < 0.001 and abs(score_1 - score_3) < 0.001:
        print("  ✅ 成功: TT 工作正常，多次搜索结果一致。")
        return True
    else:
        print("  ❌ 失败: 搜索结果不一致！")
        print(f"     S1: {score_1}, S2: {score_2}, S3: {score_3}")
        return False

# ==========================================
# 🚀 主入口
# ==========================================
if __name__ == "__main__":
    print("=== 开始 Zobrist & TT 诊断程序 (适配版) ===")
    
    try:
        pass_1 = test_path_transposition()
        pass_2 = test_undo_consistency()
        
        if pass_1 and pass_2:
            pass_3 = test_search_stability()
        else:
            print("\n⚠️ 跳过搜索测试，请先修复 Hash 计算错误。")
            
    except Exception as e:
        print(f"\n❌ 测试运行中崩溃: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n=== 测试结束 ===")
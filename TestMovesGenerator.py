import engine
import sys

# ---------------------------------------------------------
# 🛠️ 辅助函数：快速打印结果
# ---------------------------------------------------------
def assert_moves(case_name, moves, expected_move, should_exist=True):
    if should_exist:
        if expected_move in moves:
            print(f"✅ [PASS] {case_name}: 成功生成了 {expected_move}")
        else:
            print(f"❌ [FAIL] {case_name}: 期望包含 {expected_move}，但实际生成为 {moves}")
    else:
        if expected_move not in moves:
            print(f"✅ [PASS] {case_name}: 正确地忽略了 {expected_move}")
        else:
            print(f"❌ [FAIL] {case_name}: 不应该生成 {expected_move} (参数为None)，但却生成了！")

# ---------------------------------------------------------
# 🧪 测试主逻辑
# ---------------------------------------------------------
def run_tests():
    print("=== 开始测试 generatePawnMoves 参数化逻辑 ===\n")

    # 准备一个空棋盘
    board = [['.'] * 8 for _ in range(8)]
    
    # 场景 1: 白兵过路吃兵 (White En Passant)
    # -------------------------------------------------
    # 假设：白兵在 e5，黑兵刚走了 d7 -> d5
    # 预期：白兵应该能走到 d6 吃掉黑兵
    
    # 1. 设置棋子
    board[3][4] = 'P'  # e5 (Row 3, Col 4)
    board[3][3] = 'p'  # d5 (黑兵就在旁边)
    
    # 2. 模拟传入的过路兵参数
    ep_square = 'd6'    # 过路兵的目标格
    ep_color = 'black'  # 被吃的是黑兵
    
    print("Test 1: 白兵在 e5，过路兵目标 d6 (Black)")
    # 🔥 关键点：这里直接传入参数，不再依赖 global
    moves = engine.generatePawnMoves(board, 'e5', ep_square, ep_color)
    assert_moves("White En Passant", moves, 'd6', should_exist=True)


    # 场景 2: 黑兵过路吃兵 (Black En Passant)
    # -------------------------------------------------
    # 假设：黑兵在 c4，白兵刚走了 b2 -> b4
    # 预期：黑兵应该能走到 b3 吃掉白兵
    
    # 1. 设置棋子 (清理之前的)
    board = [['.'] * 8 for _ in range(8)]
    board[4][2] = 'p'  # c4 (Row 4, Col 2)
    board[4][1] = 'P'  # b4 (白兵在旁边)
    
    # 2. 模拟参数
    ep_square = 'b3'
    ep_color = 'white' # 被吃的是白兵
    
    print("\nTest 2: 黑兵在 c4，过路兵目标 b3 (White)")
    moves = engine.generatePawnMoves(board, 'c4', ep_square, ep_color)
    assert_moves("Black En Passant", moves, 'b3', should_exist=True)


    # 场景 3: 参数传 None (测试解耦是否彻底)
    # -------------------------------------------------
    # 假设：局面一模一样（白兵e5，黑兵d5），但这次没有过路兵机会（比如是上上步走的）
    # 预期：绝对不能生成 'd6'
    
    board = [['.'] * 8 for _ in range(8)]
    board[3][4] = 'P'
    board[3][3] = 'p'
    
    print("\nTest 3: 局面有兵相邻，但参数传入 None")
    # 🔥 关键点：传入 None, None
    moves = engine.generatePawnMoves(board, 'e5', None, None)
    assert_moves("No En Passant Param", moves, 'd6', should_exist=False)


    # 场景 4: 普通移动检查 (确保没改坏别的)
    # -------------------------------------------------
    print("\nTest 4: 普通移动检查 (e2 -> e3, e4)")
    board = engine.initializeBoard() # 用默认开局
    moves = engine.generatePawnMoves(board, 'e2', None, None)
    
    if 'e3' in moves and 'e4' in moves:
        print(f"✅ [PASS] 普通移动正常: {moves}")
    else:
        print(f"❌ [FAIL] 普通移动异常: {moves}")

if __name__ == "__main__":
    try:
        run_tests()
    except TypeError as e:
        print("\n💥 运行崩溃！")
        print("原因可能是你修改了 generatePawnMoves 的定义，但没有修改所有调用它的地方。")
        print(f"错误详情: {e}")
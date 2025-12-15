import engine

# ---------------------------------------------------------
# 🛠️ 辅助工具
# ---------------------------------------------------------
def get_clean_rights():
    """生成一个全新的、允许所有易位的权限字典"""
    return {
        'white_king_moved': False,
        'white_rook_a_moved': False,
        'white_rook_h_moved': False,
        'black_king_moved': False,
        'black_rook_a_moved': False,
        'black_rook_h_moved': False
    }

def assert_move(case_name, moves, expected_move, should_exist):
    if should_exist:
        if expected_move in moves:
            print(f"✅ [PASS] {case_name}: 成功生成 {expected_move}")
        else:
            print(f"❌ [FAIL] {case_name}: 期望包含 {expected_move}，但实际只有: {moves}")
    else:
        if expected_move not in moves:
            print(f"✅ [PASS] {case_name}: 正确排除了 {expected_move}")
        else:
            print(f"❌ [FAIL] {case_name}: 不该生成 {expected_move} (权限已禁)，但却生成了！")

# ---------------------------------------------------------
# 🧪 测试主逻辑
# ---------------------------------------------------------
def run_tests():
    print("=== 开始测试 generateKingMoves 参数化逻辑 ===\n")

    # 1. 准备环境：只放王和车，确保路径通畅，没有被将军
    # -------------------------------------------------
    board = [['.'] * 8 for _ in range(8)]
    board[7][4] = 'K'  # e1 (白王)
    board[7][7] = 'R'  # h1 (白车，短易位用)
    board[7][0] = 'R'  # a1 (白车，长易位用)
    
    # 场景 1: 权限全开 (Standard Case)
    # -------------------------------------------------
    # 预期：应该生成 'g1' (短易位) 和 'c1' (长易位)
    
    rights_all_open = get_clean_rights()
    
    print("Test 1: 传入全开权限 (Should Castle)")
    # 🔥 关键：显式传入字典
    moves = engine.generateKingMoves(board, 'e1', rights_all_open)
    assert_move("White Short Castle", moves, 'g1', should_exist=True)
    assert_move("White Long Castle",  moves, 'c1', should_exist=True)


    # 场景 2: 仅仅禁止短易位 (Rights Control Test)
    # -------------------------------------------------
    # 假设：白王没动，但 h1 的车动过了 (white_rook_h_moved = True)
    # 预期：'g1' 应该消失，但 'c1' 应该还在
    
    rights_no_short = get_clean_rights()
    rights_no_short['white_rook_h_moved'] = True # 🚫 禁止短易位
    
    print("\nTest 2: 传入禁止短易位权限 (Short Forbidden)")
    moves = engine.generateKingMoves(board, 'e1', rights_no_short)
    assert_move("White Short Castle", moves, 'g1', should_exist=False) # 期望消失
    assert_move("White Long Castle",  moves, 'c1', should_exist=True)  # 期望保留


    # 场景 3: 王动过了 (King Moved Test)
    # -------------------------------------------------
    # 假设：王动过了 (white_king_moved = True)
    # 预期：所有易位都应该消失
    
    rights_king_moved = get_clean_rights()
    rights_king_moved['white_king_moved'] = True # 🚫 禁止所有
    
    print("\nTest 3: 传入王已移动权限 (All Forbidden)")
    moves = engine.generateKingMoves(board, 'e1', rights_king_moved)
    assert_move("White Short Castle", moves, 'g1', should_exist=False)
    assert_move("White Long Castle",  moves, 'c1', should_exist=False)


    # 场景 4: 黑方测试 (Black Side)
    # -------------------------------------------------
    # 清空棋盘，放黑棋
    board = [['.'] * 8 for _ in range(8)]
    board[0][4] = 'k' # e8
    board[0][0] = 'r' # a8
    
    rights_black = get_clean_rights()
    
    print("\nTest 4: 黑方长易位测试 (Black Long Castle)")
    moves = engine.generateKingMoves(board, 'e8', rights_black)
    assert_move("Black Long Castle", moves, 'c8', should_exist=True)
    
    # 测试禁止
    rights_black['black_rook_a_moved'] = True
    moves_blocked = engine.generateKingMoves(board, 'e8', rights_black)
    assert_move("Black Long Castle (Blocked)", moves_blocked, 'c8', should_exist=False)

if __name__ == "__main__":
    try:
        run_tests()
    except TypeError as e:
        print("\n💥 运行崩溃！")
        print("原因：generateKingMoves 的参数数量不对，或者调用处没改全。")
        print(f"错误信息: {e}")
    except Exception as e:
        print(f"\n💥 其他错误: {e}")
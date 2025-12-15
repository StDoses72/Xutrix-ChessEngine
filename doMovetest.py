import engine

# ---------------------------------------------------------
# 🛠️ 辅助工具
# ---------------------------------------------------------
def empty_board():
    return [['.'] * 8 for _ in range(8)]

def reset_globals():
    # 最小化重置：只重置本测试会用到的全局
    engine.moveHistory = []
    engine.enPassantSquare = None
    engine.enPassantColor = None

    # pawnPosition 必须存在且是 set
    engine.pawnPosition = {'white': set(), 'black': set()}

    # 有些引擎逻辑可能依赖这些存在
    if not hasattr(engine, "castling_rights"):
        engine.castling_rights = {
            'white_king_moved': False,
            'white_rook_a_moved': False,
            'white_rook_h_moved': False,
            'black_king_moved': False,
            'black_rook_a_moved': False,
            'black_rook_h_moved': False
        }

def scan_pawns_from_board(board):
    w, b = set(), set()
    for r in range(8):
        for c in range(8):
            if board[r][c] == 'P':
                w.add(engine.indexToAlgebraic(r, c))
            elif board[r][c] == 'p':
                b.add(engine.indexToAlgebraic(r, c))
    return w, b

def assert_pawn_consistency(case_name, board):
    w_board, b_board = scan_pawns_from_board(board)
    w_set = engine.pawnPosition['white']
    b_set = engine.pawnPosition['black']

    if w_board != w_set:
        print(f"❌ [FAIL] {case_name}: WHITE pawnPosition 不一致")
        print(f"board扫到: {sorted(w_board)}")
        print(f"pawnPosition: {sorted(w_set)}")
        raise AssertionError("WHITE pawnPosition mismatch")

    if b_board != b_set:
        print(f"❌ [FAIL] {case_name}: BLACK pawnPosition 不一致")
        print(f"board扫到: {sorted(b_board)}")
        print(f"pawnPosition: {sorted(b_set)}")
        raise AssertionError("BLACK pawnPosition mismatch")

    print(f"✅ [PASS] {case_name}: pawnPosition 与 board 一致")

def assert_eq(case_name, a, b, msg=""):
    if a != b:
        print(f"❌ [FAIL] {case_name}: 期望 {b}，实际 {a}. {msg}")
        raise AssertionError(msg or "assert_eq failed")
    print(f"✅ [PASS] {case_name}")

# ---------------------------------------------------------
# 🧪 测试主逻辑
# ---------------------------------------------------------
def run_tests():
    print("=== 开始测试 pawnUndo / doMove / undoMove 一致性 ===\n")
    reset_globals()

    # -------------------------------------------------
    # Test 1: 普通兵两步推进 + undo
    # -------------------------------------------------
    board = empty_board()
    board[7][4] = 'K'
    board[0][4] = 'k'
    board[6][4] = 'P'  # e2
    engine.pawnPosition['white'].add('e2')

    assert_pawn_consistency("T1-Initial", board)

    engine.doMove(board, 'e2', 'e4')
    assert_pawn_consistency("T1-After e2e4", board)
    assert_eq("T1-enPassantSquare should be e3", engine.enPassantSquare, 'e3')

    engine.undoMove(board)
    assert_pawn_consistency("T1-After undo e2e4", board)
    assert_eq("T1-enPassantSquare restored", engine.enPassantSquare, None)

    print()

    # -------------------------------------------------
    # Test 2: 普通吃兵 + undo
    # white pawn e2 captures d3 (需要先把黑兵放在 d3)
    # -------------------------------------------------
    reset_globals()
    board = empty_board()
    board[7][4] = 'K'
    board[0][4] = 'k'
    board[6][4] = 'P'  # e2
    board[5][3] = 'p'  # d3

    engine.pawnPosition['white'].add('e2')
    engine.pawnPosition['black'].add('d3')

    assert_pawn_consistency("T2-Initial", board)

    engine.doMove(board, 'e2', 'd3')
    assert_pawn_consistency("T2-After e2xd3", board)

    engine.undoMove(board)
    assert_pawn_consistency("T2-After undo e2xd3", board)

    print()

    # -------------------------------------------------
    # Test 3: en passant + undo (最关键)
    #
    # 构造：
    #   black pawn 在 d4
    #   white pawn 从 e2 走到 e4，enPassantSquare = e3
    #   black pawn d4xe3 en-passant，吃掉 e4 的白兵
    # -------------------------------------------------
    reset_globals()
    board = empty_board()
    board[7][4] = 'K'
    board[0][4] = 'k'

    board[6][4] = 'P'  # e2
    board[4][3] = 'p'  # d4

    engine.pawnPosition['white'].add('e2')
    engine.pawnPosition['black'].add('d4')

    assert_pawn_consistency("T3-Initial", board)

    engine.doMove(board, 'e2', 'e4')
    assert_pawn_consistency("T3-After e2e4", board)
    assert_eq("T3-enPassantSquare should be e3", engine.enPassantSquare, 'e3')
    assert_eq("T3-enPassantColor should be white", engine.enPassantColor, 'white')

    engine.doMove(board, 'd4', 'e3')  # en-passant capture
    assert_pawn_consistency("T3-After d4xe3 ep", board)

    # undo ep
    engine.undoMove(board)
    assert_pawn_consistency("T3-After undo d4xe3 ep", board)

    # undo e2e4
    engine.undoMove(board)
    assert_pawn_consistency("T3-After undo e2e4", board)

    print()

    # -------------------------------------------------
    # Test 4: promotion + undo
    #
    # 这里我默认：promotion 后 pawnPosition 仍然包含 'a8'（因为你当前逻辑就是把 P 变 Q，但 pawnPosition 仍 add 到Square）
    # 如果你希望 promotion 后 pawnPosition 删除该 pawn：见下方注释
    # -------------------------------------------------
    reset_globals()
    board = empty_board()
    board[7][4] = 'K'
    board[0][4] = 'k'

    board[1][0] = 'P'  # a7
    engine.pawnPosition['white'].add('a7')

    assert_pawn_consistency("T4-Initial", board)

    engine.doMove(board, 'a7', 'a8')
    # promotion 后 board 上是 Q，但 pawnPosition 仍可能包含 a8（你的当前写法确实会 add）
    # 这里按你的当前设计检查一致性：board 已无 'P'，所以 scan_pawns 会不包含 a8
    # 如果你继续保留 pawnPosition 包含 a8，这个一致性检查会 FAIL ——这说明“pawnPosition 语义=当前棋盘上 pawn 的集合”被破坏了。
    #
    # ✅ 推荐语义：pawnPosition 只存 pawn。那 promotion 后应该 remove 掉。
    #
    # 所以我们这里分两种模式：
    #
    # 模式A（推荐）：promotion 后 pawnPosition 不包含 a8
    # 模式B（你当前实现）：promotion 后 pawnPosition 仍包含 a8 ——那 pawnPosition 就不是“pawn集合”，computePawnStructure 会出错
    #
    # 我默认你想要正确语义（模式A），因此这里要求一致性：
    assert_pawn_consistency("T4-After a7a8 promotion", board)

    engine.undoMove(board)
    assert_pawn_consistency("T4-After undo promotion", board)

    print("\nALL TESTS PASSED ✅")

# ---------------------------------------------------------
# 🔥 运行入口
# ---------------------------------------------------------
if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print("\n💥 断言失败：pawnUndo 或 pawnPosition 维护存在问题")
        print(f"错误信息: {e}")
    except Exception as e:
        print("\n💥 其他错误")
        print(f"错误信息: {e}")

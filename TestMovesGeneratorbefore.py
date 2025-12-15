import engine

def test_before_refactor():
    print("=== 🛑 运行基准测试 (改代码前) ===")
    
    # 1. 准备棋盘
    board = [['.'] * 8 for _ in range(8)]
    board[3][4] = 'P'  # e5 白兵
    board[3][3] = 'p'  # d5 黑兵
    
    # 2. 【关键】手动设置 Global 变量，模拟之前的运行环境
    engine.enPassantSquare = 'd6'
    engine.enPassantColor = 'black'
    
    print(f"设置 Global: enPassantSquare={engine.enPassantSquare}, Color={engine.enPassantColor}")
    
    # 3. 调用旧接口 (只传 board 和 square)
    moves = engine.generatePawnMoves(board, 'e5')
    
    # 4. 验证
    if 'd6' in moves:
        print("✅ [PASS] 旧逻辑成功生成了过路兵吃 d6")
    else:
        print(f"❌ [FAIL] 旧逻辑居然没生成 d6？当前生成: {moves}")

    # 5. 清理现场 (防止影响后续测试)
    engine.enPassantSquare = None
    engine.enPassantColor = None

if __name__ == "__main__":
    test_before_refactor()
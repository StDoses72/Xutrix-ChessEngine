import engine

def test_after_refactor():
    print("=== 🚀 运行验证测试 (改代码后) ===")
    
    # 1. 准备棋盘 (和之前一模一样)
    board = [['.'] * 8 for _ in range(8)]
    board[3][4] = 'P'
    board[3][3] = 'p'
    
    # 2. 【关键】不再设置 Global，而是准备参数
    ep_sq_param = 'd6'
    ep_col_param = 'black'
    
    # 确保 Global 是脏的或者空的，验证函数真的没读它
    engine.enPassantSquare = None 
    
    print(f"传入参数: enPassantSq={ep_sq_param}, Color={ep_col_param}")
    
    try:
        # 3. 调用新接口 (传入 4 个参数)
        moves = engine.generatePawnMoves(board, 'e5', ep_sq_param, ep_col_param)
        
        # 4. 验证
        if 'd6' in moves:
            print("✅ [PASS] 新逻辑成功生成了过路兵吃 d6")
        else:
            print(f"❌ [FAIL] 新逻辑丢失了过路兵！当前生成: {moves}")
            
    except TypeError as e:
        print("❌ [CRASH] 函数签名没改对？报错信息：", e)

if __name__ == "__main__":
    test_after_refactor()
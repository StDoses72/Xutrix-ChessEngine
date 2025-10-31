import string
import copy

castling_rights = {
    'white_king_moved': False,
    'white_rook_a_moved': False,
    'white_rook_h_moved': False,
    'black_king_moved': False,
    'black_rook_a_moved': False,
    'black_rook_h_moved': False
}


def algebraicToIndex(sqaure):
    row = int(sqaure[-1])
    letter = sqaure[0]
    col = ord(letter)-ord('a')
    row=8-row
    return(row,col)
def indexToAlgebraic(row, col):
    file = chr(ord('a') + col)
    rank = str(8 - row)
    return file + rank

def printBoard(board):
    for row in range(len(board)):
        print(str(8-row)+' ',end='')
        print(' '.join(board[row]))
    endRow = [' ','a','b','c','d','e','f','g','h']
    print(' '.join(endRow))
    
def getPiece(board,row,col):
    return board[row][col]

def setPiece(board,square,piece):
    row,col=algebraicToIndex(square)
    board[row][col] = piece

def initializeBoard():
    board = [['.'] * 8 for _ in range(8)]
    board[0] = ['r','n','b','q','k','b','n','r']
    board[1] = ['p'] * 8
    board[6] = ['P'] * 8
    board[7] = ['R','N','B','Q','K','B','N','R']
    return board

def movePiece(board, fromSquare, toSquare):
    fromRow, fromCol = algebraicToIndex(fromSquare)
    toRow, toCol = algebraicToIndex(toSquare)
    piece = board[fromRow][fromCol]
    target = board[toRow][toCol]

    if piece == '.':
        print(f"No piece at {fromSquare}!")
        return
    if not isOpponent(piece, target) and target != '.':
        print('Illegal move: cannot capture your own piece!')
        return


    if target == 'R':
        if toSquare == 'a1':
            castling_rights['white_rook_a_moved'] = True
        elif toSquare == 'h1':
            castling_rights['white_rook_h_moved'] = True
    elif target == 'r':
        if toSquare == 'a8':
            castling_rights['black_rook_a_moved'] = True
        elif toSquare == 'h8':
            castling_rights['black_rook_h_moved'] = True

    if target == '.':
        print(f"{piece} moves from {fromSquare} to {toSquare}")
    else:
        print(f"{piece} captures {target} at {toSquare}")


    board[toRow][toCol] = piece
    board[fromRow][fromCol] = '.'


    if piece == 'P' and toRow == 0:
        board[toRow][toCol] = 'Q'
    elif piece == 'p' and toRow == 7:
        board[toRow][toCol] = 'q'


    if piece == 'K':
        castling_rights['white_king_moved'] = True
        if fromSquare == 'e1' and toSquare == 'g1':
            board[7][5] = 'R'; board[7][7] = '.'
        elif fromSquare == 'e1' and toSquare == 'c1':
            board[7][3] = 'R'; board[7][0] = '.'
    elif piece == 'k':
        castling_rights['black_king_moved'] = True
        if fromSquare == 'e8' and toSquare == 'g8':
            board[0][5] = 'r'; board[0][7] = '.'
        elif fromSquare == 'e8' and toSquare == 'c8':
            board[0][3] = 'r'; board[0][0] = '.'

    
    if piece == 'R':
        if fromSquare == 'a1':
            castling_rights['white_rook_a_moved'] = True
        elif fromSquare == 'h1':
            castling_rights['white_rook_h_moved'] = True
    elif piece == 'r':
        if fromSquare == 'a8':
            castling_rights['black_rook_a_moved'] = True
        elif fromSquare == 'h8':
            castling_rights['black_rook_h_moved'] = True
    
    
    
    
def isSquareAttacked(board, row, col, byColor):
    directions_bishop = [(-1,-1), (-1,1), (1,-1), (1,1)]
    directions_rook = [(-1,0), (1,0), (0,-1), (0,1)]
    directions_knight = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
    directions_king = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    
    if byColor == 'white':
        pawn_dirs = [(-1,-1), (-1,1)]
        pawn_char = 'P'
    else:
        pawn_dirs = [(1,-1), (1,1)]
        pawn_char = 'p'
    for dr, dc in pawn_dirs:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == pawn_char:
            return True

    
    knight_char = 'N' if byColor == 'white' else 'n'
    for dr, dc in directions_knight:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == knight_char:
            return True

    
    king_char = 'K' if byColor == 'white' else 'k'
    for dr, dc in directions_king:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == king_char:
            return True

    
    bishop_char = 'B' if byColor == 'white' else 'b'
    queen_char = 'Q' if byColor == 'white' else 'q'
    for dr, dc in directions_bishop:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            piece = board[r][c]
            if piece != '.':
                if piece == bishop_char or piece == queen_char:
                    return True
                break
            r += dr; c += dc

    
    rook_char = 'R' if byColor == 'white' else 'r'
    for dr, dc in directions_rook:
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            piece = board[r][c]
            if piece != '.':
                if piece == rook_char or piece == queen_char:
                    return True
                break
            r += dr; c += dc

    return False    


def generatePawnMoves(board, square):
    potentialMove = []
    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    drow = -1 if piece.isupper() else 1
    targetRow = fromRow + drow
    if not (0 <= targetRow < 8):
        return potentialMove

    
    for dcol in [-1, 1]:
        targetCol = fromCol + dcol
        if 0 <= targetCol < 8 and isOpponent(piece, board[targetRow][targetCol]):
            potentialMove.append(indexToAlgebraic(targetRow, targetCol))

    
    if board[targetRow][fromCol] == '.':
        potentialMove.append(indexToAlgebraic(targetRow, fromCol))
        
        startRow = 6 if piece.isupper() else 1
        if fromRow == startRow and board[targetRow + drow][fromCol] == '.':
            potentialMove.append(indexToAlgebraic(targetRow + drow, fromCol))

    return potentialMove

def generateKnightMoves(board,square):
    potentialMove = []
    fromRow,fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece=='.':
        return potentialMove
    directionList = [(1,2),(1,-2),(2,1),(2,-1),(-1,2),(-1,-2),(-2,1),(-2,-1)]
    for drow,dcol in directionList:
        if ((0 <= fromRow + drow < 8 and 0 <= fromCol + dcol < 8) and
        (board[fromRow+drow][fromCol+dcol]=='.' or isOpponent(piece,board[fromRow+drow][fromCol+dcol]))):
            toSquare = indexToAlgebraic(fromRow+drow, fromCol+dcol)
            potentialMove.append(toSquare)                
    return potentialMove

def generateSlidingPieceMoves(board,square,directionList):
    potentialMove = []
    fromRow,fromCol = algebraicToIndex(square)
    piece=board[fromRow][fromCol]
    
    for drow,dcol in directionList:
        tempRow,tempCol = fromRow,fromCol
        while True:
            tempRow+=drow
            tempCol+=dcol
            
            if not (0 <= tempRow < 8 and 0 <= tempCol < 8):
                break 
            tempSquare = board[tempRow][tempCol]
            if (tempSquare=='.'):
                toSquare = indexToAlgebraic(tempRow, tempCol)
                potentialMove.append(toSquare)
            elif not(isOpponent(piece,tempSquare)):
                break
            elif isOpponent(piece,tempSquare):
                toSquare = indexToAlgebraic(tempRow, tempCol)
                potentialMove.append(toSquare)
                break
            else:
                break
            
    return potentialMove

def generateBishopMoves(board,square):
    return generateSlidingPieceMoves(board,square,[(-1,-1),(-1,1),(1,-1),(1,1)])

def generateRookMoves(board,square):
    return generateSlidingPieceMoves(board,square,[(1,0),(-1,0),(0,1),(0,-1)])

def generateQueenMoves(board,square):
    return generateSlidingPieceMoves(board,square,[(1,0),(-1,0),(0,1),(0,-1),(-1,-1),(-1,1),(1,-1),(1,1)])
    
    
def generateKingMoves(board, square):
    potentialMove = []
    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    directionList = [(1, 0), (-1, 0), (0, 1), (0, -1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for drow, dcol in directionList:
        if (0 <= fromRow + drow < 8 and 0 <= fromCol + dcol < 8) and (
            board[fromRow + drow][fromCol + dcol] == '.' or isOpponent(piece, board[fromRow + drow][fromCol + dcol])
        ):
            toSquare = indexToAlgebraic(fromRow + drow, fromCol + dcol)
            potentialMove.append(toSquare)


    if piece == 'K' and not castling_rights['white_king_moved'] and not isKingChecked(board, 'white'):
        # 短易位
        if not castling_rights['white_rook_h_moved'] and board[7][7] == 'R':
            if board[7][5] == '.' and board[7][6] == '.':
                if not isSquareAttacked(board, 7, 5, 'black') and not isSquareAttacked(board, 7, 6, 'black'):
                    potentialMove.append('g1')
        # 长易位
        if not castling_rights['white_rook_a_moved'] and board[7][0] == 'R':
            if board[7][1] == '.' and board[7][2] == '.' and board[7][3] == '.':
                if not isSquareAttacked(board, 7, 3, 'black') and not isSquareAttacked(board, 7, 2, 'black'):
                    potentialMove.append('c1')

    if piece == 'k' and not castling_rights['black_king_moved'] and not isKingChecked(board, 'black'):
        # 短易位
        if not castling_rights['black_rook_h_moved'] and board[0][7] == 'r':
            if board[0][5] == '.' and board[0][6] == '.':
                if not isSquareAttacked(board, 0, 5, 'white') and not isSquareAttacked(board, 0, 6, 'white'):
                    potentialMove.append('g8')
        # 长易位
        if not castling_rights['black_rook_a_moved'] and board[0][0] == 'r':
            if board[0][1] == '.' and board[0][2] == '.' and board[0][3] == '.':
                if not isSquareAttacked(board, 0, 3, 'white') and not isSquareAttacked(board, 0, 2, 'white'):
                    potentialMove.append('c8')

    return potentialMove
    
def generateAllPseudoMoves(board, color):
    PseudoMoves = []
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece=='.':
                continue
            if color == 'white' and piece.islower():
                continue
            if color == 'black' and piece.isupper():
                continue
            piecetype = piece.lower()
            square = indexToAlgebraic(row,col)
            if piecetype == 'p':
                moveList = generatePawnMoves(board,square)
            elif piecetype == 'n':
                moveList = generateKnightMoves(board,square)
            elif piecetype == 'b':
                moveList = generateBishopMoves(board,square)
            elif piecetype == 'r':
                moveList = generateRookMoves(board,square)
            elif piecetype == 'q':
                moveList = generateQueenMoves(board,square)
            elif piecetype == 'k':
                moveList = generateKingMoves(board,square)
            
            for toSquare in moveList:
                PseudoMoves.append((square,toSquare))
    return PseudoMoves
                
            
            
def isKingChecked(board, color):
    kingChar = 'K' if color == 'white' else 'k'
    for row in range(8):
        for col in range(8):
            if board[row][col] == kingChar:
                kingRow, kingCol = row, col
                opponentColor = 'black' if color == 'white' else 'white'
                return isSquareAttacked(board, kingRow, kingCol, opponentColor)
    return False

def generateAlllegalMoves(board, color):
    legalMoves = []
    PseudoMoves = []
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece=='.':
                continue
            if color == 'white' and piece.islower():
                continue
            if color == 'black' and piece.isupper():
                continue
            piecetype = piece.lower()
            square = indexToAlgebraic(row,col)
            if piecetype == 'p':
                moveList = generatePawnMoves(board,square)
            elif piecetype == 'n':
                moveList = generateKnightMoves(board,square)
            elif piecetype == 'b':
                moveList = generateBishopMoves(board,square)
            elif piecetype == 'r':
                moveList = generateRookMoves(board,square)
            elif piecetype == 'q':
                moveList = generateQueenMoves(board,square)
            elif piecetype == 'k':
                moveList = generateKingMoves(board,square)
            
            for toSquare in moveList:
                PseudoMoves.append((square,toSquare))
    for fromSquare,toSquare in PseudoMoves:
        newboard = makeMove(board,fromSquare,toSquare)
        if not isKingChecked(newboard,color):
            legalMoves.append((fromSquare,toSquare))
    return legalMoves


def makeMove(board, fromSquare, toSquare):
    tempboard = copy.deepcopy(board)
    fromRow, fromCol = algebraicToIndex(fromSquare)
    toRow, toCol = algebraicToIndex(toSquare)
    piece = tempboard[fromRow][fromCol]

    tempboard[toRow][toCol] = piece
    tempboard[fromRow][fromCol] = '.'


    if piece == 'P' and toRow == 0:
        tempboard[toRow][toCol] = 'Q'
    elif piece == 'p' and toRow == 7:
        tempboard[toRow][toCol] = 'q'


    if piece == 'K':
        castling_rights['white_king_moved'] = True
        if fromSquare == 'e1' and toSquare == 'g1':  # 短易位
            tempboard[7][5] = 'R'
            tempboard[7][7] = '.'
        elif fromSquare == 'e1' and toSquare == 'c1':  # 长易位
            tempboard[7][3] = 'R'
            tempboard[7][0] = '.'
    elif piece == 'k':
        castling_rights['black_king_moved'] = True
        if fromSquare == 'e8' and toSquare == 'g8':
            tempboard[0][5] = 'r'
            tempboard[0][7] = '.'
        elif fromSquare == 'e8' and toSquare == 'c8':
            tempboard[0][3] = 'r'
            tempboard[0][0] = '.'


    if piece == 'R':
        if fromSquare == 'a1':
            castling_rights['white_rook_a_moved'] = True
        elif fromSquare == 'h1':
            castling_rights['white_rook_h_moved'] = True
    elif piece == 'r':
        if fromSquare == 'a8':
            castling_rights['black_rook_a_moved'] = True
        elif fromSquare == 'h8':
            castling_rights['black_rook_h_moved'] = True

    return tempboard
    
def evaluateBoard(board):
    pieceValue = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0,
                'p': -1, 'n': -3, 'b': -3, 'r': -5, 'q': -9, 'k': 0}
    score = 0
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece != '.':
                score+=pieceValue[piece]
    return score

def minimax(board,depth,maximizingPlayer):
    if depth == 0:
        return evaluateBoard(board)
    color = 'white' if maximizingPlayer else 'black'
    moves = generateAlllegalMoves(board,color) 
    if moves == []:
        return evaluateBoard(board)
    
    if maximizingPlayer:
        maxEval = -float('inf')
        for fromSquare,toSquare in moves:
            newboard = makeMove(board,fromSquare,toSquare)
            eval = minimax(newboard,depth-1,False)
            maxEval = max(eval,maxEval)
        return maxEval
    else:
        minEval = float('inf')
        for fromSquare,toSquare in moves:
            newboard = makeMove(board,fromSquare,toSquare)
            eval = minimax(newboard,depth-1,True)
            minEval = min(eval,minEval)
        return minEval
        
def findBestMove(board,color,depth):
    bestMove = None
    maximizingPlayer = True if color == 'white' else False
    bestScore = -float('inf') if maximizingPlayer else float('inf')
    moves = generateAlllegalMoves(board,color)
    
    for fromSquare,toSquare in moves:
        newboard = makeMove(board,fromSquare,toSquare)
        futureScore = minimax(newboard,depth-1,not maximizingPlayer)
        if maximizingPlayer:
            if bestScore<futureScore:
                bestScore = futureScore
                bestMove = (fromSquare,toSquare)
        elif not maximizingPlayer:
            if bestScore>futureScore:
                bestScore = futureScore
                bestMove = (fromSquare,toSquare)
        else:
            pass
    return bestMove
    
def isOpponent(piece1,piece2):
    if piece1.isupper():
        if piece2.islower():
            return True
    elif piece1.islower():
        if piece2.isupper():
            return True
    return False

def main():
    board = initializeBoard()
    printBoard(board)
    numOfSteps = 0
    while True:
        color = 'white' if numOfSteps%2 == 0 else 'black'
        print(findBestMove(board,color,4))
        move = input("请输入你的走法（例如 e2 e4，或输入 q 退出）：")
        if move.lower() == 'q':
            break
        try:
            fromSq, toSq = move.split()
            movePiece(board, fromSq, toSq)
            printBoard(board)
            numOfSteps+=1
            
        except:
            print("输入格式错误！请用类似 e2 e4 的形式。")
            
main()


















############################################################################################################################################################
# def test_allMoves():
#     board = initializeBoard()
#     whiteMoves = generateAllLegalMoves(board, 'white')
#     blackMoves = generateAllLegalMoves(board, 'black')
#     print("White:", len(whiteMoves), "moves")
#     print("Black:", len(blackMoves), "moves")
#     print("Example white moves:", whiteMoves[:10])
    
# test_allMoves()
# def test_slidingPieces():
#     print("=== Sliding Piece Test ===")

#     # 空棋盘
#     board = [['.'] * 8 for _ in range(8)]
#     board[4][3] = 'Q'  # Queen at d4
#     print("Queen d4:", sorted(generateQueenMoves(board, 'd4')))

#     board[4][3] = 'R'  # Rook at d4
#     print("Rook d4:", sorted(generateRookMoves(board, 'd4')))

#     board[4][3] = 'B'  # Bishop at d4
#     print("Bishop d4:", sorted(generateBishopMoves(board, 'd4')))

# test_slidingPieces()

# def test_rook_moves():
#     print("=== Rook General Test ===")

#     # 1️⃣ 空棋盘
#     board = [['.'] * 8 for _ in range(8)]
#     board[4][3] = 'R'  # d4
#     print("Rook at d4 (empty):", sorted(generateRookMoves(board, 'd4')))

#     # 2️⃣ 被己方兵挡住
#     board = initializeBoard()
#     print("Rook at a1 (blocked):", generateRookMoves(board, 'a1'))  # []

#     # 3️⃣ 敌人阻挡
#     board = [['.'] * 8 for _ in range(8)]
#     board[4][3] = 'R'
#     board[4][6] = 'p'
#     print("Rook at d4, enemy at g4:", generateRookMoves(board, 'd4'))

#     # 4️⃣ 边界格
#     board = [['.'] * 8 for _ in range(8)]
#     board[0][0] = 'R'
#     print("Rook at a8:", generateRookMoves(board, 'a8'))

#     # 5️⃣ 混合阻挡
#     board = [['.'] * 8 for _ in range(8)]
#     board[3][3] = 'R'  # d5
#     board[3][6] = 'p'  # g5 (敌)
#     board[3][1] = 'P'  # b5 (友)
#     print("Rook at d5, mix block:", generateRookMoves(board, 'd5'))
# test_rook_moves()
# def test_generateBishopMoves_general():
#     print("=== General Bishop Move Test ===")

#     # Helper to visualize test results
#     def show_result(name, moves, expected=None):
#         print(f"\n{name}")
#         print("  moves:", sorted(moves))
#         if expected is not None:
#             print("  expected:", sorted(expected))
#             if sorted(moves) == sorted(expected):
#                 print("  ✅ PASS")
#             else:
#                 print("  ❌ FAIL")

#     # 1️⃣ 空棋盘测试：主教在 d4
#     board = [['.'] * 8 for _ in range(8)]
#     board[4][3] = 'B'  # d4
#     moves = generateBishopMoves(board, 'd4')
#     expected = [
#         # ↖
#         'c3','b2','a1',
#         # ↗
#         'e5','f6','g7','h8',
#         # ↙
#         'c5','b6','a7',
#         # ↘
#         'e3','f2','g1'
#     ]
#     show_result("Case 1: empty board, bishop at d4", moves, expected)

#     # 2️⃣ 己方子阻挡：主教在 c1，被兵挡在 d2
#     board = initializeBoard()
#     moves = generateBishopMoves(board, 'c1')
#     expected = []  # 被 d2 白兵挡住
#     show_result("Case 2: blocked by own pawn", moves, expected)

#     # 3️⃣ 敌方子可吃：清空棋盘，放主教和敌兵
#     board = [['.'] * 8 for _ in range(8)]
#     board[4][3] = 'B'   # d4
#     board[6][5] = 'p'   # f2 (敌人)
#     moves = generateBishopMoves(board, 'd4')
#     expected = ['c3','b2','a1','e5','f6','g7','h8','e3','f2','c5','b6','a7']
#     show_result("Case 3: enemy on diagonal (should capture f2)", moves, expected)

#     # 4️⃣ 边界格测试：主教在 a1
#     board = [['.'] * 8 for _ in range(8)]
#     board[7][0] = 'B'
#     moves = generateBishopMoves(board, 'a1')
#     expected = ['b2','c3','d4','e5','f6','g7','h8']
#     show_result("Case 4: bishop at a1", moves, expected)

#     # 5️⃣ 混合测试：主教被敌人挡在一个方向，被己方挡在另一个方向
#     board = [['.'] * 8 for _ in range(8)]
#     board[3][3] = 'B'  # d5
#     board[1][1] = 'p'  # b7 敌人
#     board[5][5] = 'P'  # f3 自己人
#     moves = generateBishopMoves(board, 'd5')
#     expected = ['c4','b3','a2','e6','f7','g8','c6','b7','e4']  # b7吃掉，但不越过；f3挡住
#     show_result("Case 5: mixed blocking", moves, expected)

#     print("\n=== All Bishop Tests Completed ===")
    
    
# test_generateBishopMoves_general()

# def test_pawn_double_step_block():
#     print("=== Pawn Double Step Blocking Test ===")
#     board = initializeBoard()
#     printBoard(board)

#     # ✅ Case 1: 正常开局 e2 -> ['e3', 'e4']
#     print("\nCase 1: e2 起始行（前方空）")
#     print("Expected: ['e3', 'e4']")
#     print("Actual:  ", generatePawnMoves(board, 'e2'))

#     # ✅ Case 2: e3 被挡 —— 我们人为放个棋子挡在 e3
#     print("\nCase 2: e3 被挡（前一格非空）")
#     board[5][4] = 'p'   # 放一个黑兵挡住 e3 （行=5, 列=4）
#     printBoard(board)
#     print("Expected: []  或 ['e3'] 但绝不应出现 e4")
#     print("Actual:  ", generatePawnMoves(board, 'e2'))

#     # ✅ Case 3: 黑兵正常（d7）
#     print("\nCase 3: 黑兵 d7（前方空）")
#     board = initializeBoard()
#     print("Expected: ['d6', 'd5']")
#     print("Actual:  ", generatePawnMoves(board, 'd7'))

#     # ✅ Case 4: 黑兵 d7 被挡（d6 有白兵）
#     print("\nCase 4: 黑兵 d7 被挡（d6 非空）")
#     board = initializeBoard()
#     board[2][3] = 'P'   # 行2是 rank=6 的格子，挡住 d6
#     printBoard(board)
#     print("Expected: []  或 ['d6'] 但绝不应出现 d5")
#     print("Actual:  ", generatePawnMoves(board, 'd7'))

#     print("\n=== Test Completed ===")
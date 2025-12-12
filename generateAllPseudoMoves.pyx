def generatePawnMoves(board, square):
    global enPassantSquare,enPassantColor
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



    if enPassantSquare != None:
        enPassantRow, enPassantCol = algebraicToIndex(enPassantSquare)
        if enPassantColor == 'white':
            if piece == 'p' and fromRow == enPassantRow-1 and (fromCol == enPassantCol-1 or fromCol == enPassantCol+1):
                potentialMove.append(enPassantSquare)
        elif enPassantColor == 'black':
            if piece == 'P' and fromRow == enPassantRow+1 and (fromCol == enPassantCol-1 or fromCol == enPassantCol+1):
                potentialMove.append(enPassantSquare)
            
    
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
    global castling_rights
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
                if (isSquareAttacked(board, 7, 5, 'black')==0) and (isSquareAttacked(board, 7, 6, 'black')==0):
                    potentialMove.append('g1')
        # 长易位
        if not castling_rights['white_rook_a_moved'] and board[7][0] == 'R':
            if board[7][1] == '.' and board[7][2] == '.' and board[7][3] == '.':
                if (isSquareAttacked(board, 7, 3, 'black')==0) and (isSquareAttacked(board, 7, 2, 'black')==0):
                    potentialMove.append('c1')

    if piece == 'k' and not castling_rights['black_king_moved'] and not isKingChecked(board, 'black'):
        # 短易位
        if not castling_rights['black_rook_h_moved'] and board[0][7] == 'r':
            if board[0][5] == '.' and board[0][6] == '.':
                if (isSquareAttacked(board, 0, 5, 'white')==0) and (isSquareAttacked(board, 0, 6, 'white')==0):
                    potentialMove.append('g8')  
        # 长易位
        if not castling_rights['black_rook_a_moved'] and board[0][0] == 'r':
            if board[0][1] == '.' and board[0][2] == '.' and board[0][3] == '.':
                if (isSquareAttacked(board, 0, 3, 'white')==0) and (isSquareAttacked(board, 0, 2, 'white')==0):
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
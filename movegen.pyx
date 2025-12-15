# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import isSquareAttacked

cpdef tuple algebraicToIndex(str square):
    # square like "e2"
    cdef int file = ord(square[0]) - 97   # 'a' = 97
    cdef int rank = ord(square[1]) - 49   # '1' = 49
    return (7 - rank, file)

cpdef str indexToAlgebraic(int row, int col):
    # row 0 is rank 8, row 7 is rank 1
    return chr(col + 97) + chr((7 - row) + 49)

cpdef bint isOpponent(object piece, object target):
    if target == '.':
        return False
    # piece upper => white, target lower => black
    if piece <= 'Z':
        return target > 'Z'
    else:
        return target <= 'Z'

cpdef bint isKingChecked(list board, str color):
    cdef object kingChar = 'K' if color == 'white' else 'k'
    cdef int row, col
    for row in range(8):
        for col in range(8):
            if board[row][col] == kingChar:
                if color == 'white':
                    return isSquareAttacked.isSquareAttacked(board, row, col, 'black') > 0
                else:
                    return isSquareAttacked.isSquareAttacked(board, row, col, 'white') > 0
    return False

cpdef list generatePawnMoves(list board, str square, object enPassantSquare, object enPassantColor):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, drow, targetRow, targetCol, enPassantRow, enPassantCol, startRow
    cdef object piece

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    drow = -1 if piece <= 'Z' else 1
    targetRow = fromRow + drow
    if targetRow < 0 or targetRow >= 8:
        return potentialMove

    targetCol = fromCol - 1
    if targetCol >= 0 and isOpponent(piece, board[targetRow][targetCol]):
        potentialMove.append(indexToAlgebraic(targetRow, targetCol))

    targetCol = fromCol + 1
    if targetCol < 8 and isOpponent(piece, board[targetRow][targetCol]):
        potentialMove.append(indexToAlgebraic(targetRow, targetCol))

    if enPassantSquare is not None:
        enPassantRow, enPassantCol = algebraicToIndex(enPassantSquare)
        if enPassantColor == 'white':
            if piece == 'p' and fromRow == enPassantRow - 1 and (fromCol == enPassantCol - 1 or fromCol == enPassantCol + 1):
                potentialMove.append(enPassantSquare)
        elif enPassantColor == 'black':
            if piece == 'P' and fromRow == enPassantRow + 1 and (fromCol == enPassantCol - 1 or fromCol == enPassantCol + 1):
                potentialMove.append(enPassantSquare)

    if board[targetRow][fromCol] == '.':
        potentialMove.append(indexToAlgebraic(targetRow, fromCol))

        startRow = 6 if piece <= 'Z' else 1
        if fromRow == startRow and board[targetRow + drow][fromCol] == '.':
            potentialMove.append(indexToAlgebraic(targetRow + drow, fromCol))

    return potentialMove
    

cpdef list generateKnightMoves(list board, str square):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, r, c, i
    cdef object piece

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    cdef int OFF[8][2]
    OFF[0][0] = 1;  OFF[0][1] = 2
    OFF[1][0] = 1;  OFF[1][1] = -2
    OFF[2][0] = 2;  OFF[2][1] = 1
    OFF[3][0] = 2;  OFF[3][1] = -1
    OFF[4][0] = -1; OFF[4][1] = 2
    OFF[5][0] = -1; OFF[5][1] = -2
    OFF[6][0] = -2; OFF[6][1] = 1
    OFF[7][0] = -2; OFF[7][1] = -1

    for i in range(8):
        r = fromRow + OFF[i][0]
        c = fromCol + OFF[i][1]
        if r >= 0 and r < 8 and c >= 0 and c < 8:
            if board[r][c] == '.' or isOpponent(piece, board[r][c]):
                potentialMove.append(indexToAlgebraic(r, c))

    return potentialMove


cpdef list generateBishopMoves(list board, str square):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, drow, dcol, tempRow, tempCol, i
    cdef object piece, tempSquare

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    cdef int OFF[4][2]
    OFF[0][0] = 1;  OFF[0][1] = 1
    OFF[1][0] = 1;  OFF[1][1] = -1
    OFF[2][0] = -1; OFF[2][1] = 1
    OFF[3][0] = -1; OFF[3][1] = -1

    for i in range(4):
        drow = OFF[i][0]
        dcol = OFF[i][1]

        tempRow = fromRow + drow
        tempCol = fromCol + dcol

        while 0 <= tempRow < 8 and 0 <= tempCol < 8:
            tempSquare = board[tempRow][tempCol]
            if tempSquare == '.':
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
            elif isOpponent(piece, tempSquare):
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
                break
            else:
                break

            tempRow += drow
            tempCol += dcol

    return potentialMove

cpdef list generateRookMoves(list board, str square):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, drow, dcol, tempRow, tempCol, i
    cdef object piece, tempSquare

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    cdef int OFF[4][2]
    OFF[0][0] = 1;  OFF[0][1] = 0
    OFF[1][0] = 0;  OFF[1][1] = 1
    OFF[2][0] = -1; OFF[2][1] = 0
    OFF[3][0] = 0; OFF[3][1] = -1


    for i in range(4):
        drow = OFF[i][0]
        dcol = OFF[i][1]

        tempRow = fromRow + drow
        tempCol = fromCol + dcol

        while 0 <= tempRow < 8 and 0 <= tempCol < 8:
            tempSquare = board[tempRow][tempCol]
            if tempSquare == '.':
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
            elif isOpponent(piece, tempSquare):
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
                break
            else:
                break

            tempRow += drow
            tempCol += dcol

    return potentialMove




cpdef list generateQueenMoves(list board, str square):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, drow, dcol, tempRow, tempCol, i
    cdef object piece, tempSquare

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    cdef int OFF[8][2]
    OFF[0][0] = 1;  OFF[0][1] = 0
    OFF[1][0] = 0;  OFF[1][1] = 1
    OFF[2][0] = -1; OFF[2][1] = 0
    OFF[3][0] = 0; OFF[3][1] = -1
    OFF[4][0] = 1;  OFF[4][1] = 1
    OFF[5][0] = 1;  OFF[5][1] = -1
    OFF[6][0] = -1; OFF[6][1] = 1
    OFF[7][0] = -1; OFF[7][1] = -1

    for i in range(8):
        drow = OFF[i][0]
        dcol = OFF[i][1]

        tempRow = fromRow + drow
        tempCol = fromCol + dcol

        while 0 <= tempRow < 8 and 0 <= tempCol < 8:
            tempSquare = board[tempRow][tempCol]
            if tempSquare == '.':
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
            elif isOpponent(piece, tempSquare):
                potentialMove.append(indexToAlgebraic(tempRow, tempCol))
                break
            else:
                break

            tempRow += drow
            tempCol += dcol

    return potentialMove


    
cpdef list generateKingMoves(list board, str square, dict castling_rights):
    cdef list potentialMove = []
    cdef int fromRow, fromCol, i, drow, dcol, r, c
    cdef object piece, target

    fromRow, fromCol = algebraicToIndex(square)
    piece = board[fromRow][fromCol]
    if piece == '.':
        return potentialMove

    cdef int OFF[8][2]
    OFF[0][0] = 1;  OFF[0][1] = 0
    OFF[1][0] = 0;  OFF[1][1] = 1
    OFF[2][0] = -1; OFF[2][1] = 0
    OFF[3][0] = 0;  OFF[3][1] = -1
    OFF[4][0] = 1;  OFF[4][1] = 1
    OFF[5][0] = 1;  OFF[5][1] = -1
    OFF[6][0] = -1; OFF[6][1] = 1
    OFF[7][0] = -1; OFF[7][1] = -1

    for i in range(8):
        drow = OFF[i][0]
        dcol = OFF[i][1]
        r = fromRow + drow
        c = fromCol + dcol
        if r >= 0 and r < 8 and c >= 0 and c < 8:
            target = board[r][c]
            if target == '.' or isOpponent(piece, target):
                potentialMove.append(indexToAlgebraic(r, c))

    # White castling
    if piece == 'K' and (not castling_rights.get('white_king_moved', False)) and (not isKingChecked(board, 'white')):
        # short
        if (not castling_rights.get('white_rook_h_moved', False)) and board[7][7] == 'R':
            if board[7][5] == '.' and board[7][6] == '.':
                if isSquareAttacked.isSquareAttacked(board, 7, 5, 'black') == 0 and isSquareAttacked.isSquareAttacked(board, 7, 6, 'black') == 0:
                    potentialMove.append('g1')
        # long
        if (not castling_rights.get('white_rook_a_moved', False)) and board[7][0] == 'R':
            if board[7][1] == '.' and board[7][2] == '.' and board[7][3] == '.':
                if isSquareAttacked.isSquareAttacked(board, 7, 3, 'black') == 0 and isSquareAttacked.isSquareAttacked(board, 7, 2, 'black') == 0:
                    potentialMove.append('c1')

    # Black castling
    if piece == 'k' and (not castling_rights.get('black_king_moved', False)) and (not isKingChecked(board, 'black')):
        # short
        if (not castling_rights.get('black_rook_h_moved', False)) and board[0][7] == 'r':
            if board[0][5] == '.' and board[0][6] == '.':
                if isSquareAttacked.isSquareAttacked(board, 0, 5, 'white') == 0 and isSquareAttacked.isSquareAttacked(board, 0, 6, 'white') == 0:
                    potentialMove.append('g8')
        # long
        if (not castling_rights.get('black_rook_a_moved', False)) and board[0][0] == 'r':
            if board[0][1] == '.' and board[0][2] == '.' and board[0][3] == '.':
                if isSquareAttacked.isSquareAttacked(board, 0, 3, 'white') == 0 and isSquareAttacked.isSquareAttacked(board, 0, 2, 'white') == 0:
                    potentialMove.append('c8')

    return potentialMove

        
cpdef list generateAllPseudoMoves(list board, str color):
    global enPassantSquare, enPassantColor, castling_rights
    cdef list PseudoMoves = []
    cdef int row, col
    cdef object piece
    cdef str square, toSquare
    cdef list moveList

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == '.':
                continue

            # 颜色过滤：避免 islower/isupper（少 Python 调用）
            if color == 'white':
                if piece > 'Z':   # 小写 => 黑子
                    continue
            else:  # color == 'black'
                if piece <= 'Z':  # 大写 => 白子
                    continue

            square = indexToAlgebraic(row, col)
            moveList = []

            # 直接用 piece 判断类型（避免 .lower()）
            if piece == 'P' or piece == 'p':
                moveList = generatePawnMoves(board, square, enPassantSquare, enPassantColor)
            elif piece == 'N' or piece == 'n':
                moveList = generateKnightMoves(board, square)
            elif piece == 'B' or piece == 'b':
                moveList = generateBishopMoves(board, square)
            elif piece == 'R' or piece == 'r':
                moveList = generateRookMoves(board, square)
            elif piece == 'Q' or piece == 'q':
                moveList = generateQueenMoves(board, square)
            elif piece == 'K' or piece == 'k':
                moveList = generateKingMoves(board, square, castling_rights)

            for toSquare in moveList:
                PseudoMoves.append((square, toSquare))

    return PseudoMoves

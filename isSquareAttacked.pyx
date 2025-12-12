# cython: boundscheck=False, wraparound=False, nonecheck=False

pawnDirWhite = ((-1, -1), (-1, 1))
pawnDirBlack = ((1, -1), (1, 1))

knightDir = (
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2)
)

kingDir = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
)

bishopDir = ((1, 1), (-1, 1), (-1, -1), (1, -1))
rookDir   = ((0, 1), (1, 0), (-1, 0), (0, -1))

cpdef int isSquareAttacked(list board, int row, int col, str byColor):
    cdef int dr, dc, r, c
    cdef str piece,pawnChar,knightChar,kingChar,bishopChar,queenChar,rookChar
    cdef int count = 0


    if byColor == 'white':
        pawnChar = 'P'
    else:
        pawnChar = 'p'
    for i in range(2):
        if byColor =='white':
            dr = pawnDirBlack[i][0]
            dc = pawnDirBlack[i][1]
        else:
            dr = pawnDirWhite[i][0]
            dc = pawnDirWhite[i][1]
        r = dr + row
        c = dc + col
        if 0 <= r < 8 and 0 <= c < 8:
            if board[r][c] == pawnChar:
                count+=1
    


    if byColor == 'white':
        knightChar = 'N'
    else:
        knightChar = 'n'
    
    for i in range(8):
        dr = knightDir[i][0]
        dc = knightDir[i][1]
        r = dr + row
        c = dc + col
        if 0 <= r < 8 and 0 <= c < 8:
            if board[r][c] == knightChar:
                count+=1


    if byColor == 'white':
        kingChar = 'K'
    else:
        kingChar = 'k'
    for i in range(8):
        dr = kingDir[i][0]
        dc = kingDir[i][1]
        r = dr + row
        c = dc + col
        if 0 <= r < 8 and 0 <= c < 8:
            if board[r][c] == kingChar:
                count+=1
        
        

    if byColor == 'white':
        bishopChar = 'B'
    else:
        bishopChar = 'b'

    queenChar = 'Q' if byColor == 'white' else 'q'

    for i in range(4):
        dr = bishopDir[i][0]
        dc = bishopDir[i][1]
        r = row + dr
        c = col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            piece = board[r][c]
            if piece != '.':
                if piece == bishopChar or piece == queenChar:
                    count+=1
                break
            r += dr; c += dc


    rookChar = 'R' if byColor == 'white' else 'r'

    for i in range(4):
        dr = rookDir[i][0]
        dc = rookDir[i][1]
        r = row + dr
        c = col + dc
        while 0<=r<8 and 0<=c<8:
            piece = board[r][c]
            if piece != '.':
                if piece == rookChar or piece == queenChar:
                    count+=1
                break
            r+=dr; c += dc


    return count






import string
import copy
import json
import numpy as np
import os
from collections import deque
import random
import time
from isSquareAttacked import isSquareAttacked
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

piece_files = {
    "p": "p_table_adjusted.json",
    "n": "n_table_adjusted.json",
    "b": "b_table_adjusted.json",
    "r": "r_table.json",
    "q": "q_table.json",
    "k": "k_table.json"
}

piece_paths = {
    piece: os.path.join(BASE_DIR, "piecePosition", filename)
    for piece, filename in piece_files.items()
}

pawnJsonPath   = piece_paths["p"]
knightJsonPath = piece_paths["n"]
bishopJsonPath = piece_paths["b"]
rookJsonPath   = piece_paths["r"]
queenJsonPath  = piece_paths["q"]
kingJsonPath   = piece_paths["k"]

kingEndPosition = np.array([
    [-50, -30, -30, -30, -30, -30, -30, -50],
    [-30, -10, -10, -10, -10, -10, -10, -30],
    [-30, -10,  20,  20,  20,  20, -10, -30],
    [-30, -10,  20,  40,  40,  20, -10, -30],
    [-30, -10,  20,  40,  40,  20, -10, -30],
    [-30, -10,  20,  20,  20,  20, -10, -30],
    [-30, -10, -10, -10, -10, -10, -10, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50]
    ])


castling_rights = {
    'white_king_moved': False,
    'white_rook_a_moved': False,
    'white_rook_h_moved': False,
    'black_king_moved': False,
    'black_rook_a_moved': False,
    'black_rook_h_moved': False
}
whiteKingCastled = False
blackKingCastled = False

enPassantSquare = None
enPassantColor = None

isWhiteQueenExist = True
isBlackQueenExist = True

pawnPosition = {'white':set(),
                'black':set()
}


centerWeights = np.array([
    [0, 0, 1, 1, 1, 1, 0, 0],
    [0, 1, 2, 2, 2, 2, 1, 0],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 4, 4, 3, 2, 1],
    [1, 2, 3, 3, 3, 3, 2, 1],
    [0, 1, 2, 2, 2, 2, 1, 0],
    [0, 0, 1, 1, 1, 1, 0, 0]
])


moveHistory = deque()




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
    global pawnPosition
    board = [['.'] * 8 for _ in range(8)]
    board[0] = ['r','n','b','q','k','b','n','r']
    board[1] = ['p'] * 8
    board[6] = ['P'] * 8
    board[7] = ['R','N','B','Q','K','B','N','R']
    pawnPosition['white']={'a2','b2','c2','d2','e2','f2','g2','h2'}
    pawnPosition['black']={'a7','b7','c7','d7','e7','f7','g7','h7'}
    return board

def movePiece(board, fromSquare, toSquare):#This is for user to use
    global isWhiteQueenExist, isBlackQueenExist,enPassantSquare,enPassantColor,pawnPosition,castling_rights,moveHistory
    setEnPassant = False
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

    if piece == 'P' or piece == 'p':
        if abs(fromRow - toRow)==2:
            if piece == 'P':
                enPassantColor = 'white'
                enPassantSquare = indexToAlgebraic(toRow+1,fromCol)
                setEnPassant = True
            else:
                enPassantColor = 'black'
                enPassantSquare = indexToAlgebraic(toRow-1,fromCol)
                setEnPassant = True
        elif toSquare == enPassantSquare:
            if piece == 'P' and enPassantColor == 'black':
                board[fromRow][toCol] = '.'
            elif piece == 'p' and enPassantColor == 'white':
                board[fromRow][toCol] = '.'
        

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

    if target == 'Q':
        isWhiteQueenExist = False
    if target == 'q':
        isBlackQueenExist = False
        
    #Officially do the move
    board[toRow][toCol] = piece
    board[fromRow][fromCol] = '.'
    
    #Update pawnPosition
    if piece == 'P':
        pawnPosition['white'].remove(fromSquare)
        pawnPosition['white'].add(toSquare)
        if toSquare in pawnPosition['black']:
            pawnPosition['black'].remove(toSquare)
    elif piece == 'p':
        pawnPosition['black'].remove(fromSquare)
        pawnPosition['black'].add(toSquare)
        if toSquare in pawnPosition['white']:
            pawnPosition['white'].remove(toSquare)
    
    if piece == 'P' and toRow == 0:
        board[toRow][toCol] = 'Q'
    elif piece == 'p' and toRow == 7:
        board[toRow][toCol] = 'q'


    if piece == 'K':
        if fromSquare == 'e1' and toSquare == 'g1' and board[7][7] == 'R' and castling_rights['white_king_moved']==False and castling_rights['white_rook_h_moved']==False:
            board[7][5] = 'R'; board[7][7] = '.'
        elif fromSquare == 'e1' and toSquare == 'c1' and board[7][0] == 'R' and castling_rights['white_king_moved']==False and castling_rights['white_rook_a_moved']==False:
            board[7][3] = 'R'; board[7][0] = '.'
        castling_rights['white_king_moved'] = True
    elif piece == 'k':
        if fromSquare == 'e8' and toSquare == 'g8' and board[0][7] == 'r' and not castling_rights['black_king_moved'] and not castling_rights['black_rook_h_moved']:
            board[0][5] = 'r'; board[0][7] = '.'
        elif fromSquare == 'e8' and toSquare == 'c8' and board[0][0] == 'r' and not castling_rights['black_king_moved'] and not castling_rights['black_rook_a_moved']:
            board[0][3] = 'r'; board[0][0] = '.'
        castling_rights['black_king_moved'] = True

    
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
    
    if not setEnPassant:
        enPassantColor = None
        enPassantSquare = None


def doMove(board,fromSquare,toSquare):#This is for engine simulation
    global isWhiteQueenExist, isBlackQueenExist,enPassantSquare,enPassantColor,pawnPosition,castling_rights,moveHistory,whiteKingCastled,blackKingCastled
    setEnPassant = False
    fromRow, fromCol = algebraicToIndex(fromSquare)
    toRow, toCol = algebraicToIndex(toSquare)
    piece = board[fromRow][fromCol]
    target = board[toRow][toCol]

    snapshot = {'from':fromSquare,
                'to':toSquare,
                'movedPiece':piece,
                'capturedPiece':target,
                'rights':copy.deepcopy(castling_rights),
                'enPassantSquare':enPassantSquare,
                'enPassantColor':enPassantColor,
                'pawnPosition':{'white':pawnPosition['white'].copy(),'black':pawnPosition['black'].copy()},
                'isBlackQueenExist':isBlackQueenExist,
                'isWhiteQueenExist':isWhiteQueenExist,
                'special': None,
                'whiteKingCastled':whiteKingCastled,
                'blackKingCastled':blackKingCastled
                
                }
    

    
        

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


    if target == 'Q':
        isWhiteQueenExist = False
    if target == 'q':
        isBlackQueenExist = False
        
        
    #Enpassant
    if piece == 'P' or piece == 'p':
        if abs(fromRow - toRow)==2:
            if piece == 'P':
                enPassantColor = 'white'
                enPassantSquare = indexToAlgebraic(toRow+1,fromCol)
                setEnPassant = True
            else:
                enPassantColor = 'black'
                enPassantSquare = indexToAlgebraic(toRow-1,fromCol)
                setEnPassant = True
                
        elif toSquare == enPassantSquare:
            if piece == 'P' and enPassantColor == 'black':
                pawnPosition['black'].remove(indexToAlgebraic(fromRow,toCol))
                board[fromRow][toCol] = '.'
            elif piece == 'p' and enPassantColor == 'white':
                pawnPosition['white'].remove(indexToAlgebraic(fromRow,toCol))
                board[fromRow][toCol] = '.'
                
                
    #Officially do the move
    board[toRow][toCol] = piece
    board[fromRow][fromCol] = '.'
    

    
    #Update pawnPosition
    if piece == 'P':
        pawnPosition['white'].remove(fromSquare)
        pawnPosition['white'].add(toSquare)
        if toSquare in pawnPosition['black']:
            pawnPosition['black'].remove(toSquare)
            
    elif piece == 'p':
        pawnPosition['black'].remove(fromSquare)
        pawnPosition['black'].add(toSquare)
        if toSquare in pawnPosition['white']:
            pawnPosition['white'].remove(toSquare)
    
    
    #Do not need to restore in undo
    if piece == 'P' and toRow == 0:
        board[toRow][toCol] = 'Q'
    elif piece == 'p' and toRow == 7:
        board[toRow][toCol] = 'q'

    #Castling
    if piece == 'K':
        if fromSquare == 'e1' and toSquare == 'g1' and board[7][7] == 'R' and castling_rights['white_king_moved']==False and castling_rights['white_rook_h_moved']==False:
            snapshot['special'] = 'wk'
            board[7][5] = 'R'; board[7][7] = '.'
            whiteKingCastled = True
            
        elif fromSquare == 'e1' and toSquare == 'c1' and board[7][0] == 'R' and castling_rights['white_king_moved']==False and castling_rights['white_rook_a_moved']==False:
            snapshot['special'] = 'wq'
            board[7][3] = 'R'; board[7][0] = '.'
            whiteKingCastled = True
        castling_rights['white_king_moved'] = True
    elif piece == 'k':
        if fromSquare == 'e8' and toSquare == 'g8' and board[0][7] == 'r' and not castling_rights['black_king_moved'] and not castling_rights['black_rook_h_moved']:
            snapshot['special'] = 'bk'
            board[0][5] = 'r'; board[0][7] = '.'
            blackKingCastled = True
        elif fromSquare == 'e8' and toSquare == 'c8' and board[0][0] == 'r' and not castling_rights['black_king_moved'] and not castling_rights['black_rook_a_moved']:
            snapshot['special'] = 'bq'
            board[0][3] = 'r'; board[0][0] = '.'
            blackKingCastled = True
        castling_rights['black_king_moved'] = True

    #Global status change
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
    
    if not setEnPassant:
        enPassantColor = None
        enPassantSquare = None
    moveHistory.append(snapshot)





def undoMove(board):
    global isWhiteQueenExist, isBlackQueenExist,enPassantSquare,enPassantColor
    global pawnPosition,castling_rights,moveHistory,whiteKingCastled,blackKingCastled

    if len(moveHistory) == 0:
        return
    
    snapshot = moveHistory.pop()
    fromSq = snapshot["from"]
    toSq = snapshot["to"]
    fromRow, fromCol = algebraicToIndex(fromSq)
    toRow, toCol = algebraicToIndex(toSq)

    movedPiece = snapshot["movedPiece"]
    capturedPiece = snapshot["capturedPiece"]

    # 1) Restore board (including en-passant restores + castling rook move)
    if movedPiece in ('P','p') and toSq == snapshot['enPassantSquare']:
        if movedPiece == 'P' and snapshot['enPassantColor'] == 'black':
            board[fromRow][toCol] = 'p'
        elif movedPiece == 'p' and snapshot['enPassantColor'] == 'white':
            board[fromRow][toCol] = 'P'

    sp = snapshot['special']
    if sp == 'wk':
        board[7][4] = 'K'
        board[7][6] = '.'
        board[7][7] = 'R'
        board[7][5] = '.'
    elif sp == 'wq':
        board[7][4] = 'K'
        board[7][2] = '.'
        board[7][0] = 'R'
        board[7][3] = '.'

    elif sp == 'bk':
        board[0][4] = 'k'
        board[0][6] = '.'
        board[0][7] = 'r'
        board[0][5] = '.'
    elif sp == 'bq':
        board[0][4] = 'k'
        board[0][2] = '.'
        board[0][0] = 'r'
        board[0][3] = '.'

    # Restore the moved piece and captured piece
    board[fromRow][fromCol] = movedPiece
    board[toRow][toCol] = capturedPiece

    # 2) Restore castling rights
    castling_rights.clear()
    castling_rights.update(snapshot["rights"])

    # 3) Restore en passant
    enPassantSquare = snapshot["enPassantSquare"]
    enPassantColor = snapshot["enPassantColor"]

    # 4) Restore pawnPosition sets
    pawnPosition['white'] = snapshot['pawnPosition']['white'].copy()
    pawnPosition['black'] = snapshot['pawnPosition']['black'].copy()

    # 5) Restore queens
    isWhiteQueenExist = snapshot["isWhiteQueenExist"]
    isBlackQueenExist = snapshot["isBlackQueenExist"]

    # 6) Restore castled flags
    whiteKingCastled = snapshot["whiteKingCastled"]
    blackKingCastled = snapshot["blackKingCastled"]
    
    



    



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
                
            
            
def isKingChecked(board, color):
    kingChar = 'K' if color == 'white' else 'k'
    for row in range(8):
        for col in range(8):
            if board[row][col] == kingChar:
                kingRow, kingCol = row, col
                opponentColor = 'black' if color == 'white' else 'white'
                return (isSquareAttacked(board, kingRow, kingCol, opponentColor)>0)
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
        doMove(board,fromSquare,toSquare)
        if not isKingChecked(board,color):
            legalMoves.append((fromSquare,toSquare))
        undoMove(board)
        
    return legalMoves



    
def evaluateBoard(board,piecePositionMap,moves,mobilityHint=None):
    global isBlackQueenExist,isWhiteQueenExist,pawnPosition,whiteKingCastled,blackKingCastled
    
    score = 0
    
    pieceValue = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0,
                'p': -100, 'n': -320, 'b': -330, 'r': -500, 'q': -900, 'k': 0}
    
    isEndGame = not(isWhiteQueenExist and isBlackQueenExist)
    
    
    #For position computation
    pieceCoefficientInOpen = {'p':1.0,'P':1.0,'n':1.4,'N':1.4,'b':1.3,'B':1.3,
                              'r':0.8,'R':0.8,'q':0.5,'Q':0.5,'k':1.0,'K':1.0}
    pieceCoefficientInEnd = {'p':1.2,'P':1.2,'n':1.0,'N':1.0,'b':1.1,'B':1.1,
                              'r':1.0,'R':1.0,'q':0.5,'Q':0.5,'k':2.0,'K':2.0}
    piecePositionScoreCap = {'p':20,'n':30,'b':30,'q':10,'r':20,'k':20}
    pstScale = 0.3
    if isEndGame:
        pstScale = 0.15
    
    if isEndGame:
        piecePositionScoreCap['k'] = 60
        
    #For mobility computation
    pieceCoefficientMap = {'N':1.0,'B':1.0,'P':0.5,'R':0.8,'K':(0.3 if not isEndGame else 1),'Q':0.6}
    mobilityCap = {
    'N': 30,   
    'B': 40,   
    'R': 25,   
    'Q': 20,   
    'K': 15,   
    'P': 10    
}
    #Calculating the amount of move


    numWhite = len(generateAlllegalMoves(board,'white'))
    numBlack = len(generateAlllegalMoves(board,'black'))
    score += (numWhite-numBlack)*(0.6 if not isEndGame else 0.2)
    #return 0
    
    #Compute pawn structure score
    pawnStructureScore = computePawnStructure(board)
    score+=pawnStructureScore*(0.15 if not isEndGame else 0.25)
    #Looping over the board and calculate the score for each square
    for row in range(8):
        for col in range(8):
            
            piece = board[row][col]
            
            if piece != '.':
                #Calculating material score, which has the coefficient of 1.0
                score+=pieceValue[piece]
                
                
                #Calculating position score, which has the coefficient of 0.8
                if not isEndGame:
                    piecePositionScore = pstScale*pieceCoefficientInOpen[piece]*piecePositionMap[piece][row,col]
                    cap = piecePositionScoreCap[piece.lower()]
                    if piecePositionScore > cap:
                        piecePositionScore = cap
                    elif piecePositionScore < -cap:
                        piecePositionScore = -cap
                else:
                    if piece=='K':
                        piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap['Ke'][row,col]
                    elif piece=='k':
                        piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap['ke'][row,col]
                    else:
                        piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap[piece][row,col]
                    cap = piecePositionScoreCap[piece.lower()]
                    if piecePositionScore > cap:
                        piecePositionScore = cap
                    elif piecePositionScore < -cap:
                        piecePositionScore = -cap
                if piece.isupper():
                    score += piecePositionScore*0.8
                elif piece.islower():
                    score -= piecePositionScore*0.8

            #Compute for mobility score, which has the coefficient of (0.6 if not isEndGame else 0.2)
            fromSquare = indexToAlgebraic(row,col)
            if piece == 'P' or piece == 'p':
                moveForPiece = generatePawnMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['P']:
                    addingscore = mobilityCap['P']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
            elif piece == 'N' or piece == 'n':
                moveForPiece = generateKnightMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['N']:
                    addingscore = mobilityCap['N']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
            elif piece == 'B' or piece == 'b':
                moveForPiece = generateBishopMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['B']:
                    addingscore = mobilityCap['B']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
            elif piece == 'R' or piece == 'r':
                moveForPiece = generateRookMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['R']:
                    addingscore = mobilityCap['R']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
            elif piece == 'Q' or piece == 'q':
                moveForPiece = generateQueenMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['Q']:
                    addingscore = mobilityCap['Q']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
            elif piece == 'K' or piece == 'k':
                #Kings mobility
                moveForPiece = generateKingMoves(board,fromSquare)
                addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
                if addingscore >= mobilityCap['K']:
                    addingscore = mobilityCap['K']
                if piece.isupper():
                    score+=addingscore*(0.6 if not isEndGame else 0.2)
                else:
                    score-=addingscore*(0.6 if not isEndGame else 0.2)
                    
                #kingSafety
                surrounding = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
                friPieceAroundWhite = 0
                friPieceAroundBlack = 0
                for dr,dc in surrounding:
                    r = row+dr
                    c = col+dc
                    if (0<=r<8) and (0<=c<8):
                        pieceAround = board[r][c]
                        pieceAroundKingScore = {'P':10,'N':3,'B':3,'R':0.5,'Q':0,
                                                'p':-10,'n':-3,'b':-3,'r':-0.5,'q':0,}
                        if piece == 'K':
                            if pieceAround != '.'and not isOpponent(piece,pieceAround):
                                friPieceAroundWhite += 1
                                if not isEndGame:
                                    score+=pieceAroundKingScore[pieceAround]
                                
                        elif piece == 'k':
                            if pieceAround != '.'and not isOpponent(piece,pieceAround):
                                friPieceAroundBlack += 1
                                if not isEndGame:
                                    score+=pieceAroundKingScore[pieceAround]
                if isEndGame:
                    if friPieceAroundWhite > 3:
                        score -= (friPieceAroundWhite - 3) * 0.15
                    if friPieceAroundBlack > 3:
                        score += (friPieceAroundBlack - 3) * 0.15

    centerControl = computeCenterControl(board)
    #reward castle
    if whiteKingCastled: score += 40*(1.0 if not isEndGame else 0.2)
    if blackKingCastled: score -= 40*(1.0 if not isEndGame else 0.2)
    
    
    score += centerControl
    return score




def importPositionMap():
    listOfJsonPath = [pawnJsonPath,knightJsonPath,kingJsonPath,queenJsonPath,bishopJsonPath,rookJsonPath]
    piecePositionMap = {}
    for path in listOfJsonPath:
        with open(path,'r',encoding='utf-8') as p:
            data = json.load(p)
            piece = list(data.keys())[0]
            arr = np.array(data[piece], dtype=float)
            
            
            arr = np.nan_to_num(arr, nan=0.0)
            arr -= np.mean(arr)
            
            piecePositionMap[piece] = arr
            piecePositionMap[piece.lower()] = arr[::-1]
    piecePositionMap['Ke']=kingEndPosition
    piecePositionMap['ke']=kingEndPosition[::-1]
    return piecePositionMap


def computePawnStructure(board):
    global pawnPosition
    score = 0
    whitePawnPositions = pawnPosition['white']
    blackPawnPositions = pawnPosition['black']
    for position in whitePawnPositions:
        #if it is an along pawn or support by pawn chain
        row,col=algebraicToIndex(position)
        
        dir = [(1,-1),(1,1)]
        for dr,dc in dir:
            surroundingRow,surroundingCol = row+dr,col+dc
            if (0<=surroundingRow<8) and (0<=surroundingCol<8):
                if(board[surroundingRow][surroundingCol]=='P'):
                    if((0<=row-1<8) and (0<=col+1<8) and (board[row-1][col+1]!='p')) or ((0<=row-1<8) and (0<=col-1<8) and (board[row-1][col-1]!='p')):
                        score +=10
                    else:
                        score +=5
                else:
                    score -=5
        
        #if there is a doubled pawn in col
        for i in range(8):
            if (board[i][col] == 'P') and (i != row):
                score-=10
        

        
                
        
    for position in blackPawnPositions:
        #if it is an along pawn or support by pawn chain
        row,col=algebraicToIndex(position)
        dir = [(-1,-1),(-1,1)]
        for dr,dc in dir:
            surroundingRow,surroundingCol = row+dr,col+dc
            if (0<=surroundingRow<8) and (0<=surroundingCol<8):
                if(board[surroundingRow][surroundingCol]=='p'):
                    if((0<=row+1<8) and (0<=col+1<8) and (board[row+1][col+1]!='p')) or ((0<=row+1<8) and (0<=col-1<8) and (board[row+1][col-1]!='p')):
                        score -=10
                    else:
                        score -=5
                else:
                    score +=5
        #if there is a doubled pawn in col
        for i in range(8):
            if (board[i][col] == 'p') and (i!=row):
                score+=10
                    
    return score





def computeCenterControl(board):
    global centerWeights
    score = 0
    return score





def minimax(board,depth,alpha,beta,maximizingPlayer,piecePositionMap,isRoot):
    color = 'white' if maximizingPlayer else 'black'
    moves = generateAlllegalMoves(board,color)
    if moves == []:
        if isKingChecked(board,color):
            if maximizingPlayer:
                return -100000+depth
                
            else:
                return 100000-depth
        else:
            return 0
        
    rootMobility = 0
    if isRoot:
        rootMobility = len(moves) if color =='white' else -len(moves)
        
    if depth == 0:
        return evaluateBoard(board,piecePositionMap,moves)
    if maximizingPlayer:
        maxEval = -float('inf')
        for fromSquare,toSquare in moves:
            doMove(board,fromSquare,toSquare)
            eval = minimax(board,depth-1,alpha,beta,False,piecePositionMap,False)
            undoMove(board)
            maxEval = max(eval,maxEval)
            alpha = max(alpha,maxEval)
            if alpha>=beta:
                break
        return maxEval + rootMobility
    else:
        minEval = float('inf')
        for fromSquare,toSquare in moves:
            
            doMove(board,fromSquare,toSquare)
            eval = minimax(board,depth-1,alpha,beta,True,piecePositionMap,False)
            undoMove(board)
            minEval = min(eval,minEval)
            beta = min(beta,minEval)
            if beta<=alpha:
                break
        return minEval + rootMobility
    
# ────────────────────────────────────────────────────
# Level 1: Root (MAX) α=-∞ β=+∞
# │
# ├── A1: MIN (α=-∞, β=+∞)
# │     ├── A1a: MAX (α=-∞, β=+∞)
# │     │     ├── A1a1 = 3 → α=max(-∞,3)=3
# │     │     ├── A1a2 = 5 → α=max(3,5)=5
# │     │     └── A1a3 = 2 → α=max(5,2)=5
# │     │     → 返回 5
# │     ├── A1b: MAX (α=-∞, β=5)
# │     │     ├── A1b1 = 9 → α=9
# │     │     ⚠️ α(9) ≥ β(5) → 剪枝！不看A1b2, A1b3
# │     │     → 返回 9
# │     ├── A1c: MAX (α=-∞, β=min(+∞,min(5,9))=5)
# │     │     ├── A1c1 = 6 → α=6
# │     │     ⚠️ α(6) ≥ β(5) → 剪枝！A1c2, A1c3跳过
# │     │     → 返回 6
# │     → MIN节点取 min(5,9,6)=5 → 返回 5
# │     → Root 更新 α=max(-∞,5)=5
# │
# ├── A2: MIN (α=5, β=+∞)
# │     ├── A2a: MAX (α=5, β=+∞)
# │     │     ├── A2a1 = 10 → α=10
# │     │     ⚠️ α(10) ≥ β(+∞)? 否 → 继续
# │     │     ├── A2a2 = 2 → α=max(10,2)=10
# │     │     └── A2a3 = 0 → α=10 → 返回 10
# │     ├── A2b: MAX (α=5, β=min(+∞,10)=10)
# │     │     ├── A2b1 = 5 → α=5
# │     │     ├── A2b2 = 6 → α=6
# │     │     ├── A2b3 = 12 → α=12
# │     │     ⚠️ α(12) ≥ β(10) → 剪枝！
# │     │     → 返回 12
# │     ├── A2c: MAX (α=5, β=min(+∞,min(10,12))=10)
# │     │     ├── A2c1 = 4 → α=4
# │     │     ├── A2c2 = 3 → α=max(4,3)=4
# │     │     ├── A2c3 = 1 → α=4
# │     │     → 返回 4
# │     → MIN节点取 min(10,12,4)=4 → 返回 4
# │     → Root α=max(5,4)=5（不变）
# │
# ├── A3: MIN (α=5, β=+∞)
# │     ├── A3a: MAX (α=5, β=+∞)
# │     │     ├── A3a1 = 9 → α=9
# │     │     ⚠️ α(9) ≥ β(+∞)? 否 → 继续
# │     │     ├── A3a2 = 11 → α=11
# │     │     ├── A3a3 = 10 → α=11 → 返回 11
# │     ├── A3b: MAX (α=5, β=min(+∞,11)=11)
# │     │     ├── A3b1 = 2 → α=2
# │     │     ├── A3b2 = 3 → α=3
# │     │     ├── A3b3 = 1 → α=3 → 返回 3
# │     ├── A3c: MAX (α=5, β=min(+∞,min(11,3))=3)
# │     │     ⚠️ α(5) ≥ β(3) → 整个 A3c 剪枝！
# │     │     （A3c1, A3c2, A3c3 完全不展开）
# │     │     → 返回 β=3
# │     → MIN节点 min(11,3)=3 → 返回 3
# │
# └── Root: MAX 取 max(5,4,3)=5 → ✅ 最优值 = 5
# ────────────────────────────────────────────────────


        
def findBestMove(board,color,depth,piecePositionMap):
    bestMove = None
    maximizingPlayer = True if color == 'white' else False
    bestScore = -float('inf') if maximizingPlayer else float('inf')
    moves = generateAlllegalMoves(board,color)
    
    for fromSquare,toSquare in moves:
        doMove(board,fromSquare,toSquare)
        futureScore = minimax(board,depth-1,-float('inf'), float('inf'),not maximizingPlayer,piecePositionMap,True)
        undoMove(board)
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
    piecePositionMap = importPositionMap()
    printBoard(board)
    numOfSteps = 0
    engineSide = None
    print('1: Engine use white')
    print('2: Engine use black')
    print('3: Engine do not participate')
    print('4: Engine in both side')
    choice = input('Choose number to choose where should engine be: ')
    if choice == '1':
        engineSide = 'white'
    elif choice == '2':
        engineSide = 'black'
    elif choice == '3':
        engineSide = 'none'
    elif choice == '4':
        engineSide = 'both'
    while True:
        color = 'white' if numOfSteps%2 == 0 else 'black'
        if engineSide == 'both' or color == engineSide:
            moveRecommend = findBestMove(board,color,3,piecePositionMap)
            if moveRecommend is None:
                print('Mated')
                break
            print(moveRecommend)
            doMove(board,moveRecommend[0],moveRecommend[1])
            printBoard(board)
            numOfSteps += 1 
            continue 
        
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






















# def isSquareAttacked(board, row, col, byColor):
#     directions_bishop = [(-1,-1), (-1,1), (1,-1), (1,1)]
#     directions_rook = [(-1,0), (1,0), (0,-1), (0,1)]
#     directions_knight = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
#     directions_king = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    
#     if byColor == 'white':
#         pawn_dirs = [(-1,-1), (-1,1)]
#         pawn_char = 'P'
#     else:
#         pawn_dirs = [(1,-1), (1,1)]
#         pawn_char = 'p'
#     for dr, dc in pawn_dirs:
#         r, c = row + dr, col + dc
#         if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == pawn_char:
#             return True

    
#     knight_char = 'N' if byColor == 'white' else 'n'
#     for dr, dc in directions_knight:
#         r, c = row + dr, col + dc
#         if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == knight_char:
#             return True

    
#     king_char = 'K' if byColor == 'white' else 'k'
#     for dr, dc in directions_king:
#         r, c = row + dr, col + dc
#         if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == king_char:
#             return True

    
#     bishop_char = 'B' if byColor == 'white' else 'b'
#     queen_char = 'Q' if byColor == 'white' else 'q'
#     for dr, dc in directions_bishop:
#         r, c = row + dr, col + dc
#         while 0 <= r < 8 and 0 <= c < 8:
#             piece = board[r][c]
#             if piece != '.':
#                 if piece == bishop_char or piece == queen_char:
#                     return True
#                 break
#             r += dr; c += dc

    
#     rook_char = 'R' if byColor == 'white' else 'r'
#     for dr, dc in directions_rook:
#         r, c = row + dr, col + dc
#         while 0 <= r < 8 and 0 <= c < 8:
#             piece = board[r][c]
#             if piece != '.':
#                 if piece == rook_char or piece == queen_char:
#                     return True
#                 break
#             r += dr; c += dc

#     return False    

# def computeMaterial(board):
#     pieceValue = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0,
#                 'p': -100, 'n': -320, 'b': -330, 'r': -500, 'q': -900, 'k': 0}
#     score = 0
#     for row in range(8):
#         for col in range(8):
#             piece = board[row][col]
#             if piece != '.':
#                 score+=pieceValue[piece]
#     return score

# def computePosition(board,piecePositionMap):
#     global isWhiteQueenExist, isBlackQueenExist
    
#     pieceCoefficientInOpen = {'p':1.0,'P':1.0,'n':1.4,'N':1.4,'b':1.3,'B':1.3,
#                               'r':0.8,'R':0.8,'q':0.5,'Q':0.5,'k':1.0,'K':1.0}
#     pieceCoefficientInEnd = {'p':1.2,'P':1.2,'n':1.0,'N':1.0,'b':1.1,'B':1.1,
#                               'r':1.0,'R':1.0,'q':0.5,'Q':0.5,'k':2.0,'K':2.0}
#     piecePositionScoreCap = {'p':20,'n':30,'b':30,'q':10,'r':20,'k':20}
#     isEndGame = not(isWhiteQueenExist and isBlackQueenExist)
#     pstScale = 0.3
#     if isEndGame:
#         pstScale = 0.15
#     score = 0
#     if isEndGame:
#         piecePositionScoreCap['k'] = 60
#     for row in range(8):
#         for col in range(8):
#             piece = board[row][col]
#             if piece == '.':
#                 continue
#             if not isEndGame:
#                 piecePositionScore = pstScale*pieceCoefficientInOpen[piece]*piecePositionMap[piece][row][col]
#                 cap = piecePositionScoreCap[piece.lower()]
#                 if piecePositionScore > cap:
#                     piecePositionScore = cap
#                 elif piecePositionScore < -cap:
#                     piecePositionScore = -cap
#             else:
#                 piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap[piece][row][col]
#                 cap = piecePositionScoreCap[piece.lower()]
#                 if piecePositionScore > cap:
#                     piecePositionScore = cap
#                 elif piecePositionScore < -cap:
#                     piecePositionScore = -cap
#             if piece.isupper():
#                 score += piecePositionScore
#             elif piece.islower():
#                 score -= piecePositionScore
#     return score

# def computeMobility(board,moves,mobilityHint=None):
#     global isWhiteQueenExist, isBlackQueenExist
#     isEndGame = not(isWhiteQueenExist and isBlackQueenExist)
#     score = 0
#     pieceCoefficientMap = {'N':1.0,'B':1.0,'P':0.5,'R':0.8,'K':(0.3 if not isEndGame else 1),'Q':0.6}
#     mobilityCap = {
#     'N': 30,   
#     'B': 40,   
#     'R': 25,   
#     'Q': 20,   
#     'K': 15,   
#     'P': 10    
# }
#     if mobilityHint != None:
#         score+= mobilityHint
#     else:#Only use when in indepent evaluation
#         numWhite = len(generateAlllegalMoves(board,'white'))
#         numBlack = len(generateAlllegalMoves(board,'black'))
#         score += numWhite-numBlack
#         #return 0
    
#     for row in range(8):
#         for col in range(8):
#             piece = board[row][col]
#             fromSquare = indexToAlgebraic(row,col)
#             if piece =='.':
#                 continue
#             if piece == 'P' or piece == 'p':
#                 moveForPiece = generatePawnMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['P']:
#                     addingscore = mobilityCap['P']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#             elif piece == 'N' or piece == 'n':
#                 moveForPiece = generateKnightMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['N']:
#                     addingscore = mobilityCap['N']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#             elif piece == 'B' or piece == 'b':
#                 moveForPiece = generateBishopMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['B']:
#                     addingscore = mobilityCap['B']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#             elif piece == 'R' or piece == 'r':
#                 moveForPiece = generateRookMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['R']:
#                     addingscore = mobilityCap['R']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#             elif piece == 'Q' or piece == 'q':
#                 moveForPiece = generateQueenMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['Q']:
#                     addingscore = mobilityCap['Q']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#             elif piece == 'K' or piece == 'k':
#                 moveForPiece = generateKingMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['K']:
#                     addingscore = mobilityCap['K']
#                 if piece.isupper():
#                     score+=addingscore
#                 else:
#                     score-=addingscore
#     return score






# def makeMove(board, fromSquare, toSquare, rights):
#     """
#     Create a temporary board copy to simulate a move (no global side effects).
#     This version:
#         - Reads enPassant / castling from globals (safe since it doesn't modify them)
#         - Updates only local copies
#         - Returns (newBoard, newRights, localEnPassantSquare, localEnPassantColor)
#     """
#     global enPassantSquare, enPassantColor  # read-only usage
#     newBoard = copy.deepcopy(board)
#     newRights = copy.deepcopy(rights)

#     # local en passant (isolated from global)
#     localEnPassantSquare = enPassantSquare
#     localEnPassantColor = enPassantColor
#     setEnPassant = False

#     fromRow, fromCol = algebraicToIndex(fromSquare)
#     toRow, toCol = algebraicToIndex(toSquare)
#     piece = newBoard[fromRow][fromCol]
#     target = newBoard[toRow][toCol]

#     # --- En passant capture logic ---
#     if piece in ('P', 'p'):
#         if abs(fromRow - toRow) == 2:
#             # set potential en passant
#             if piece == 'P':
#                 localEnPassantSquare = indexToAlgebraic(toRow + 1, fromCol)
#                 localEnPassantColor = 'white'
#             else:
#                 localEnPassantSquare = indexToAlgebraic(toRow - 1, fromCol)
#                 localEnPassantColor = 'black'
#             setEnPassant = True
#         elif toSquare == enPassantSquare:
#             # handle actual en passant capture
#             if piece == 'P' and enPassantColor == 'black':
#                 newBoard[fromRow + 1][toCol] = '.'
#             elif piece == 'p' and enPassantColor == 'white':
#                 newBoard[fromRow - 1][toCol] = '.'

#     # --- Execute move ---
#     newBoard[toRow][toCol] = piece
#     newBoard[fromRow][fromCol] = '.'

#     # --- Promotion ---
#     if piece == 'P' and toRow == 0:
#         newBoard[toRow][toCol] = 'Q'
#     elif piece == 'p' and toRow == 7:
#         newBoard[toRow][toCol] = 'q'

#     # --- Castling logic ---
#     if piece == 'K':
#         newRights['white_king_moved'] = True
#         if fromSquare == 'e1' and toSquare == 'g1':
#             newBoard[7][5], newBoard[7][7] = 'R', '.'
#         elif fromSquare == 'e1' and toSquare == 'c1':
#             newBoard[7][3], newBoard[7][0] = 'R', '.'
#     elif piece == 'k':
#         newRights['black_king_moved'] = True
#         if fromSquare == 'e8' and toSquare == 'g8':
#             newBoard[0][5], newBoard[0][7] = 'r', '.'
#         elif fromSquare == 'e8' and toSquare == 'c8':
#             newBoard[0][3], newBoard[0][0] = 'r', '.'

#     # --- Update rook move status ---
#     if piece == 'R':
#         if fromSquare == 'a1': newRights['white_rook_a_moved'] = True
#         elif fromSquare == 'h1': newRights['white_rook_h_moved'] = True
#     elif piece == 'r':
#         if fromSquare == 'a8': newRights['black_rook_a_moved'] = True
#         elif fromSquare == 'h8': newRights['black_rook_h_moved'] = True

#     # --- Reset local en passant if no new one is set ---
#     if not setEnPassant:
#         localEnPassantSquare = None
#         localEnPassantColor = None

#     return newBoard, newRights, localEnPassantSquare, localEnPassantColor






# def testDoUndoConsistency(board, numTests=100):
#     """
#     Test whether doMove() and undoMove() perfectly restore board & state.
#     Runs random legal moves numTests times.
#     """
#     global castling_rights, enPassantSquare, enPassantColor
#     global pawnPosition, isWhiteQueenExist, isBlackQueenExist, moveHistory

#     print("\n=== Running doMove / undoMove Consistency Test ===\n")

#     # Backup original globals
#     original_castling = copy.deepcopy(castling_rights)
#     original_enpassant_sq = enPassantSquare
#     original_enpassant_color = enPassantColor
#     original_pawnPosition = copy.deepcopy(pawnPosition)
#     original_whiteQ = isWhiteQueenExist
#     original_blackQ = isBlackQueenExist

#     passed, failed = 0, 0

#     for i in range(numTests):
#         # 复制当前状态（因为每次测试都要回到同一起点）
#         testBoard = copy.deepcopy(board)

#         # 获取所有合法走法
#         color = "white" if i % 2 == 0 else "black"
#         moves = generateAlllegalMoves(testBoard, color)
#         if not moves:
#             continue
#         move = random.choice(moves)
#         fromSq, toSq = move

#         # 保存所有初始状态快照
#         pre_state = {
#             "board": copy.deepcopy(testBoard),
#             "castling_rights": copy.deepcopy(castling_rights),
#             "enPassantSquare": enPassantSquare,
#             "enPassantColor": enPassantColor,
#             "pawnPosition": copy.deepcopy(pawnPosition),
#             "isWhiteQueenExist": isWhiteQueenExist,
#             "isBlackQueenExist": isBlackQueenExist,
#         }

#         # 执行并回退
#         doMove(testBoard, fromSq, toSq)
#         undoMove(testBoard)

#         # 检查恢复一致性
#         if (
#             testBoard == pre_state["board"]
#             and castling_rights == pre_state["castling_rights"]
#             and enPassantSquare == pre_state["enPassantSquare"]
#             and enPassantColor == pre_state["enPassantColor"]
#             and pawnPosition == pre_state["pawnPosition"]
#             and isWhiteQueenExist == pre_state["isWhiteQueenExist"]
#             and isBlackQueenExist == pre_state["isBlackQueenExist"]
#         ):
#             passed += 1
#         else:
#             failed += 1
#             print(f"❌ Failed at test #{i+1} ({fromSq}->{toSq})")
#             printBoard(testBoard)
#             print("Expected:")
#             printBoard(pre_state["board"])
#             break

#     # 恢复原始全局状态
#     castling_rights = copy.deepcopy(original_castling)
#     enPassantSquare = original_enpassant_sq
#     enPassantColor = original_enpassant_color
#     pawnPosition = copy.deepcopy(original_pawnPosition)
#     isWhiteQueenExist = original_whiteQ
#     isBlackQueenExist = original_blackQ

#     print(f"\n🎯 Consistency Test Complete: {passed} passed, {failed} failed.\n")
    
# def testSpecialMoveUndo(board):
#     print("\n=== Running Special Move Undo Consistency Test ===\n")
#     passed, failed = 0, 0

#     # ------------------------------
#     # 1️⃣ EN PASSANT
#     # ------------------------------
#     print("Test 1: En Passant do/undo consistency")
#     initializeBoard()
#     # Setup custom board
#     board = [['.'] * 8 for _ in range(8)]
#     board[3][4] = 'p'   # black pawn on e5
#     board[6][3] = 'P'   # white pawn on d2

#     global enPassantSquare, enPassantColor, moveHistory, pawnPosition
#     enPassantSquare = None
#     enPassantColor = None
#     moveHistory.clear()

#     # ✅ 同步 pawnPosition
#     pawnPosition['white'] = {'d2'}
#     pawnPosition['black'] = {'e5'}

#     # White moves d2->d4 (en passant target)
#     doMove(board, 'd2', 'd4')
#     # Black performs en passant e5xd4
#     doMove(board, 'e5', 'd4')
#     undoMove(board)
#     undoMove(board)

#     init_board = [['.'] * 8 for _ in range(8)]
#     init_board[3][4] = 'p'
#     init_board[6][3] = 'P'

#     if board == init_board:
#         print("✅ Passed: En passant restored correctly.")
#         passed += 1
#     else:
#         print("❌ Failed: En passant mismatch after undo.")
#         failed += 1

#     # ------------------------------
#     # 2️⃣ CASTLING
#     # ------------------------------
#     print("\nTest 2: Castling do/undo consistency")
#     board = [['.'] * 8 for _ in range(8)]
#     board[7][4] = 'K'
#     board[7][7] = 'R'
#     global castling_rights
#     castling_rights = {
#         'white_king_moved': False,
#         'white_rook_a_moved': False,
#         'white_rook_h_moved': False,
#         'black_king_moved': False,
#         'black_rook_a_moved': False,
#         'black_rook_h_moved': False
#     }
#     moveHistory.clear()

#     doMove(board, 'e1', 'g1')  # short castle
#     undoMove(board)

#     if board[7][4] == 'K' and board[7][7] == 'R' and board[7][5] == '.' and board[7][6] == '.':
#         print("✅ Passed: Castling restored correctly.")
#         passed += 1
#     else:
#         print("❌ Failed: Castling not restored properly.")
#         failed += 1

#     # ------------------------------
#     # 3️⃣ PROMOTION
#     # ------------------------------
#     print("\nTest 3: Promotion do/undo consistency")
#     board = [['.'] * 8 for _ in range(8)]
#     board[1][0] = 'P'  # White pawn on a7
#     moveHistory.clear()

#     # ✅ 同步 pawnPosition
#     pawnPosition['white'] = {'a7'}
#     pawnPosition['black'] = set()

#     doMove(board, 'a7', 'a8')  # promote
#     undoMove(board)

#     if board[1][0] == 'P' and board[0][0] == '.':
#         print("✅ Passed: Promotion restored correctly.")
#         passed += 1
#     else:
#         print("❌ Failed: Promotion not restored properly.")
#         failed += 1

#     # ------------------------------
#     print(f"\n🎯 Special Move Undo Tests Complete: {passed} passed, {failed} failed.\n")























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

# def testEnPassant_All():
#     global enPassantSquare, enPassantColor

#     print("\n=== Running Comprehensive En Passant Test Suite ===\n")
#     passed, failed = 0, 0

#     # -------------------------------------------------
#     # A. White can capture en passant (e5xd6 e.p.)
#     # -------------------------------------------------
#     enPassantSquare = "d6"
#     enPassantColor = "black"
#     boardA = [['.']*8 for _ in range(8)]
#     boardA[3][3] = 'p'  # d5 black pawn
#     boardA[3][4] = 'P'  # e5 white pawn

#     print("Test A: White can capture en passant (e5xd6)")
#     moves = generateAlllegalMoves(boardA, 'white')
#     if ('e5', 'd6') in moves:
#         print("✅ Passed: e5xd6 found in legal moves.")
#         passed += 1
#     else:
#         print("❌ Failed: e5xd6 missing.")
#         failed += 1

#     # -------------------------------------------------
#     # B. Black can capture en passant (f4xe3 e.p.)
#     # -------------------------------------------------
#     enPassantSquare = "e3"
#     enPassantColor = "white"
#     boardB = [['.']*8 for _ in range(8)]
#     boardB[4][4] = 'P'  # e4 white pawn
#     boardB[4][5] = 'p'  # f4 black pawn

#     print("\nTest B: Black can capture en passant (f4xe3)")
#     moves = generateAlllegalMoves(boardB, 'black')
#     if ('f4', 'e3') in moves:
#         print("✅ Passed: f4xe3 found in legal moves.")
#         passed += 1
#     else:
#         print("❌ Failed: f4xe3 missing.")
#         failed += 1

#     # -------------------------------------------------
#     # C. En Passant expired (no longer legal)
#     # -------------------------------------------------
#     enPassantSquare = None
#     enPassantColor = None
#     boardC = [['.']*8 for _ in range(8)]
#     boardC[3][3] = 'p'  # d5 black pawn
#     boardC[3][4] = 'P'  # e5 white pawn

#     print("\nTest C: En Passant expired (should not allow e5xd6)")
#     moves = generateAlllegalMoves(boardC, 'white')
#     if ('e5', 'd6') not in moves:
#         print("✅ Passed: no en passant allowed.")
#         passed += 1
#     else:
#         print("❌ Failed: illegal e.p. move still exists.")
#         failed += 1

#     # -------------------------------------------------
#     # D. En Passant removes captured pawn correctly
#     # -------------------------------------------------
#     enPassantSquare = "d6"
#     enPassantColor = "black"
#     boardD = [['.']*8 for _ in range(8)]
#     boardD[3][3] = 'p'  # d5 black pawn
#     boardD[3][4] = 'P'  # e5 white pawn

#     print("\nTest D: Ghost pawn removed after e5xd6")
#     movePiece(boardD, "e5", "d6")
#     d5_row, d5_col = algebraicToIndex("d5")
#     d6_row, d6_col = algebraicToIndex("d6")
#     if boardD[d5_row][d5_col] == '.' and boardD[d6_row][d6_col] == 'P':
#         print("✅ Passed: d5 empty and d6 has white pawn.")
#         passed += 1
#     else:
#         print("❌ Failed: ghost pawn not cleared or pawn misplaced.")
#         failed += 1

#     # -------------------------------------------------
#     # E1. Edge-file en passant (a5×b6)
#     # -------------------------------------------------
#     enPassantSquare = "b6"
#     enPassantColor = "black"
#     boardE1 = [['.']*8 for _ in range(8)]
#     boardE1[3][0] = 'P'  # a5 white pawn
#     boardE1[3][1] = 'p'  # b5 black pawn

#     print("\nTest E1: White edge-file en passant (a5xb6)")
#     moves = generateAlllegalMoves(boardE1, 'white')
#     if ('a5', 'b6') in moves:
#         print("✅ Passed: a5xb6 found in legal moves.")
#         passed += 1
#     else:
#         print("❌ Failed: a5xb6 missing.")
#         failed += 1

#     # -------------------------------------------------
#     # E2. Black edge-file en passant (h5×g4)
#     # -------------------------------------------------
#     enPassantSquare = "g4"
#     enPassantColor = "white"
#     boardE2 = [['.']*8 for _ in range(8)]
#     boardE2[4][6] = 'P'  # g4 white pawn
#     boardE2[3][7] = 'p'  # h5 black pawn

#     print("\nTest E2: Black edge-file en passant (h5xg4)")
#     moves = generateAlllegalMoves(boardE2, 'black')
#     if ('h5', 'g4') in moves:
#         print("✅ Passed: h5xg4 found in legal moves.")
#         passed += 1
#     else:
#         print("❌ Failed: h5xg4 missing.")
#         failed += 1

#     # -------------------------------------------------
#     # F. Wrong color marker (should forbid e.p.)
#     # -------------------------------------------------
#     enPassantSquare = "e3"
#     enPassantColor = "black"  # wrong color
#     boardF = [['.']*8 for _ in range(8)]
#     boardF[4][4] = 'P'  # e4 white pawn
#     boardF[4][5] = 'p'  # f4 black pawn

#     print("\nTest F: Wrong color marker (f4xe3 should NOT appear)")
#     moves = generateAlllegalMoves(boardF, 'black')
#     if ('f4', 'e3') not in moves:
#         print("✅ Passed: e.p. correctly forbidden due to color mismatch.")
#         passed += 1
#     else:
#         print("❌ Failed: wrong-color e.p. still allowed.")
#         failed += 1

#     # -------------------------------------------------
#     print(f"\n🎯 En Passant Tests Complete: {passed} passed, {failed} failed.\n")
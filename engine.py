import string
import copy
import json
import numpy as np
import os
from collections import deque
import random
import time
from isSquareAttacked import isSquareAttacked
from movegen import isKingChecked,generatePawnMoves,generateKnightMoves,generateBishopMoves,generateRookMoves,generateQueenMoves,generateKingMoves,generateAllPseudoMoves
import logging
import pesto
import opening



numOfSteps = 0

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

openMoves = []
UsingOpen = True




PIECE_INDEX = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}


np.random.seed(112358)
ZOBRIST_TABLE = np.random.randint(0, 2**63, size=(12, 64), dtype=np.uint64) 


ZOBRIST_BLACK_TURN = np.random.randint(0, 2**63, dtype=np.uint64)

currentHash = np.uint64(0)

TRANSPOSITION_TABLE = {}
TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2

SQ_TO_COORD = {}
# (7, 0) -> 'a1'
COORD_TO_SQ = {}

for r in range(8):
    for c in range(8):
        rank = str(8 - r)
        file = chr(ord('a') + c)
        sq_str = file + rank
        SQ_TO_COORD[sq_str] = (r, c)
        COORD_TO_SQ[(r, c)] = sq_str


def algebraicToIndex(square):
    return SQ_TO_COORD[square]

def indexToAlgebraic(row, col):
    return COORD_TO_SQ[(row, col)]

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
    global pawnPosition,currentHash
    board = [['.'] * 8 for _ in range(8)]
    board[0] = ['r','n','b','q','k','b','n','r']
    board[1] = ['p'] * 8
    board[6] = ['P'] * 8
    board[7] = ['R','N','B','Q','K','B','N','R']
    pawnPosition['white']={'a2','b2','c2','d2','e2','f2','g2','h2'}
    pawnPosition['black']={'a7','b7','c7','d7','e7','f7','g7','h7'}
    currentHash = computeHash(board,'white')
    return board

def movePiece(board, fromSquare, toSquare):#This is for user to use
    global isWhiteQueenExist, isBlackQueenExist,enPassantSquare,enPassantColor,pawnPosition,castling_rights,moveHistory,currentHash
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
                capturedPawnSq = indexToAlgebraic(fromRow, toCol)
                if capturedPawnSq in pawnPosition['black']:
                    pawnPosition['black'].remove(capturedPawnSq)
                board[fromRow][toCol] = '.'
            elif piece == 'p' and enPassantColor == 'white':
                capturedPawnSq = indexToAlgebraic(fromRow, toCol)
                if capturedPawnSq in pawnPosition['white']:
                    pawnPosition['white'].remove(capturedPawnSq)
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
        if toSquare in pawnPosition['white']:
            pawnPosition['white'].remove(toSquare)
    elif piece == 'p' and toRow == 7:
        board[toRow][toCol] = 'q'
        if toSquare in pawnPosition['black']:
            pawnPosition['black'].remove(toSquare)


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
    
    next_turn_color = 'black' if piece.isupper() else 'white'
    
    # 2. 全盘重算，确保绝对正确
    currentHash = computeHash(board, next_turn_color)


def doMove(board,fromSquare,toSquare):#This is for engine simulation
    global isWhiteQueenExist, isBlackQueenExist,enPassantSquare,enPassantColor,pawnPosition,castling_rights,moveHistory,whiteKingCastled,blackKingCastled,currentHash,PIECE_INDEX
    setEnPassant = False
    fromRow, fromCol = algebraicToIndex(fromSquare)
    toRow, toCol = algebraicToIndex(toSquare)
    piece = board[fromRow][fromCol]
    target = board[toRow][toCol]

    snapshot = {'from':fromSquare,
                'to':toSquare,
                'movedPiece':piece,
                'capturedPiece':target,
                'rights':castling_rights.copy(),
                'enPassantSquare':enPassantSquare,
                'enPassantColor':enPassantColor,
                'pawnPosition':{'white':pawnPosition['white'].copy(),'black':pawnPosition['black'].copy()},
                'isBlackQueenExist':isBlackQueenExist,
                'isWhiteQueenExist':isWhiteQueenExist,
                'special': None,
                'whiteKingCastled':whiteKingCastled,
                'blackKingCastled':blackKingCastled,
                'hash':currentHash
                }
    
    def pieceXOR(piece,row,col):
        if piece == '.':
            return 0
        pieceIndex = PIECE_INDEX[piece]
        squareIndex = row*8+col
        return ZOBRIST_TABLE[pieceIndex][squareIndex]
    
        
    #Do the hash computation
    currentHash ^= pieceXOR(piece,fromRow,fromCol)
    if target !='.':
        currentHash ^= pieceXOR(target,toRow,toCol)
    
    actualPieceToPlace = piece
    if piece == 'P' and toRow == 0: actualPieceToPlace = 'Q'
    elif piece == 'p' and toRow == 7: actualPieceToPlace = 'q'
    
    currentHash ^= pieceXOR(actualPieceToPlace, toRow, toCol)
    
    if piece in ('P','p') and toSquare == enPassantSquare:
        if piece == 'P':
            opRow,opCol = algebraicToIndex(enPassantSquare)
            currentHash ^= pieceXOR('p',opRow+1,opCol)
        elif piece == 'p':
            opRow,opCol = algebraicToIndex(enPassantSquare)
            currentHash ^= pieceXOR('P',opRow-1,opCol)
            
    if piece in ('K','k'):
        if piece == 'K':
            # white short castle hash xor
            if fromSquare == 'e1' and toSquare == 'g1': 
                currentHash ^= pieceXOR('R', 7, 7) # Take away h1 rook
                currentHash ^= pieceXOR('R', 7, 5) # put it to h1
            # white long castle hash xor
            elif fromSquare == 'e1' and toSquare == 'c1':
                currentHash ^= pieceXOR('R', 7, 0) # Take awat a1 rook
                currentHash ^= pieceXOR('R', 7, 3) # put it to d1
        elif piece == 'k':
            # black short castle hash xor
            if fromSquare == 'e8' and toSquare == 'g8':
                currentHash ^= pieceXOR('r', 0, 7)
                currentHash ^= pieceXOR('r', 0, 5)
            # black long castle hash xor
            elif fromSquare == 'e8' and toSquare == 'c8':
                currentHash ^= pieceXOR('r', 0, 0)
                currentHash ^= pieceXOR('r', 0, 3)
    currentHash ^= ZOBRIST_BLACK_TURN
    
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
    global currentHash

    if len(moveHistory) == 0:
        return
    
    snapshot = moveHistory.pop()
    fromSq = snapshot["from"]
    toSq = snapshot["to"]
    fromRow, fromCol = algebraicToIndex(fromSq)
    toRow, toCol = algebraicToIndex(toSq)

    movedPiece = snapshot["movedPiece"]
    capturedPiece = snapshot["capturedPiece"]
    currentHash = snapshot['hash']

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
    
    



    





def generateAlllegalMoves(board, color):
    global enPassantSquare,enPassantColor,castling_rights
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
                moveList = generatePawnMoves(board,square,enPassantSquare,enPassantColor)
            elif piecetype == 'n':
                moveList = generateKnightMoves(board,square)
            elif piecetype == 'b':
                moveList = generateBishopMoves(board,square)
            elif piecetype == 'r':
                moveList = generateRookMoves(board,square)
            elif piecetype == 'q':
                moveList = generateQueenMoves(board,square)
            elif piecetype == 'k':
                moveList = generateKingMoves(board,square,castling_rights)
            
            for toSquare in moveList:
                PseudoMoves.append((square,toSquare))
    for fromSquare,toSquare in PseudoMoves:
        doMove(board,fromSquare,toSquare)
        if not isKingChecked(board,color):
            legalMoves.append((fromSquare,toSquare))
        undoMove(board)
        
    return legalMoves

def generateAllCaptureMoves(board,color):
    moves = generateAlllegalMoves(board,color)
    captureMoves = []
    for fromSquare,toSquare in moves:
        fromRow,fromCol = algebraicToIndex(fromSquare)
        toRow,toCol = algebraicToIndex(toSquare)
        if (board[toRow][toCol] != '.') and isOpponent(board[fromRow][fromCol],board[toRow][toCol]):
            if SEE(board, fromSquare, toSquare) >= 0:
                captureMoves.append((fromSquare,toSquare))
    return captureMoves


def evaluateBoard(board,piecePositionMap,mobilityHint=None):
    global isBlackQueenExist,isWhiteQueenExist,pawnPosition,whiteKingCastled,blackKingCastled,centerWeights,numOfSteps
    
    score = 0
    mgScore = 0
    egScore = 0
    phase = 0
    totalPhase = 24
    
    
    
    #Compute pawn structure score
    # pawnStructureScore = computePawnStructure(board)
    # score+=pawnStructureScore*0.8
    
    
    
    
    #Looping over the board and calculate the score for each square
    for row in range(8):
        for col in range(8):
            
            piece = board[row][col]
            
            if piece != '.':
                upperPiece = piece.upper()
                
                pestoTable = pesto.TABLES[upperPiece]
                
                if piece.isupper():
                    # WHITE piece on board row0=a8; pesto index assumes a1=0 -> flip ranks
                    idx = (7 - row) * 8 + col
                    mgScore += pestoTable[idx][0] + pesto.MG_VALUE[upperPiece]
                    egScore += pestoTable[idx][1] + pesto.EG_VALUE[upperPiece]
                    if upperPiece in pesto.GAME_PHASE_INC:
                        phase += pesto.GAME_PHASE_INC[upperPiece]

                elif piece.islower():
                    # BLACK piece: map to white-perspective square by rank mirror (d8 -> d1 etc.)
                    idx = row * 8 + col
                    mgScore -= (pestoTable[idx][0] + pesto.MG_VALUE[upperPiece])
                    egScore -= (pestoTable[idx][1] + pesto.EG_VALUE[upperPiece])
                    if upperPiece in pesto.GAME_PHASE_INC:
                        phase += pesto.GAME_PHASE_INC[upperPiece]
                        
    phase = min(phase,totalPhase)
    
    score += ((mgScore * phase) + (egScore * (totalPhase - phase))) // totalPhase
    score += 30
    return score
# def evaluateBoard(board,piecePositionMap,mobilityHint=None):
#     global isBlackQueenExist,isWhiteQueenExist,pawnPosition,whiteKingCastled,blackKingCastled,centerWeights,numOfSteps
    
#     score = 0
    
#     pieceValue = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0,
#                 'p': -100, 'n': -320, 'b': -330, 'r': -500, 'q': -900, 'k': 0}
    
#     isEndGame = not(isWhiteQueenExist and isBlackQueenExist)
    
    
#     #For position computation
#     pieceCoefficientInOpen = {'p':1.0,'P':1.0,'n':1.4,'N':1.4,'b':1.3,'B':1.3,
#                               'r':0.8,'R':0.8,'q':0.5,'Q':0.5,'k':1.0,'K':1.0}
#     pieceCoefficientInEnd = {'p':1.2,'P':1.2,'n':1.0,'N':1.0,'b':1.1,'B':1.1,
#                               'r':1.0,'R':1.0,'q':0.5,'Q':0.5,'k':2.0,'K':2.0}
#     piecePositionScoreCap = {'p':20,'n':30,'b':30,'q':10,'r':20,'k':20}
#     pstScale = 0.3
#     if isEndGame:
#         pstScale = 0.15
    
#     if isEndGame:
#         piecePositionScoreCap['k'] = 60
        
#     #For mobility computation
#     pieceCoefficientMap = {'N':1.0,'B':1.0,'P':0.5,'R':0.8,'K':(0.3 if not isEndGame else 1),'Q':0.6}
#     mobilityCap = {
#     'N': 12,   
#     'B': 15,   
#     'R': 10,   
#     'Q': 8,   
#     'K': 5,   
#     'P': 3    
# }
    
    
#     #Compute pawn structure score
#     pawnStructureScore = computePawnStructure(board)
#     score+=pawnStructureScore*(0.15 if not isEndGame else 0.25)
#     #Looping over the board and calculate the score for each square
#     for row in range(8):
#         for col in range(8):
            
#             piece = board[row][col]
            
#             if piece != '.':
#                 #Calculating material score, which has the coefficient of 1.0
#                 score+=pieceValue[piece]
                
                
#                 #Calculating position score, which has the coefficient of 0.8
#                 if not isEndGame:
#                     piecePositionScore = pstScale*pieceCoefficientInOpen[piece]*piecePositionMap[piece][row,col]
#                     cap = piecePositionScoreCap[piece.lower()]
#                     if piecePositionScore > cap:
#                         piecePositionScore = cap
#                     elif piecePositionScore < -cap:
#                         piecePositionScore = -cap
#                 else:
#                     if piece=='K':
#                         piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap['Ke'][row,col]
#                     elif piece=='k':
#                         piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap['ke'][row,col]
#                     else:
#                         piecePositionScore = pstScale*pieceCoefficientInEnd[piece]*piecePositionMap[piece][row,col]
#                     cap = piecePositionScoreCap[piece.lower()]
#                     if piecePositionScore > cap:
#                         piecePositionScore = cap
#                     elif piecePositionScore < -cap:
#                         piecePositionScore = -cap
#                 if piece.isupper():
#                     score += piecePositionScore*0.8
#                 elif piece.islower():
#                     score -= piecePositionScore*0.8

#             #Compute for mobility score, which has the coefficient of (0.3 if not isEndGame else 0.1)
#             fromSquare = indexToAlgebraic(row,col)
#             if piece == 'P' or piece == 'p':
#                 moveForPiece = generatePawnMoves(board,fromSquare,enPassantSquare,enPassantColor)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['P']:
#                     addingscore = mobilityCap['P']
#                 if piece.isupper():
#                     score+=addingscore*(0.3 if not isEndGame else 0.1)
#                 else:
#                     score-=addingscore*(0.3 if not isEndGame else 0.1)
#             elif piece == 'N' or piece == 'n':
#                 moveForPiece = generateKnightMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['N']:
#                     addingscore = mobilityCap['N']
#                 if piece.isupper():
#                     score+=addingscore*(0.3 if not isEndGame else 0.1)
#                 else:
#                     score-=addingscore*(0.3 if not isEndGame else 0.1)
#             elif piece == 'B' or piece == 'b':
#                 moveForPiece = generateBishopMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['B']:
#                     addingscore = mobilityCap['B']
#                 if piece.isupper():
#                     score+=addingscore*(0.3 if not isEndGame else 0.1)
#                 else:
#                     score-=addingscore*(0.3 if not isEndGame else 0.1)
#             elif piece == 'R' or piece == 'r':
#                 moveForPiece = generateRookMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['R']:
#                     addingscore = mobilityCap['R']
#                 if piece.isupper():
#                     score+=addingscore*(0.3 if not isEndGame else 0.1)
#                 else:
#                     score-=addingscore*(0.3 if not isEndGame else 0.1)
#             elif piece == 'Q' or piece == 'q':
#                 moveForPiece = generateQueenMoves(board,fromSquare)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['Q']:
#                     addingscore = mobilityCap['Q']
#                 if piece.isupper():
#                     score+=addingscore*(0.3 if not isEndGame else 0.1)
#                 else:
#                     score-=addingscore*(0.3 if not isEndGame else 0.1)
#             elif piece == 'K' or piece == 'k':
#                 #Kings mobility
#                 moveForPiece = generateKingMoves(board,fromSquare,castling_rights)
#                 addingscore = len(moveForPiece)*pieceCoefficientMap[piece.upper()]
#                 if addingscore >= mobilityCap['K']:
#                     addingscore = mobilityCap['K']
#                 if piece.isupper():
#                     score+=addingscore*(0.05 if not isEndGame else 0.15)
#                 else:
#                     score-=addingscore*(0.05 if not isEndGame else 0.15)
                    
#                 #kingSafety
#                 surrounding = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
#                 friPieceAroundWhite = 0
#                 friPieceAroundBlack = 0
#                 for dr,dc in surrounding:
#                     r = row+dr
#                     c = col+dc
#                     if (0<=r<8) and (0<=c<8):
#                         pieceAround = board[r][c]
#                         pieceAroundKingScore = {'P':10,'N':3,'B':3,'R':0.5,'Q':-2,
#                                                 'p':-10,'n':-3,'b':-3,'r':-0.5,'q':2,}
#                         if piece == 'K':
#                             if pieceAround != '.'and not isOpponent(piece,pieceAround):
#                                 friPieceAroundWhite += 1
#                                 if not isEndGame:
#                                     score+=pieceAroundKingScore[pieceAround]
                                
#                         elif piece == 'k':
#                             if pieceAround != '.'and not isOpponent(piece,pieceAround):
#                                 friPieceAroundBlack += 1
#                                 if not isEndGame:
#                                     score+=pieceAroundKingScore[pieceAround]
#                 if isEndGame:
#                     if friPieceAroundWhite > 3:
#                         score -= (friPieceAroundWhite - 3) * 0.15
#                     if friPieceAroundBlack > 3:
#                         score += (friPieceAroundBlack - 3) * 0.15
                        
           
#             # if piece !='.':            
#             #     # white positive, black negative
#             #     sign = 1 if piece.isupper() else -1
#             #     # Add center weight directly from lookup table
#             #     score += sign * centerWeights[row][col]*(0.3 if not isEndGame else 0.15)
                
#     score+=computeCenterControl(board)*(0.3 if not isEndGame else 0.15)
#     centerSquare = {(3,3),(3,4),(4,3),(4,4)}
#     for pst in pawnPosition['white']:
#         trow,tcol = algebraicToIndex(pst)
#         if numOfSteps<8 and (trow,tcol) in centerSquare:
#             score+=12
    
#     for pst in pawnPosition['black']:
#         trow,tcol = algebraicToIndex(pst)
#         if numOfSteps<8 and (trow,tcol) in centerSquare:
#             score-=12

#     return score

    




def importPositionMap():
    listOfJsonPath = [pawnJsonPath,knightJsonPath,kingJsonPath,queenJsonPath,bishopJsonPath,rookJsonPath]
    piecePositionMap = {}
    for path in listOfJsonPath:
        with open(path,'r',encoding='utf-8') as p:
            data = json.load(p)
            piece = list(data.keys())[0]
            arr = np.array(data[piece], dtype=float)
            
            
            
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
                        score +=15
                    else:
                        score +=10
                else:
                    score -=10
        
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
                        score -=15
                    else:
                        score -=10
                else:
                    score +=10
        #if there is a doubled pawn in col
        for i in range(8):
            if (board[i][col] == 'p') and (i!=row):
                score+=10
                    
    return score



def computeCenterControl(board):
    global centerWeights
    score = 0
    mainCenterSquare = {(3,3),(3,4),(4,3),(4,4)}
    semiCenterSquare = {(2,2),(2,3),(2,4),(2,5),(3,2),(3,5),(4,2),(4,5),(5,2),(5,3),(5,4),(5,5)}
    for row,col in mainCenterSquare:
        whiteControl = isSquareAttacked(board,row,col,'white')
        blackControl = isSquareAttacked(board,row,col,'black')
        score += whiteControl-blackControl
    for row,col in semiCenterSquare:
        whiteControl = isSquareAttacked(board,row,col,'white')*0.3
        blackControl = isSquareAttacked(board,row,col,'black')*0.3
        score += whiteControl-blackControl
    return score




def sortMovesBySEE(board, moves):
    scoredMoves = []
    for move in moves:
        fromSquare, toSquare = move
        if board[algebraicToIndex(toSquare)[0]][algebraicToIndex(toSquare)[1]] != '.':
            seeScore = SEE(board, fromSquare, toSquare)
        else:
            seeScore = 0
        scoredMoves.append((seeScore, move))
    scoredMoves.sort(reverse=True)  # Moves with higher SEE scores come first
    return [m for s, m in scoredMoves]



def sortMovesByMVV_LVA(board, moves):
    PIECE_VALUES = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000, 
                'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}
    scoredMoves = []
    for move in moves:
        fromSquare, toSquare = move
        
        r_to, c_to = algebraicToIndex(toSquare)
        target = board[r_to][c_to]
        
        if target != '.':
            r_from, c_from = algebraicToIndex(fromSquare)
            attacker = board[r_from][c_from]
            
            # MVV-LVA formula：
            # 10 * target value - piece value
            score = 10 * PIECE_VALUES[target] - PIECE_VALUES[attacker] + 10000
        else:
            score = 0 
            
        scoredMoves.append((score, move))
    

    scoredMoves.sort(key=lambda x: x[0], reverse=True)
    return [m for s, m in scoredMoves]

def minimax(board, depth, alpha, beta, maximizingPlayer, piecePositionMap, isRoot):
    global currentHash
    entryHash = currentHash
    

    # 1. 查表 (TT Lookup) - 是否已经搜过这个局面？

    # TT Look up, does this state been searched before?

    alphaOriginal = alpha # preserve alpha for TT update later
    tt_move = None
    
    # Check if the current position is in the transposition table
    if currentHash in TRANSPOSITION_TABLE:
        tt_entry = TRANSPOSITION_TABLE[currentHash]
        # entry format: (score, depth, flag, best_move)
        tt_score, tt_depth, tt_flag, tt_move = tt_entry
        
        # Only when the table record is equal or deeper than current is valuable
        if not isRoot and tt_depth >= depth:
            if tt_flag == TT_EXACT: # Actual value
                return tt_score
            elif tt_flag == TT_LOWERBOUND: # lower bound
                alpha = max(alpha, tt_score)
            elif tt_flag == TT_UPPERBOUND: # higher bound
                beta = min(beta, tt_score)
            
            # return if can be pruned
            if alpha >= beta:
                return tt_score


    # Base case

    if depth == 0:
        # Quiescence Search
        return quiescence(board, alpha, beta, maximizingPlayer, piecePositionMap)
    
    color = 'white' if maximizingPlayer else 'black'
    moves = generateAlllegalMoves(board, color)
    
    if moves == []:
        if isKingChecked(board, color):
            # if checkmate, adjust based on depth
            return -100000 + (10 - depth) if maximizingPlayer else 100000 - (10 - depth)
        else:
            # 逼和
            return 0


    # Move Ordering
    # Hash Move First
    if tt_move is not None:
        # Have to check if it's still a valid move
        if tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)
            
    # SEE Sort
    # Only sort non hash move by SEE
    if tt_move and moves[0] == tt_move:
        rest_moves = sortMovesBySEE(board, moves[1:])
        moves = [tt_move] + rest_moves
    else:
        moves = sortMovesBySEE(board, moves)
    
    in_check = isKingChecked(board, color)

    if not in_check:
        currentBeamWidth = 25 if isRoot else 15
        
        if len(moves) > currentBeamWidth:
            # Keep the top 25 moves
            kept_moves = moves[:currentBeamWidth]
            
            # Safety Net, get those that are not safe to prune
            for m in moves[currentBeamWidth:]:
                f_sq, t_sq = m
                
                r_from, c_from = algebraicToIndex(f_sq)
                r_to, c_to = algebraicToIndex(t_sq)
                moved_piece = board[r_from][c_from]
                target_piece = board[r_to][c_to]
                
                # Keep if capture or promotion
                is_capture = (target_piece != '.')
                
                is_promotion = False
                if moved_piece == 'P' and r_to == 0: is_promotion = True
                elif moved_piece == 'p' and r_to == 7: is_promotion = True
                
                if is_capture or is_promotion:
                    kept_moves.append(m)
            
            moves = kept_moves
            

    # Search loop
    best_move_this_node = None # Best move at this node
    
    if maximizingPlayer:
        maxEval = -float('inf')
        for fromSquare, toSquare in moves:
            doMove(board, fromSquare, toSquare)
            # Recursion
            eval = minimax(board, depth - 1, alpha, beta, False, piecePositionMap, False)
            undoMove(board)
            
            # Update best move
            if eval > maxEval:
                maxEval = eval
                best_move_this_node = (fromSquare, toSquare)
            
            # Alpha-Beta updates
            alpha = max(alpha, eval)
            if alpha >= beta:
                break # Beta Cutoff
        
        final_val = maxEval
        
    else:
        minEval = float('inf')
        for fromSquare, toSquare in moves:
            doMove(board, fromSquare, toSquare)
            # Recursion
            eval = minimax(board, depth - 1, alpha, beta, True, piecePositionMap, False)
            undoMove(board)
            
            # Update best move
            if eval < minEval:
                minEval = eval
                best_move_this_node = (fromSquare, toSquare)
                
            # Alpha-Beta updates
            beta = min(beta, eval)
            if beta <= alpha:
                break # Alpha Cutoff
                
        final_val = minEval

    # TT Store

    tt_flag = TT_EXACT
    if final_val <= alphaOriginal:
        tt_flag = TT_UPPERBOUND # Fail Low: Does not larger than alpha, means it is too bad (Upper Bound)
    elif final_val >= beta:
        tt_flag = TT_LOWERBOUND # Fail High: larger than beta，means it is too good(Lower Bound)
    else:
        tt_flag = TT_EXACT      # Exact: 在窗口内，是精确值
    
    # Store: Hash -> (Score, Depth, Flag, BestMove)
    TRANSPOSITION_TABLE[entryHash] = (final_val, depth, tt_flag, best_move_this_node)
    
    return final_val



    
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

def quiescence(board,alpha,beta,maximizingPlayer,piecePositionMap):
    currentScore = evaluateBoard(board,piecePositionMap)
    if maximizingPlayer:
        if currentScore >=beta:
            return beta
        if currentScore >alpha:
            alpha = currentScore
    else:
        if currentScore<=alpha:
            return alpha
        if currentScore <beta:
            beta = currentScore
    
    color = 'white' if maximizingPlayer else 'black'
    
    captureMoves = generateAllCaptureMoves(board,color)
    if len(captureMoves) == 0:
        return currentScore

    if maximizingPlayer:
        maxEval = -float('inf')
        for fromSquare,toSquare in captureMoves:
            doMove(board,fromSquare,toSquare)
            eval = quiescence(board,alpha,beta,False,piecePositionMap)
            undoMove(board)
            maxEval = max(eval,maxEval)
            alpha = max(eval,alpha)
            if alpha>=beta:
                break # Beta cutoff
        return maxEval
    else:
        minEval = float('inf')
        for fromSquare,toSquare in captureMoves:
            doMove(board,fromSquare,toSquare)
            eval = quiescence(board,alpha,beta,True,piecePositionMap)
            undoMove(board)
            minEval = min(eval,minEval)
            beta = min(beta,eval)
            if beta<=alpha:
                break # Alpha cutoff
        return minEval



#  SEE (Static Exchange Evaluation) & Helpers 


piece_values_simple = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000,
                       'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}

def get_piece_value(piece):
    return piece_values_simple.get(piece, 0)

def get_lowest_attacker(board, square, color):
    targetRow, targetCol = algebraicToIndex(square)
    lowest_value = float('inf')
    best_attacker_sq = None
    best_attacker_piece = None

    # Pawn
    pawn_char = 'P' if color == 'white' else 'p'
    attack_from_row = targetRow + 1 if color == 'white' else targetRow - 1
    
    if 0 <= attack_from_row < 8:
        for dc in [-1, 1]:
            c = targetCol + dc
            if 0 <= c < 8 and board[attack_from_row][c] == pawn_char:
                return (pawn_char, indexToAlgebraic(attack_from_row, c))

    # Knight
    knight_char = 'N' if color == 'white' else 'n'
    for dr, dc in [(1,2),(1,-2),(2,1),(2,-1),(-1,2),(-1,-2),(-2,1),(-2,-1)]:
        r, c = targetRow + dr, targetCol + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == knight_char:
            return (knight_char, indexToAlgebraic(r, c))

    # Sliders (Bishop, Rook, Queen)
    
    # Bishops & Queens (Diagonal)
    bishop_char = 'B' if color == 'white' else 'b'
    queen_char = 'Q' if color == 'white' else 'q'
    
    candidates = []
    
    for dr, dc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
        r, c = targetRow + dr, targetCol + dc
        while 0 <= r < 8 and 0 <= c < 8:
            p = board[r][c]
            if p != '.':
                if p == bishop_char or p == queen_char:
                    candidates.append((p, indexToAlgebraic(r, c), get_piece_value(p)))
                break
            r += dr
            c += dc
            
    # Rooks & Queens (Orthogonal)
    rook_char = 'R' if color == 'white' else 'r'
    for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
        r, c = targetRow + dr, targetCol + dc
        while 0 <= r < 8 and 0 <= c < 8:
            p = board[r][c]
            if p != '.':
                if p == rook_char or p == queen_char:
                    candidates.append((p, indexToAlgebraic(r, c), get_piece_value(p)))
                break
            r += dr
            c += dc
            
    # King
    king_char = 'K' if color == 'white' else 'k'
    for dr, dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
        r, c = targetRow + dr, targetCol + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == king_char:
             candidates.append((king_char, indexToAlgebraic(r, c), 20000))

    if not candidates:
        return (None, None)
    
    # return the one with the lowest value
    candidates.sort(key=lambda x: x[2])
    return (candidates[0][0], candidates[0][1])


def SEE(board, fromSquare, toSquare):
    fromRow, fromCol = algebraicToIndex(fromSquare)
    toRow, toCol = algebraicToIndex(toSquare)
    
    target = board[toRow][toCol]
    attacker = board[fromRow][fromCol]
    
    changes = []
    def apply_temp(r, c, p):
        changes.append((r, c, board[r][c]))
        board[r][c] = p

  
    values = [get_piece_value(target)]
    
    # doFirstMove
    apply_temp(toRow, toCol, attacker)
    apply_temp(fromRow, fromCol, '.')
    
    # 接下来该对手下
    current_side = 'black' if attacker.isupper() else 'white'
    
    # 迭代寻找后续攻击者
    while True:
        piece, sq = get_lowest_attacker(board, toSquare, current_side)
        if not piece:
            break
        
        values.append(get_piece_value(board[toRow][toCol]))
        
        src_r, src_c = algebraicToIndex(sq)
        apply_temp(toRow, toCol, piece)
        apply_temp(src_r, src_c, '.')
        
        current_side = 'white' if current_side == 'black' else 'black'
        if piece.lower() == 'k': # End when king is captured
            break
            
    # restore board state
    for r, c, p in reversed(changes):
        board[r][c] = p
        
    # Compute the SEE score backwards
    score = 0
    for v in reversed(values[1:]):
        score = max(0, v - score)
        
    return values[0] - score


def computeHash(board,color):
    hashValue = np.uint64(0)
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece !='.':
                pieceIndex = PIECE_INDEX[piece]
                squareIndex = row*8+col
                pieceHash = ZOBRIST_TABLE[pieceIndex][squareIndex]
                hashValue ^= pieceHash
    if color == 'black':
        hashValue^= ZOBRIST_BLACK_TURN
    return hashValue


def get_pv_line(board, depth):
    global currentHash, TRANSPOSITION_TABLE
    line = []
    
    
    seen_hashes = set()
    
    for _ in range(depth):
        if currentHash in TRANSPOSITION_TABLE:
            move = TRANSPOSITION_TABLE[currentHash][3] # best_move
            if move is None: break
            
            line.append(move)
            seen_hashes.add(currentHash)
            
            
            doMove(board, move[0], move[1])
        else:
            break
            
    
    for _ in range(len(line)):
        undoMove(board)
        
    return line
        
def findBestMove(board,color,depth,piecePositionMap):
    bestMove = None
    maximizingPlayer = True if color == 'white' else False
    bestScore = -float('inf') if maximizingPlayer else float('inf')
    moves = generateAlllegalMoves(board,color)
    
    logging.debug(f"\n🔍 Searching best move for {color.upper()}, depth={depth}, total legal moves={len(moves)}")
    for fromSquare,toSquare in moves:
        doMove(board,fromSquare,toSquare)
        movingPiece = board[algebraicToIndex(toSquare)[0]][algebraicToIndex(toSquare)[1]]
        futureScore = minimax(board,depth-1,-float('inf'), float('inf'),not maximizingPlayer,piecePositionMap,True)
        undoMove(board)
        logging.debug(f"[ROOT] Move {fromSquare}->{toSquare} scored {futureScore:.2f}")
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
        
    if bestMove is not None:
       
        flag = TT_EXACT 
        TRANSPOSITION_TABLE[currentHash] = (bestScore, depth, flag, bestMove)
        
        pv_line = get_pv_line(board, depth)
        print(f"Engine thinking: Line: {pv_line}")
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
    global numOfSteps,UsingOpen,openMoves
    ocWhite = opening.WhiteOpen[random.choice(list(opening.WhiteOpen.keys()))]
    ocBlack = opening.BlackOpen[random.choice(list(opening.BlackOpen.keys()))]
    board = initializeBoard()
    piecePositionMap = importPositionMap()
    printBoard(board)
    
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
        UsingOpen = False
    elif choice == '4':
        engineSide = 'both'
        UsingOpen = False
    else:
        print("Invalid choice. Engine will not participate.")
        UsingOpen = False
    while True:
        color = 'white' if numOfSteps%2 == 0 else 'black'
        if engineSide == 'both' or color == engineSide:
            startTime = time.time()
            moveRecommend = None
            if UsingOpen and ocWhite!=[] and ocBlack!=[] and engineSide in ['white','black','both']:
                if engineSide == 'white':
                    moveRecommend = ocWhite.pop(0)
                elif engineSide == 'black':
                    moveRecommend = ocBlack.pop(0)
                elif engineSide == 'both':
                    if color == 'white':
                        moveRecommend = ocWhite.pop(0)
                    else:
                        moveRecommend = ocBlack.pop(0)
            else:
                moveRecommend = findBestMove(board,color,5,piecePositionMap)
            if moveRecommend is None:
                print('Mated')
                break
            print(moveRecommend)
            doMove(board,moveRecommend[0],moveRecommend[1])
            openMoves.append(moveRecommend)
            endTime = time.time()
            printBoard(board)
            print(endTime-startTime)
            numOfSteps += 1 
            continue 
        
        move = input("Please enter your move (e.g., e2 e4, or input q to quit):")
        if move.lower() == 'q':
            break
        try:
            fromSq, toSq = move.split()
            openMoves.append((fromSq,toSq))
            movePiece(board, fromSq, toSq)
            printBoard(board)
            numOfSteps+=1
            if engineSide == 'white':
                if tuple(move.split()) == ocWhite[0]:
                    ocWhite.pop(0)
                else:
                    UsingOpen = False
            elif engineSide == 'black':
                if tuple(move.split()) == ocBlack[0]:
                    ocBlack.pop(0)
                else:
                    UsingOpen = False
            
        except:
            print("Input format error! Please use a form like e2 e4.")
            
            

if __name__ == "__main__":
    main()

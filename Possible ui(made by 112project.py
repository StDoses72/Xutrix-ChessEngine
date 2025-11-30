# Place your creative task here!

# Be clever, be creative, have fun

from cmu_graphics import *
import math

class Board:
    def __init__(self):
        self.board = [[None]*8 for _ in range(8)]
        self.whiteKingMoved = False
        self.blackKingMoved = False
        self.whiteARookMoved = False
        self.whiteHRookMoved = False
        self.blackKingMoved = False
        self.materialDiff = 0
        self.enPassant = None
        self.enPassantCapturer = None
        
    
    def __repr__(self):
        pass
        
    def findLegalMoves(self,fromRow,fromCol):
        piece = self.board[fromRow][fromCol]
        if isinstance(piece,King):
            return kingMoves(self,fromRow,fromCol)
        elif isinstance(piece,Knight):
            return knightMoves(self,fromRow,fromCol)
        elif isinstance(piece,Pawn):
            return pawnMoves(self,fromRow,fromCol)
        elif isinstance(piece,Bishop):
            return slidingPieceMoves('B',self,fromRow,fromCol)
        elif isinstance(piece,Rook):
            return slidingPieceMoves('R',self,fromRow,fromCol)
        elif isinstance(piece,Queen):
            return slidingPieceMoves('Q',self,fromRow,fromCol)
            
        
        
        
        
        
        
        
        
    def doMove(self,fromRow,fromCol,toRow,toCol):
        isEnpassant = False
        piece = self.board[fromRow][fromCol]
        target = self.board[toRow][toCol]
        if piece == None:
            pass
        else:
            if isinstance(piece,Pawn) and (toRow,toCol) == self.enPassant:
                if ((fromRow-1,fromCol-1) == self.enPassant) or ((fromRow-1,fromCol+1) == self.enPassant):#For white
                    self.board[fromRow][fromCol] = None
                    self.board[toRow][toCol] = piece
                    piece.row = toRow
                    piece.col = toCol
                    self.board[toRow+1][toCol].row = None
                    self.board[toRow+1][toCol].col = None
                    self.board[toRow+1][toCol] = None
                elif ((fromRow+1,fromCol-1) == self.enPassant) or ((fromRow+1,fromCol+1) == self.enPassant):#For white
                    self.board[fromRow][fromCol] = None
                    self.board[toRow][toCol] = piece
                    piece.row = toRow
                    piece.col = toCol
                    self.board[toRow-1][toCol].row = None
                    self.board[toRow-1][toCol].col = None
                    self.board[toRow-1][toCol] = None
            else:
                self.board[fromRow][fromCol] = None
                self.board[toRow][toCol] = piece
                piece.row = toRow
                piece.col = toCol
                if target!=None:
                    target.row = None
                    target.col = None
        if (fromRow == 7 and fromCol == 0 and isinstance(piece,Rook) and piece.color == 'white') or (toRow == 7 and toCol == 0 and isinstance(target,Rook) and target.color== 'white'):
            self.whiteARookMoved = True
        elif (fromRow == 7 and fromCol == 7 and isinstance(piece,Rook) and piece.color == 'white') or (toRow == 7 and toCol == 7 and isinstance(target,Rook) and target.color == 'white'):
            self.whiteHRookMoved = True
        
        if (fromRow == 0 and fromCol == 0 and isinstance(piece,Rook) and piece.color == 'black') or (toRow == 0 and toCol == 0 and isinstance(target,Rook) and target.color == 'black'):
            self.blackARookMoved = True
        elif (fromRow == 0 and fromCol == 7 and isinstance(piece,Rook) and piece.color == 'white') or (toRow == 0 and toCol == 7 and isinstance(target,Rook) and target.color == 'white'):
            self.blackHRookMoved = True
        
        if isinstance(piece,Pawn):#Enpassant
            if fromRow == 6 and toRow ==4 and fromCol == toCol:
                self.enPassant = (toRow+1,toCol)
                self.enPassantCapturer = 'black'
                isEnpassant = True
            if fromRow == 1 and toRow ==3 and fromCol == toCol:
                self.enPassant = (toRow-1,toCol)
                self.enPassantCapturer = 'white'
                isEnpassant = True
                    
        if not isEnpassant:
            self.enPassant = None
            self.enPassantColor = None


#Moves generators
def kingMoves(board,row,col):
    moves = []
    cdir = [(-1,-1),(-1,0),(-1,1),
            (0,-1),(0,1),
            (1,-1),(1,0),(1,1)]
    for drow,dcol in cdir:
        r = row+drow
        c = col+dcol
        if 0<=r<=7 and 0<=c<=7:
            if board.board[row][col].isOpponent(board.board[r][c]):
                moves.append((r,c))
    return moves
            
def pawnMoves(board,row,col):
    moves=[]
    piece = board.board[row][col]
    color = piece.color
    if color == 'white':
        for drow in range(1,3):#generating normal push moves
            if drow ==2:
                if row ==6:
                    r = row-drow
                    moves.append((r,col))
            else:
                moves.append((row-drow,col))
        for dcol in range(-1,2):#generating capture moves
            if dcol!=0 and 0<=row+1<=7 and 0<=col+dcol<=7:
                target = board.board[row-1][col+dcol]
                if piece.isOpponent(target) and target!=None:
                    moves.append((row-1,col+dcol))
        if ((piece.row-1,piece.col-1)==board.enPassant and board.enPassantCapturer =='white') or ((piece.row-1,piece.col+1)==board.enPassant and board.enPassantCapturer =='white'):
            moves.append(board.enPassant)
                
    else:
        for drow in range(1,3):
            if drow ==2:
                if row ==1:
                    r = row+drow
                    moves.append((r,col))
            else:
                moves.append((row+drow,col))
        for dcol in range(-1,2):
            if dcol!=0 and 0<=row+1<=7 and 0<=col+dcol<=7:
                target = board.board[row+1][col+dcol]
                if piece.isOpponent(target) and target!=None:
                    moves.append((row-1,col+dcol))
        if ((piece.row+1,piece.col-1)==board.enPassant and board.enPassantCapturer =='black') or ((piece.row+1,piece.col+1)==board.enPassant and board.enPassantCapturer =='black'):
            moves.append(board.enPassant)
    return moves
def knightMoves(board,row,col):
    moves = []
    cdir = [(2,1),(2,-1),(1,2),(1,-2),(-1,2),(-1,-2),(-2,1),(-2,-1)]
    for drow,dcol in cdir:
        r = row+drow
        c = col+dcol
        if 0<=r<=7 and 0<=c<=7:
            if board.board[row][col].isOpponent(board.board[r][c]):
                moves.append((r,c))
    return moves
def slidingPieceMoves(ptype,board,row,col):
    moves = []
    cdir = []
    if ptype == 'B':
        cdir = [(-1,-1),(-1,1),(1,-1),(1,1)]
    elif ptype == 'R':
        cdir = [(1,0),(-1,0),(0,1),(0,-1)]
    elif ptype == 'Q':
        cdir = [(-1,-1),(-1,1),(1,-1),(1,1),(1,0),(-1,0),(0,1),(0,-1)]
    
    for drow,dcol in cdir:
        tempr,tempc = row,col
        while True:
            tempr,tempc = tempr+drow,tempc+dcol
            if tempr<0 or tempr>7 or tempc<0 or tempc>7:
                break
            if not (board.board[row][col].isOpponent(board.board[tempr][tempc])):
                break
            if board.board[tempr][tempc] == None:
                moves.append((tempr,tempc))
            else:
                if (board.board[row][col].isOpponent(board.board[tempr][tempc])):
                    moves.append((tempr,tempc))
                    break
    return moves
















          

class Piece:
    def __init__(self,row,col,color):
        self.row = row
        self.col = col
        self.color = color
    def isOpponent(self,other):
        if other == None:
            return True
        if isinstance(other,Piece):
            return (self.color != other.color)
#Piece Class
class King(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
class Knight(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
class Pawn(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
class Bishop(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
class Rook(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
class Queen(Piece):
    def __init__(self,row,col,color):
        super().__init__(row,col,color)
    
        

        
        
def initializeBoard():
    board = Board()
    #Piece for Black
    board.board[0][0] = Rook(0,0,'black')
    board.board[0][1] = Knight(0,1,'black')
    board.board[0][2] = Bishop(0,2,'black')
    board.board[0][3] = Queen(0,3,'black')
    board.board[0][4] = King(0,4,'black')
    board.board[0][5] = Bishop(0,5,'black')
    board.board[0][6] = Knight(0,6,'black')
    board.board[0][7] = Rook(0,7,'black')
    board.board[1][0] = Pawn(1,0,'black')
    board.board[1][1] = Pawn(1,1,'black')
    board.board[1][2] = Pawn(1,2,'black')
    board.board[1][3] = Pawn(1,3,'black')
    board.board[1][4] = Pawn(1,4,'black')
    board.board[1][5] = Pawn(1,5,'black')
    board.board[1][6] = Pawn(1,6,'black')
    board.board[1][7] = Pawn(1,7,'black')
    board.board[0][0] = Rook(0,0,'black')
    #Piece for White
    board.board[7][0] = Rook(7,0,'white')
    board.board[7][1] = Knight(7,1,'white')
    board.board[7][2] = Bishop(7,2,'white')
    board.board[7][3] = Queen(7,3,'white')
    board.board[7][4] = King(7,4,'white')
    board.board[7][5] = Bishop(7,5,'white')
    board.board[7][6] = Knight(7,6,'white')
    board.board[7][7] = Rook(7,7,'white')
    board.board[6][0] = Pawn(6,0,'white')
    board.board[6][1] = Pawn(6,1,'white')
    board.board[6][2] = Pawn(6,2,'white')
    board.board[6][3] = Pawn(6,3,'white')
    board.board[6][4] = Pawn(6,4,'white')
    board.board[6][5] = Pawn(6,5,'white')
    board.board[6][6] = Pawn(6,6,'white')
    board.board[6][7] = Pawn(6,7,'white')
    return board

def drawBoard(app,board):
    cellSize = (app.height-50)//8
    for row in range(8):
        for col in range(8):
            color = 'white' if col%2 == row%2 else 'darkgray'
            drawRect(col*cellSize,row*cellSize,cellSize,cellSize,fill = color,border = 'black')
            
    for row in range(8):
        for col in range(8):
            piece = board.board[row][col]
            label = ''
            if isinstance(piece,Rook):
                label = 'R'
                if piece.color == 'black':
                    label = label.lower()
            elif isinstance(piece,Knight):
                label = 'N'
                if piece.color == 'black':
                    label = label.lower()
            elif isinstance(piece,Bishop):
                label = 'B'
                if piece.color == 'black':
                    label = label.lower()
            elif isinstance(piece,Queen):
                label = 'Q'
                if piece.color == 'black':
                    label = label.lower()
            elif isinstance(piece,King):
                label = 'K'
                if piece.color == 'black':
                    label = label.lower()
            elif isinstance(piece,Pawn):
                label = 'P'
                if piece.color == 'black':
                    label = label.lower()
            if label == '':
                pass
            else:
                drawLabel(label,col*cellSize+0.5*cellSize,row*cellSize+0.5*cellSize,size = 18)
    drawRect(0,0,cellSize*8,cellSize*8,fill = None,border = 'black',borderWidth = 4.25)           

def onAppStart(app):
    app.width = 450
    app.height =500
    app.board = initializeBoard()
    app.turn = 'white'
    app.piecePosition = []
    app.isSelected = False
    app.selectedSquare = None
    app.moves = []
    

def redrawAll(app):
    drawBoard(app,app.board)
    drawLabel(f'Current material difference is {app.board.materialDiff}',(app.height-50)//2,(app.height-25))
    for row,col in app.moves:
        drawCircle(col*(app.height-50)//8+(app.height-50)//16,row*(app.height-50)//8+(app.height-50)//16,10,fill = 'yellow')
        

def onMousePress(app,mouseX,mouseY):
    cellSize = (app.height-50)//8
    row = mouseY//cellSize
    col = mouseX//cellSize
    if not (row>7 or col>7 or row<0 or col<0):#Click inside the board
        if app.isSelected == False:#You need to choose the piece you want to move
            if app.board.board[row][col] != None:
                app.isSelected = True
                app.selectedSquare = (row,col)
                # print(f'isSelected,{type(app.board.board[row][col]).__name__} at {row},{col}')
                app.moves = app.board.findLegalMoves(row,col)
                
            else:
                app.isSelected = False
                app.selectedSquare = None
                # print(f'No selecting legal piece at {row},{col}')
                app.moves = []
        else:#you need to make your move
            if (app.board.board[row][col] == None) and (row,col) not in app.moves:
                app.isSelected = False
                app.selectedSquare = None
                # print('It does not seems to be a legal move')
                app.moves = []
            elif (row,col) in app.moves:
                fromR,fromC = app.selectedSquare
                app.board.doMove(fromR,fromC,row,col)
                app.isSelected = False
                app.selectedSquare = None
                app.moves = []
                # print(f'{type(app.board.board[row][col]).__name__} move from {(fromR,fromC)} to {(row,col)}')
                
    else:#click outside the board
        app.isSelected = False
        app.selectedSquare = None
        # print('Outside the board')
        app.moves = []



def onKeyPress(app,key):
    if key == 'r':
        app.board.doMove(0,0,3,3)
        print(app.board.board[3][3].row,app.board.board[3][3].col)
        print(app.board.findLegalMoves(3,3))
        print(app.board.blackARookMoved)
    if key == 'k':
        print(app.board.findLegalMoves(7,4))
    if key == 'n':
        print(app.board.findLegalMoves(7,1))
        print(app.board.findLegalMoves(7,6))
        print(app.board.findLegalMoves(0,1))
        print(app.board.findLegalMoves(0,6))
    if key == 'q':
        print(app.board.findLegalMoves(0,3))
        app.board.doMove(7,3,5,3)
        print(app.board.findLegalMoves(5,3))
    if key == 'p':
        app.board.board[5][1]=Pawn(5,1,'black')
        app.board.board[2][1]=Pawn(2,1,'black')
        print(app.board.findLegalMoves(6,0))
        print(app.board.findLegalMoves(1,0))
    if key == 'b':
        print(app.board.findLegalMoves(7,5))
        app.board.doMove(1,3,2,3)
        print(app.board.findLegalMoves(0,2))
    if key == 'e':
        app.board.doMove(6,7,3,7)
        app.board.doMove(1,6,3,6)
        print(app.board.findLegalMoves(3,7))
    if key =='t':
        app.board.doMove(3,7,2,6)
    if key == 'i':
        app.board.doMove(3,6,4,7)
    
    


    
def main():
    runApp()

main()
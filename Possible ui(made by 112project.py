from cmu_graphics import *



class Board:
    def __init__(self):
        self.board = [[None]*8 for _ in range(8)]
        self.whiteKingMoved = False
        self.blackKingMoved = False
        self.whiteARookMoved = False
        self.whiteHRookMoved = False
        self.blackARookMoved = False
        self.blackHRookMoved = False
        self.materialDiff = 0
        self.enPassant = None
        self.enPassantCapturer = None
        self.whiteLongCastle = False
        self.whiteShortCastle = False
        self.blackLongCastle = False
        self.blackShortCastle = False
        self.isWhiteLose = False
        self.isBlackLose = False
        
    
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
                    
                if isinstance(target,King) and target.color =='white':
                    self.isWhiteLose = True
                elif isinstance(target,King) and target.color =='black':
                    self.isBlackLose = True
            if isinstance(piece,King):
                if piece.color =='white':
                    if fromRow == 7 and fromCol == 4 and toCol ==  6 and toRow == 7:#short castle
                        temp = self.board[7][7]
                        self.board[7][7]=None
                        temp.row = 7
                        temp.col = 5
                        self.board[7][5] = temp
                        self.whiteHRookMoved =True
                    elif fromRow == 7 and fromCol == 4 and toRow == 7 and toCol == 2:#long castle
                        temp = self.board[7][0]
                        self.board[7][0]=None
                        temp.row = 7
                        temp.col = 3
                        self.board[7][3] = temp
                        self.whiteARookMoved =True
                    self.whiteKingMoved = True
                elif piece.color =='black':
                    if fromRow == 0 and fromCol == 4 and toCol ==  6 and toRow == 0:#short castle
                        temp = self.board[0][7]
                        self.board[0][7]=None
                        temp.row = 0
                        temp.col = 5
                        self.board[0][5] = temp
                        self.blackHRookMoved =True
                    elif fromRow == 0 and fromCol == 4 and toRow == 0 and toCol == 2:#long castle
                        temp = self.board[0][0]
                        self.board[0][0]=None
                        temp.row = 0
                        temp.col = 3
                        self.board[0][3] = temp
                        self.blackARookMoved =True
                    self.blackKingMoved = True
            elif isinstance(piece,Rook):
                if piece.color == 'white':
                    if fromRow == 7 and fromCol ==7 and self.whiteHRookMoved == False:
                        self.whiteHRookMoved =True
                    if fromRow == 7 and fromCol ==0 and self.whiteARookMoved == False:
                        self.whiteARookMoved =True
                if piece.color == 'black':
                    if fromRow == 0 and fromCol ==7 and self.whiteHRookMoved == False:
                        self.blackHRookMoved =True
                    if fromRow == 0 and fromCol ==0 and self.whiteARookMoved == False:
                        self.blackARookMoved =True

                    
                elif piece.color == 'black':
                    self.blackKingMoved == True
                    
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
    
    def isSquareAttacked(self,row,col,byColor):
        piece = self.board[row][col]
        #Pawn attack:
        if byColor == 'black':
            for dcol in [-1,1]:
                if 0<=row+1<8 and 0<=col+dcol<8:
                    if isinstance(self.board[row+1][col+dcol],Pawn) and self.board[row+1][col+dcol].color == byColor:
                        return True
        else:
            for dcol in [-1,1]:
                if 0<=row+1<8 and 0<=col+dcol<8:
                    if isinstance(self.board[row-1][col+dcol],Pawn) and self.board[row-1][col+dcol].color == byColor:
                        return True
        #Knight attack
        cdir = [(2,1),(2,-1),(1,2),(1,-2),(-1,2),(-1,-2),(-2,1),(-2,-1)]
        for drow,dcol in cdir:
            if 0<=row+drow<=7 and 0<=col+dcol<=7:
                if isinstance(self.board[row+drow][col+dcol],Knight) and self.board[row+drow][col+dcol].color == byColor:
                    return True
        #King attack
        cdir = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        for drow,dcol in cdir:
            if 0<=row+drow<=7 and 0<=col+dcol<=7:
                if isinstance(self.board[row+drow][col+dcol],King) and self.board[row+drow][col+dcol].color == byColor:
                    return True
        #Bishop & Queen attack
        cdir = [(1,1),(-1,1),(-1,-1),(1,-1)]
        for drow,dcol in cdir:
            r = row+drow
            c = col+dcol
            while 0<=r<8 and 0<=c<8:
                t = self.board[r][c]
                if t != None:
                    if (isinstance(t,Bishop) or isinstance(t,Queen)) and t.color == byColor:
                        return True
                    break
                r+= drow
                c+= dcol
        #Rook & Queen attack
        cdir = [(1,0),(0,1),(-1,0),(0,-1)]
        for drow,dcol in cdir:
            r = row+drow
            c = col+dcol
            while 0<=r<8 and 0<=c<8:
                t = self.board[r][c]
                if t != None:
                    if (isinstance(t,Rook) or isinstance(t,Queen)) and t.color == byColor:
                        return True
                    break
                r+= drow
                c+= dcol
        return False
    def isChecked(self,color):
        for row in range(8):
            for col in range(8):
                if isinstance(self.board[row][col],King) and self.board[row][col].color == color:
                    byColor = 'black' if color =='white' else 'white'
                    if self.isSquareAttacked(row,col,byColor):
                        return True
        return False
#Moves generators
def kingMoves(board,row,col):
    color = board.board[row][col].color
    moves = []
    cdir = [(-1,-1),(-1,0),(-1,1),
            (0,-1),(0,1),
            (1,-1),(1,0),(1,1)]
    for drow,dcol in cdir:
        r = row+drow
        c = col+dcol
        if 0<=r<=7 and 0<=c<=7:
            if board.board[row][col].isOpponent(board.board[r][c]):
                if color =='white':
                    if not board.isSquareAttacked(r,c,'black'):
                        moves.append((r,c))
                else:
                    if not board.isSquareAttacked(r,c,'white'):
                        moves.append((r,c))
    if board.board[row][col].color == 'white':
        if board.whiteKingMoved == False and board.whiteHRookMoved == False:#shortCastle
            if board.board[7][5] == None and board.board[7][6] == None and not board.isSquareAttacked(7,5,'black') and not board.isSquareAttacked(7,6,'black'):
                moves.append((7,6))
        if board.whiteKingMoved == False and board.whiteARookMoved == False:#longCastle
            if board.board[7][1] == None and board.board[7][2] == None and board.board[7][3]==None and not board.isSquareAttacked(7,1,'black') and not board.isSquareAttacked(7,2,'black') and not board.isSquareAttacked(7,3,'black'):
                moves.append((7,2))
    elif board.board[row][col].color == 'black':#short castle
        if board.blackKingMoved == False and board.blackHRookMoved == False:
            if board.board[0][5] == None and board.board[0][6] == None and not board.isSquareAttacked(0,5,'white') and not board.isSquareAttacked(0,6,'white'):
                moves.append((0,6))

        if board.blackKingMoved == False and board.blackARookMoved == False:
            if board.board[0][1] == None and board.board[0][2] == None and board.board[0][3]==None and not board.isSquareAttacked(0,1,'white') and not board.isSquareAttacked(0,2,'white') and not board.isSquareAttacked(0,3,'white'):
                moves.append((0,2))
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
                    if 0<=row-2<8 and board.board[row-1][col]==None and board.board[row-2][col]==None:
                        moves.append((r,col))
            else:
                if 0<=row-1<8 and board.board[row-1][col]==None:
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
                    if 0<=row+2<8 and board.board[row+1][col]==None and board.board[row+2][col]==None:
                        moves.append((r,col))
            else:
                if 0<=row+1<8 and board.board[row+1][col]==None:
                    moves.append((row+drow,col))
        for dcol in range(-1,2):
            if dcol!=0 and 0<=row+1<=7 and 0<=col+dcol<=7:
                target = board.board[row+1][col+dcol]
                if piece.isOpponent(target) and target!=None:
                    moves.append((row+1,col+dcol))
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
            if board.isChecked('white') and isinstance(board.board[row][col],King) and board.board[row][col].color == 'white':
                drawRect(col*cellSize,row*cellSize,cellSize,cellSize,fill = 'red',border = 'black')
            elif board.isChecked('black') and isinstance(board.board[row][col],King) and board.board[row][col].color == 'black':
                drawRect(col*cellSize,row*cellSize,cellSize,cellSize,fill = 'red',border = 'black')
            else:
                drawRect(col*cellSize,row*cellSize,cellSize,cellSize,fill = color,border = 'black')
            
    for row in range(8):
        for col in range(8):
            piece = board.board[row][col]
            url = ''
            if isinstance(piece,Rook):
                url = 'cmu://1073385/43649031/Rook.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43649038/RookB.png'
            elif isinstance(piece,Knight):
                url = 'cmu://1073385/43648951/Knight.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43648964/KnightB.png'
            elif isinstance(piece,Bishop):
                url = 'cmu://1073385/43648924/Bishop.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43648934/BishopB.png'
            elif isinstance(piece,Queen):
                url = 'cmu://1073385/43649001/Queen.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43649013/QueenB.png'
            elif isinstance(piece,King):
                url = 'cmu://1073385/43648943/King.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43648945/KingB.png'
            elif isinstance(piece,Pawn):
                url = 'cmu://1073385/43648969/Pawn.png'
                if piece.color == 'black':
                    url = 'cmu://1073385/43648981/PawnB.png'
            if url == '':
                pass
            else:
                pieceSize = 0.8*cellSize
                drawImage(url,col*cellSize+0.5*cellSize-0.5*pieceSize,row*cellSize+0.5*cellSize-0.5*pieceSize,width=pieceSize,height=pieceSize)
    drawRect(0,0,cellSize*8,cellSize*8,fill = None,border = 'black',borderWidth = 4.25)           

def onAppStart(app):
    starting(app)
    
def starting(app):
    app.width = 450
    app.height = 500
    app.board = initializeBoard()
    app.turn = 'white'
    app.piecePosition = []
    app.isSelected = False
    app.selectedSquare = None
    app.moves = []
    app.isWhiteTurn = True
    app.winner = None

def redrawAll(app):
    drawBoard(app,app.board)
    if app.isWhiteTurn:
        drawLabel("It is currently white's turn",(app.height-50)*2//4,(app.height-25),size = 20)
    else:
        drawLabel("It is currently black's turn",(app.height-50)*2//4,(app.height-25),size = 20)
    for row,col in app.moves:
        drawCircle(col*(app.height-50)//8+(app.height-50)//16,row*(app.height-50)//8+(app.height-50)//16,10,fill = 'yellow')
    if app.winner !=None:
        drawRect(0,0,app.width,app.height,fill='white')
        drawLabel(f'The winner is {app.winner}!',app.width//2,app.height//3,size = 20)
        drawLabel(f'Press R to Start a new game!',app.width//2,app.height*2//3,size = 20)
   

def onMousePress(app,mouseX,mouseY):
    cellSize = (app.height-50)//8
    row = mouseY//cellSize
    col = mouseX//cellSize
    if not (row>7 or col>7 or row<0 or col<0):#Click inside the board
        if app.isSelected == False:#You need to choose the piece you want to move
            piece = app.board.board[row][col]
            if piece != None:
                if (piece.color == 'white' and app.isWhiteTurn) or (piece.color == 'black' and not app.isWhiteTurn):
                    app.isSelected = True
                    app.selectedSquare = (row,col)
                    # print(f'isSelected,{type(app.board.board[row][col]).__name__} at {row},{col}')
                    app.moves = app.board.findLegalMoves(row,col)
                    if app.moves == []:
                        app.isSelected = False
                        app.selectedSquare = None
                
            else:
                app.isSelected = False
                app.selectedSquare = None
                # print(f'No selecting legal piece at {row},{col}')
                app.moves = []
        else:#you need to make your move
            if (row,col) not in app.moves :
                app.isSelected = False
                app.selectedSquare = None
                #print('It does not seems to be a legal move')
                app.moves = []
                piece = app.board.board[row][col]
                if piece != None:
                    if (piece.color == 'white' and app.isWhiteTurn) or (piece.color == 'black' and not app.isWhiteTurn):
                        app.isSelected = True
                        app.selectedSquare = (row,col)
                        # print(f'isSelected,{type(app.board.board[row][col]).__name__} at {row},{col}')
                        app.moves = app.board.findLegalMoves(row,col)
                        if app.moves == []:
                            app.isSelected = False
                            app.selectedSquare = None
            elif (row,col) in app.moves:
                fromR,fromC = app.selectedSquare
                app.board.doMove(fromR,fromC,row,col)
                app.isSelected = False
                app.selectedSquare = None
                app.moves = []
                app.isWhiteTurn = not app.isWhiteTurn
                # print(f'{type(app.board.board[row][col]).__name__} move from {(fromR,fromC)} to {(row,col)}')
                
    else:#click outside the board
        app.isSelected = False
        app.selectedSquare = None
        # print('Outside the board')
        app.moves = []
    if app.board.isWhiteLose == True and app.board.isBlackLose == False:
        app.winner = 'black'
    elif app.board.isBlackLose == True and app.board.isWhiteLose == False:
        app.winner = 'white'



def onKeyPress(app,key):
    if app.winner !=None:
        if key == 'r':
            starting(app)
    
    


    
def main():
    runApp()

main()
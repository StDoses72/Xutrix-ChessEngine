# Xutrix-ChessEngine
A self-developed chess engine

2025/11/09

Update the method of minimax. Choose the method of do a move, take snapshot, push the snapshot into stack, and undo the move by pop snapshot out from the stack to restore the board as well as the global variables.

2025/11/07

Finished building the mobility function. Introducing the mobility after one move, and the mobility of the board under the depth required. Also, to prevent the over-dependence on mobility, added the feature of mobility cap for each piece and the mobility coefficient for each piece in order to lock the mobility score in a reasonable scale. Add the idea of enpassant into the game

2025/11/06

Introduce the idea of mate. Allowing the engine the take mate as the top priority. Adjusted the some of the position json in order to let the engine to do more rational move, to become more like a human player. Take the status of game into the position consideration and introduce the position score cap, so that prevent the problem that the engine will over-consider the position score that leads to the loss of material.

2025/11/5

Apply the idea of Position Score into the function evaluateBoard(). The position score for this version is computed and modified based ion the use stockfish 17


2025/11/1


Apply the alpha-beta cutoff into the minimax process


Increase the time of findBestMove for depth of 4 from 1-2 min to around 15-30 sec




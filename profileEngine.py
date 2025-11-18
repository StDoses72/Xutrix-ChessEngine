import cProfile
import pstats
import engine

def run():
    # 运行一局固定深度的搜索（避免用户输入影响结果）
    board = engine.initializeBoard()
    ppm = engine.importPositionMap()
    # 让引擎搜索 2–3 层就能找到主要瓶颈
    engine.findBestMove(board, "white", 3, ppm)

if __name__ == "__main__":
    cProfile.run('run()', 'profile_stats.prof')
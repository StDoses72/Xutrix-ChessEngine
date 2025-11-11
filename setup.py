from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

# 输出当前解释器信息，方便确认版本
print(f"Building with Python {sys.version}")

extensions = [
    Extension(
        name="isSquareAttacked",
        sources=["isSquareAttacked.pyx"],
        extra_compile_args=["/O2"],  # 优化等级
        extra_link_args=[],
    )
]

setup(
    name="Xustrix",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "nonecheck": False,
            "initializedcheck": False,
        },
    ),
)
from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

print(f"Building with Python {sys.version}")

extensions = [
    Extension(
        name="isSquareAttacked",
        sources=["isSquareAttacked.pyx"],
        py_limited_api=True,                             # ★ 关键
        define_macros=[("Py_LIMITED_API", "0x03080000")],# ★ 关键
        extra_compile_args=["/O2"],
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
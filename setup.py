from setuptools import setup, Extension
from Cython.Build import cythonize
import sys, os


is_windows = sys.platform.startswith('win')

common_macros = [("Py_LIMITED_API", "0x03080000")]


common_compile_args = ["/O2"] if is_windows else ["-O2"]

extensions = [
    Extension(
        name="isSquareAttacked",
        sources=["isSquareAttacked.pyx"],
        py_limited_api=True,
        define_macros=common_macros,
        extra_compile_args=common_compile_args,
    ),
    Extension(
        name="movegen",
        sources=["movegen.pyx"],
        py_limited_api=True,
        define_macros=common_macros,
        extra_compile_args=common_compile_args,
    ),
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
        annotate=True,
    ),
)

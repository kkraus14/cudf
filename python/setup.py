# Copyright (c) 2018, NVIDIA CORPORATION.

import versioneer
import os
import sys

from setuptools import setup, find_packages
from setuptools.extension import Extension
from Cython.Build import cythonize
from distutils.sysconfig import get_python_lib


install_requires = [
    'numba',
    'cython'
]

cuda_include_dir = '/usr/local/cuda/include'
cuda_lib_dir = "/usr/local/cuda/lib"

if os.environ.get('CUDA_HOME', False):
    cuda_lib_dir = os.path.join(os.environ.get('CUDA_HOME'), 'lib64')
    cuda_include_dir = os.path.join(os.environ.get('CUDA_HOME'), 'include')

libs = ['cuda', 'cudf', 'rmm']

cython_files = ['cudf/bindings/*.pyx']

extensions = [
    Extension("*",
              sources=cython_files,
              include_dirs=[
                '../cpp/include/cudf',
                '../cpp/thirdparty/dlpack/include/dlpack/',
                os.path.join(sys.prefix, 'include'),
                cuda_include_dir
              ],
              library_dirs=[get_python_lib()],
              runtime_library_dirs=[
                os.path.join(sys.prefix, 'lib'),
                cuda_lib_dir
              ],
              libraries=libs,
              language='c++',
              extra_compile_args=['-std=c++11'])
]

setup(name='cudf',
      description="cuDF - GPU Dataframe",
      version=versioneer.get_version(),
      classifiers=[
        # "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        # "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7"
      ],
      # Include the separately-compiled shared library
      author="NVIDIA Corporation",
      setup_requires=['cython'],
      ext_modules=cythonize(extensions),
      packages=find_packages(include=['cudf', 'cudf.*']),
      install_requires=install_requires,
      license="Apache",
      cmdclass=versioneer.get_cmdclass(),
      zip_safe=False
      )

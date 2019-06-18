# Copyright (c) 2019, NVIDIA CORPORATION.

# cython: profile=False
# distutils: language = c++
# cython: embedsignature = True
# cython: language_level = 3

from cudf.bindings.cudf_cpp cimport *


cdef extern from "table.hpp" namespace "cudf" nogil:
    
    cdef cppclass table:

        table(gdf_column* cols[], gdf_size_type num_cols) except +

        table() except +

        gdf_column** begin() except +

        gdf_column** end() except +

        gdf_column* get_column(gdf_index_type index) except +
 
        gdf_size_type num_columns() except +

        gdf_size_type num_rows() except +

# Todo? add const overloads 
#        const gdf_column* const* begin() const except +
#        gdf_column const* const* end() const
#        gdf_column const* get_column(gdf_index_type index) const except +


# Temporary until we properly wrap RMM in Cython
cdef extern from "rmm/thrust_rmm_allocator.h" nogil:

    ctypedef size_t size_type

    cdef cppclass device_ptr[T]:
        T* get() except +

    cdef cppclass device_vector[T]:
        device_ptr[T] data() except +
        size_type size() except +

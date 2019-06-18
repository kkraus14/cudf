# Copyright (c) 2019, NVIDIA CORPORATION.

# cython: profile=False
# distutils: language = c++
# cython: embedsignature = True
# cython: language_level = 3

from cudf.bindings.cudf_cpp cimport *
from cudf.bindings.types cimport table as cudf_table
from cudf.bindings.types cimport device_vector
from libcpp.pair cimport pair


cdef extern from "groupby.hpp" nogil:
    
    cdef pair[cudf_table, device_vector*] gdf_group_by_without_aggregations(
        const cudf_table& input_table,
        gdf_size_type num_key_cols,
        const gdf_index_type* key_col_indices,
        gdf_context* context
    )

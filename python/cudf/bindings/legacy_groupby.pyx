# Copyright (c) 2018, NVIDIA CORPORATION.

# cython: profile=False
# distutils: language = c++
# cython: embedsignature = True
# cython: language_level = 3

# Copyright (c) 2018, NVIDIA CORPORATION.

from cudf.bindings.cudf_cpp cimport *
from cudf.bindings.cudf_cpp import *
from libc.stdint cimport uintptr_t
from libc.stdlib cimport free
from libcpp.vector cimport vector
cimport cython

import collections
import numpy as np
from pandas.api.types import is_categorical_dtype
from numbers import Number

from cudf.dataframe.dataframe import DataFrame
from cudf.dataframe.series import Series
from cudf.dataframe.buffer import Buffer
from cudf.dataframe.categorical import CategoricalColumn
from cudf.utils.cudautils import zeros
from cudf.bindings.nvtx import nvtx_range_pop
import cudf.dataframe.index as index
from librmm_cffi import librmm as rmm
import nvcategory
import nvstrings


cdef gdf_column** cols_view_from_cols(cols):
    col_count=len(cols)
    cdef gdf_column **c_cols = <gdf_column**>malloc(sizeof(gdf_column*)*col_count)

    cdef i
    for i in range(col_count):
        check_gdf_compatibility(cols[i])
        c_cols[i] = column_view_from_column(cols[i])

    return c_cols


cdef free_table(cudf_table* table, gdf_column** cols):
    cdef i
    cdef gdf_column *c_col
    for i in range(table[0].num_columns()) :
        c_col = table[0].get_column(i)
        free(c_col)

    del table
    free(cols)

def cpp_group_dataframe(self, levels):
    """Group dataframe.

    The output dataframe has the same number of rows as the input
    dataframe.  The rows are shuffled so that the groups are moved
    together in ascending order based on the multi-level index.

    Parameters
    ----------
    df : DataFrame
    levels : list[str]
        Column names for the multi-level index.

    Returns
    -------
    (df, segs) : namedtuple
        * df : DataFrame
            The grouped dataframe.
        * segs : Series.
                Group starting index.
    """
    # Handle empty dataframe
    if len(df) == 0:
        # Groupby on empty dataframe
        return df, Buffer(np.array([], dtype='int32'))

    # Prepare dataframe
    df = self._df.iloc[:, levels].reset_index(drop=True)
    df = df.to_frame() if isinstance(df, Series) else df
    input_columns = list(df.columns)

    # Prepare libcudf inputs
    in_cols = [series._column for series in df._cols.values()]
    cdef gdf_column** c_in_cols = cols_view_from_cols(in_cols)
    cdef cudf_table* c_in_table = new cudf_table(c_in_cols, col_count)
    cdef gdf_size_type c_num_key_cols = len(levels)
    key_col_indices = [df._cols.keys().index(val) for val in levels]
    cdef vector[gdf_index_type] c_key_col_indices = key_col_indices
    cdef gdf_context* c_context = create_context_view(0, 'sort', 0, 0, 0, 'null_as_largest')

    # Perform grouping
    with nogil:
        cdef pair[cudf_table, device_vector*] c_result = gdf_group_by_without_aggregations(
            <cudf_table&> c_input_table[0],
            <gdf_size_type> c_num_key_cols,
            <gdf_index_type*> c_key_col_indices.data(),
            <gdf_context*> c_context
        )

    # Convert libcudf objects to Python objects
    cdef cudf_table c_out_table = c_result.first
    cdef gdf_column* c_tmp_col = NULL
    out_df = cudf.DataFrame()
    for idx, colname in enumerate(input_columns):
        out_df[colname] = 

    # Jake is changing this to return a std::unique_ptr that I'll have to release and later
    cdef device_vector* c_out_segments = c_result.second

    # Free libcudf inputs
    free_table(c_in_table, c_in_cols)
    free(c_context)

    # Finish
    return _dfsegs_pack(df=out_df, segs=segs)

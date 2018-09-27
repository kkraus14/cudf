"""
Provides base classes and utils for implementing type-specific logical
view of Columns.
"""

import numpy as np
import pandas as pd
import pyarrow as pa

from numba import cuda, njit

from .buffer import Buffer
from . import utils, cudautils
from .column import Column


class TypedColumnBase(Column):
    """Base class for all typed column
    e.g. NumericalColumn, CategoricalColumn

    This class provides common operations to implement logical view and
    type-based operations for the column.

    Notes
    -----
    For designed to be instantiated directly.  Instantiate subclasses instead.
    """
    def __init__(self, **kwargs):
        dtype = kwargs.pop('dtype')
        super(TypedColumnBase, self).__init__(**kwargs)
        # Logical dtype
        self._dtype = dtype

    @property
    def dtype(self):
        return self._dtype

    def is_type_equivalent(self, other):
        """Is the logical type of the column equal to the other column.
        """
        mine = self._replace_defaults()
        theirs = other._replace_defaults()

        def remove_base(dct):
            # removes base attributes in the phyiscal layer.
            basekeys = Column._replace_defaults(self).keys()
            for k in basekeys:
                del dct[k]

        remove_base(mine)
        remove_base(theirs)

        return type(self) == type(other) and mine == theirs

    def _replace_defaults(self):
        params = super(TypedColumnBase, self)._replace_defaults()
        params.update(dict(dtype=self._dtype))
        return params

    def argsort(self, ascending):
        _, inds = self.sort_by_values(ascending=ascending)
        return inds

    def sort_by_values(self, ascending):
        raise NotImplementedError


def column_empty_like(column, dtype, masked):
    """Allocate a new column like the given *column*
    """
    data = cuda.device_array(shape=len(column), dtype=dtype)
    params = dict(data=Buffer(data))
    if masked:
        mask = utils.make_mask(data.size)
        params.update(dict(mask=Buffer(mask), null_count=data.size))
    return Column(**params)


def column_empty_like_same_mask(column, dtype):
    """Create a new empty Column with the same length and the same mask.

    Parameters
    ----------
    dtype : np.dtype like
        The dtype of the data buffer.
    """
    data = cuda.device_array(shape=len(column), dtype=dtype)
    params = dict(data=Buffer(data))
    if column.has_null_mask:
        params.update(mask=column.nullmask)
    return Column(**params)


def column_select_by_boolmask(column, boolmask):
    """Select by a boolean mask to a column.

    Returns (selected_column, selected_positions)
    """
    from .numerical import NumericalColumn
    assert column.null_count == 0  # We don't properly handle the boolmask yet
    boolbits = cudautils.compact_mask_bytes(boolmask.to_gpu_array())
    indices = cudautils.arange(len(boolmask))
    _, selinds = cudautils.copy_to_dense(indices, mask=boolbits)
    _, selvals = cudautils.copy_to_dense(column.data.to_gpu_array(),
                                         mask=boolbits)

    selected_values = column.replace(data=Buffer(selvals))
    selected_index = Buffer(selinds)
    return selected_values, NumericalColumn(data=selected_index,
                                            dtype=selected_index.dtype)


def as_column(arbitrary):
    """Create a Column from an arbitrary object

    Currently support inputs are:

    * ``Column``
    * ``Buffer``
    * numba device array
    * numpy array
    * pandas.Categorical

    Returns
    -------
    result : subclass of TypedColumnBase
        - CategoricalColumn for pandas.Categorical input.
        - NumericalColumn for all other inputs.
    """
    from . import numerical, categorical, datetime

    if isinstance(arbitrary, Column):
        if not isinstance(arbitrary, TypedColumnBase):
            # interpret as numeric
            data = arbitrary.view(numerical.NumericalColumn,
                                  dtype=arbitrary.dtype)
        else:
            data = arbitrary

    elif isinstance(arbitrary, pd.Categorical):
        data = categorical.pandas_categorical_as_column(arbitrary)
        mask = ~pd.isnull(arbitrary)
        data = data.set_mask(cudautils.compact_mask_bytes(mask))

    elif isinstance(arbitrary, Buffer):
        data = numerical.NumericalColumn(data=arbitrary, dtype=arbitrary.dtype)

    elif cuda.devicearray.is_cuda_ndarray(arbitrary):
        data = as_column(Buffer(arbitrary))
        if data.dtype in [np.float16, np.float32, np.float64]:
            mask = cudautils.mask_from_devary(arbitrary)
            data = data.set_mask(mask)

    elif isinstance(arbitrary, np.ndarray):
        if arbitrary.dtype.kind == 'M':
            # hack, coerce to int, then set the dtype
            data = datetime.DatetimeColumn.from_numpy(arbitrary)
        else:
            data = as_column(Buffer(arbitrary))
            if np.count_nonzero(np.isnan(arbitrary)) > 0:
                mask = ~np.isnan(arbitrary)
                data = data.set_mask(cudautils.compact_mask_bytes(mask))

    elif isinstance(arbitrary, (list,)):
        if any(x is None for x in arbitrary):
            if all((isinstance(x, int) or x is None) for x in arbitrary):
                padata = pa.array(arbitrary)
                npdata = np.asarray(padata.buffers()[1]).view(np.int64)
                data = as_column(npdata)
                mask = np.asarray(padata.buffers()[0])
                data = data.set_mask(mask)
            elif all((isinstance(x, ) or x is None) for x in arbitrary):
                padata = pa.array(arbitrary)
                npdata = np.asarray(padata.buffers()[1]).view(np.float64)
                data = as_column(npdata)
                mask = np.asarray(padata.buffers()[0])
                data = data.set_mask(mask)
        else:
            data = as_column(np.asarray(arbitrary))

    else:
        data = as_column(np.asarray(arbitrary))

    return data


def column_applymap(udf, column, out_dtype):
    """Apply a elemenwise function to transform the values in the Column.

    Parameters
    ----------
    udf : function
        Wrapped by numba jit for call on the GPU as a device function.
    column : Column
        The source column.
    out_dtype  : numpy.dtype
        The dtype for use in the output.

    Returns
    -------
    result : Buffer
    """
    core = njit(udf)
    results = cuda.device_array(shape=len(column), dtype=out_dtype)
    values = column.data.to_gpu_array()
    if column.mask:
        # For masked columns
        @cuda.jit
        def kernel_masked(values, masks, results):
            i = cuda.grid(1)
            # in range?
            if i < values.size:
                # valid?
                if utils.mask_get(masks, i):
                    # call udf
                    results[i] = core(values[i])

        masks = column.mask.to_gpu_array()
        kernel_masked.forall(len(column))(values, masks, results)
    else:
        # For non-masked columns
        @cuda.jit
        def kernel_non_masked(values, results):
            i = cuda.grid(1)
            # in range?
            if i < values.size:
                # call udf
                results[i] = core(values[i])

        kernel_non_masked.forall(len(column))(values, results)
    # Output
    return Buffer(results)

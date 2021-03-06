"""
A module for data processing and internal data display functions.
Provides functions that manipulate gridded data into other forms, display
grids as tables, and extract interesting statistics from gridded data such
as sample means.
"""

from typing import List, Tuple, Callable, Union
from math import sqrt, floor, log10, nan, isnan
import numpy as np

X067_EXPECTED = [[nan, nan, nan, nan],
                 [nan, nan, nan, nan],
                 [nan, nan, nan, nan],
                 [-3.2, -3.3, nan, nan],
                 [-3.4, -3.4, -3.3, -3.4],
                 [-3.3, -3.3, -3.4, -3.4],
                 [-3.1, -3.2, -3.3, -3.2],
                 [-3.1, -3.1, -3.2, -3.1],
                 [-3.0, -3.0, -3.1, -3.0],
                 [-3.1, -3.0, -3.0, -3.0],
                 [-3.1, -3.1, -3.0, -3.1],
                 [-3.3, -3.2, -3.1, -3.1],
                 [-3.4, -3.4, -3.2, -3.3],
                 [-3.2, -3.3, -3.3, -3.4],
                 [-3.0, -3.2, -3.4, -3.3],
                 [-2.9, -3.0, -3.4, -3.1],
                 [nan, nan, nan, nan],
                 [nan, nan, nan, nan]]


X1_EXPECTED = [nan, nan, nan, nan] * 3\
    + [0, 0, nan, nan]\
    + [[0] * 4] * 12\
    + [nan, nan, nan, nan] * 2


X15_EXPECTED = [[nan, nan, nan, nan],
                [nan, nan, nan, nan],
                [nan, nan, nan, nan],
                [3.8, 3.7, nan, nan],
                [3.6, 3.7, 3.8, 3.7],
                [3.4, 3.5, 3.7, 3.5],
                [3.2, 3.2, 3.4, 3.3],
                [3.2, 3.2, 3.2, 3.2],
                [3.1, 3.1, 3.2, 3.2],
                [3.2, 3.2, 3.1, 3.1],
                [3.5, 3.2, 3.1, 3.2],
                [3.5, 3.3, 3.2, 3.5],
                [3.7, 3.6, 3.3, 3.5],
                [3.7, 3.8, 3.4, 3.7],
                [3.4, 3.7, 3.6, 3.8],
                [3.3, 3.4, 3.8, 3.6],
                [nan, nan, nan, nan],
                [nan, nan, nan, nan]]


X2_EXPECTED = [[nan, nan, nan, nan],
               [nan, nan, nan, nan],
               [nan, nan, nan, nan],
               [6.0, 6.1, nan, nan],
               [5.8, 6.0, 6.0, 6.0],
               [5.5, 5.6, 5.8, 5.6],
               [5.2, 5.3, 5.5, 5.4],
               [5.0, 5.0, 5.2, 5.1],
               [4.9, 4.9, 5.0, 5.0],
               [5.0, 5.0, 4.9, 4.9],
               [5.2, 5.0, 4.9, 5.0],
               [5.6, 5.4, 5.0, 5.2],
               [6.0, 5.8, 5.4, 5.6],
               [6.1, 6.1, 5.5, 6.0],
               [6.1, 6.1, 5.8, 6.1],
               [6.0, 6.1, 6.0, 6.1],
               [nan, nan, nan, nan],
               [nan, nan, nan, nan]]


X25_EXPECTED = [[nan, nan, nan, nan],
                [nan, nan, nan, nan],
                [nan, nan, nan, nan],
                [7.9, 8.0, nan, nan],
                [7.7, 7.9, 7.9, 7.9],
                [7.0, 7.2, 7.7, 7.4],
                [6.7, 6.8, 7.0, 7.0],
                [6.6, 6.6, 6.7, 6.7],
                [6.4, 6.4, 6.6, 6.6],
                [6.6, 6.4, 6.3, 6.4],
                [6.7, 6.6, 6.3, 6.6],
                [7.2, 7.0, 6.6, 6.7],
                [7.9, 7.6, 6.9, 7.3],
                [8.0, 7.9, 7.0, 7.9],
                [8.0, 8.0, 7.6, 7.8],
                [7.9, 8.0, 7.9, 8.0],
                [nan, nan, nan, nan],
                [nan, nan, nan, nan]]


X3_EXPECTED = [[nan, nan, nan, nan],
               [nan, nan, nan, nan],
               [nan, nan, nan, nan],
               [9.4, 9.5, nan, nan],
               [9.1, 9.2, 9.4, 9.3],
               [8.6, 8.7, 9.1, 8.8],
               [7.9, 8.1, 8.6, 8.3],
               [7.4, 7.5, 8.0, 7.6],
               [7.3, 7.3, 7.4, 7.4],
               [7.4, 7.3, 7.2, 7.3],
               [7.9, 7.5, 7.2, 7.5],
               [8.7, 8.3, 7.5, 7.9],
               [9.3, 9.0, 8.2, 8.8],
               [9.5, 9.4, 8.6, 8.8],
               [9.3, 9.5, 8.9, 9.5],
               [9.1, 9.3, 9.4, 9.4],
               [nan, nan, nan, nan],
               [nan, nan, nan, nan]]


def convert_grid_data_to_table(data: np.ndarray) -> np.ndarray:
    """
    Returns an array, representing the average values within the latitude
    bands in the gridded data provided.

    The array is structured such that the first index indicates latitude,
    measured in how many latitude bands exist between the index in question
    and the south pole. For example, index 0 into the second dimension of
    the array has 0 bands between it and the south pole, and is therefore
    the southernmost band.

    The second index in the return array represents time, divided into as
    many segments as the grids were built on. That is, the length of the
    array's first dimension will be equal to the length of the array
    passed in, as the length of that list is the number of time segments.

    Precondition:
        data.ndim >= 2

    :param data:
        A gridded data array, in the standard form of LatLongGrid data
    :return:
        An array of average values for each latitude band in the data
    """
    if data.ndim == 2:
        # Assume the data is already in tabular form.
        return data
    elif data.ndim == 3:
        table = []

        # Order of time and latitude dimensions must be switched, in addition
        # to the aggregating over latitude bands.
        for lat_band in range(data.shape[1]):
            row = []
            for time_seg in range(data.shape[0]):
                # Find the average for this latitude band
                data_slice = data[time_seg, lat_band, :]
                avg = mean(data_slice)
                row.append(avg)
            # Build a table from each time-segment row.
            table.append(row)
        return np.array(table)
    else:
        # No reordering of dimensions needs to happen above the 3rd dimension.
        table = convert_grid_data_to_table(data[0])
        for row in data[1:]:
            # Append the new row to the end of the accumulated array's
            # second-from-highest dimension.
            table = np.hstack((table, convert_grid_data_to_table(row)))
        return table


def _format_row(cell_values: List,
                length: int = 10) -> str:
    """
    Convert a list of values into a string, formatted like a row in a table.

    The values in the list are separated by dividers, and are truncated or
    padded until their length is equal to the optional length parameter, or
    10 characters by default.

    :param cell_values:
        A list of values to be converted to a row in a table
    :param length:
        The length, in characters, of each entry in the table
    :return:
        A string with the values formatted into a table row
    """
    cells = []
    for i in range(len(cell_values)):
        cells.append(str(cell_values[i]))

        # Correct the string to be the appropriate length, padding with
        # whitespace when needed.
        if len(cells[i]) > length:
            cells[i] = cells[i][:length]
        elif len(cells[i]) < length:
            cells[i] = cells[i].ljust(length, " ")

    return " | ".join(cells)


def convert_table_to_strs(table: np.ndarray) -> List[str]:
    """
    The table contains averaged values latitude bands within each grid.
    It is returned as a list, where each index in the list is a row in the
    table. This is so that multiple tables can be concatenated horizontally,
    by joining corresponding rows from two different tables.

    The table's horizontal dimension represents time, with columns further to
    the right being later on. The table's vertical dimension represents
    latitude, with the top marking the northernmost bands and the bottom
    marking the southernmost bands.

    :param table:
        A table containing data with
    :return:
        A table containing a single datapoint from each latitude band in the
        grids, with one row of the table per index in the list
    """
    headings = ["Division {}".format(i) for i in range(1, len(table[0]) + 1)]
    cell_length = int(floor(log10(len(table)))) + 10

    strs_table = []

    # Rows are returned in reverse order. Add them sequentially to the table.
    for row in table:
        strs_table.append(_format_row(row, cell_length))

    # Add the second and first rows of headers to the table.
    strs_table.append(_format_row(["-" * cell_length] * len(table[0]),
                                  cell_length))
    strs_table.append(_format_row(headings, cell_length))

    # Reverse the order of the rows, so that headers appear at the top, and
    # higher latitudes appear earlier.
    strs_table.reverse()
    return strs_table


def merge_str_tables(table1: List[str],
                     table2: List[str],
                     sep: str = " " * 12) -> List[str]:
    """
    Display two tables of results adjacent to each other.

    Table1 will take up its position on the left, and table2 on the right.
    The two will be separated horizontally by the optional sep parameter,
    or by 12 spaces if none is given.

    Precondition:
        len(table1) == len(table2)

    :param table1:
        The table positioned on the left
    :param table2:
        The table positioned on the right
    :param sep:
        The string that separates the two tables horizontally
    :return:
        A new table containing both original tables side by side
    """
    if len(table1) != len(table2):
        raise IndexError("Both tables must have the same length"
                         "(have {}, {})".format(len(table1), len(table2)))

    table3 = []
    # Connect adjacent table rows with the separator inbetween.
    for i in range(len(table1)):
        table3.append(sep.join([table1[i], table2[i]]))

    return table3


def print_tables(*tables) -> None:
    """
    Print all the tables provided as arguments, all adjacent to each other
    and separated by 12 spaces.

    Tables are two-dimensional array-like objects. For best appearances,
    all tables should have the same dimensions.

    :param tables:
        A series of arrays containing tabular data
    """
    first = tables[0]
    first_as_strs = convert_table_to_strs(first)

    for extra in tables[1:]:
        extra_as_strs = convert_table_to_strs(extra)
        first_as_strs = merge_str_tables(first_as_strs, extra_as_strs)

    # Print gaps before and after the tables for a cleaner output appearance.
    print()
    for row in first_as_strs:
        print(row)
    print()


def sum_table(table: Union[np.ndarray, int],
              modifier: Callable[[int], int] = lambda x: x)\
        -> Tuple[int, int]:
    """
    Calculate a sum of all elements in table. An optional second argument
    specifies a transformation that is performed on each element individually.

    Returns two numbers: The first is the sum over the elements, and the
    second is the number of elements considered. Any elements with value
    None or nan are not considered. If no elements in the whole table are
    valid, then 0 and 0 are returned.

    :param table:
        An array of numbers, including None and nan values
    :param modifier:
        An optional transformation to apply to each number
    :return:
        The sum of the elements in the table with the given transformation,
        and the number of elements that contributed to the sum
    """
    if isinstance(table, np.ndarray):
        total = 0
        num_valid_elems = 0

        # The sums and valid element counts in each subarray contribute
        # directly to the corresponding counts at this level.
        for subarray in table:
            sub_total, sub_valid_cells = sum_table(subarray, modifier)
            total += sub_total
            num_valid_elems += sub_valid_cells

        return total, num_valid_elems
    elif not isnan(table) and table is not None:
        # table is a single number.
        return modifier(table), 1
    else:
        # table is either None or nan, and thus invalid.
        return 0, 0


def mean(data: np.ndarray) -> float:
    """
    Returns the average value of all valid numeric elements in data.
    An element is valid if it is not None or nan.

    :param data:
        An array of numbers
    :return:
        The average amongst valid numbers
    """
    try:
        sum_cells, num_valid_cells = sum_table(data, lambda x: x)
        smpl_mean = sum_cells / num_valid_cells
        return smpl_mean
    except ZeroDivisionError:
        return nan


def variance(data: np.ndarray) -> float:
    """
    Returns the variance within all valid numeric elements in data.
    An element is valid if it is not None or nan.

    :param data:
        An array of numbers
    :return:
        The variance of the valid numbers
    """
    try:
        sum_sqrs, num_valid_cells = sum_table(data, lambda x: x ** 2)
        smpl_variance = sum_sqrs / num_valid_cells
        return smpl_variance
    except ZeroDivisionError:
        return nan


def std_dev(data: np.ndarray) -> float:
    """
    Returns the standard deviation within all valid numeric elements in data.
    An element is valid if it is not None or nan.

    :param data:
        An array of numbers
    :return:
        The standard deviation of the valid numbers
    """
    smpl_std_dev = sqrt(variance(data))
    return smpl_std_dev

"""
.. moduleauthor:: Li, Wang <wangziqi@foreseefund.com>
"""

from functools import partial
import abc
import logging

from pandas.tseries.index import DatetimeIndex

from orca import logger
from orca import (
        DATES,
        SIDS)
from orca.mongo import util as mongo_util
from orca.utils import date as date_util

class FilterBase(object):
    """Base class for filters.

    :param boolean debug_on: Enable/Disable debug level messages. Default: True
    :param boolean datetime_index: Whether to use DatetimeIndex or list of date strings. Default: False
    :param boolean reindex: Whether to use full sids as columns in DataFrame. Default: False
    :param boolean date_check: Whethter to check if passed date-related parameters are valid. Default: False

    .. notes::

       This is a base class and should not be used directly.
    """

    __metaclass__ = abc.ABCMeta

    LOGGER_NAME = 'universe'

    def __init__(self, **kwargs):
        self.logger = logger.get_logger(FilterBase.LOGGER_NAME)
        self.set_debug_mode(kwargs.get('debug_on', True))
        self.datetime_index = kwargs.get('datetime_index', False)
        self.reindex = kwargs.get('reindex', False)
        self.date_check = kwargs.get('date_check', False)
        self.__dict__.update(kwargs)

    def set_debug_mode(self, debug_on):
        """Enable/Disable debug level message in data fetchers.
        This is enabled by default."""
        level = logging.DEBUG if debug_on else logging.INFO
        self.logger.setLevel(level)

    def debug(self, msg):
        """Logs a message with level DEBUG on the alpha logger."""
        self.logger.debug(msg)

    def info(self, msg):
        """Logs a message with level INFO on the alpha logger."""
        self.logger.info(msg)

    def warning(self, msg):
        """Logs a message with level WARNING on the alpha logger."""
        self.logger.warning(msg)

    def error(self, msg):
        """Logs a message with level ERROR on the alpha logger."""
        self.logger.error(msg)

    def critical(self, msg):
        """Logs a message with level CRITICAL on the alpha logger."""
        self.logger.critical(msg)

    def format(self, df):
        """Format a dataframe by ``datetime_index`` and ``reindex``."""
        if self.reindex:
            df = df.reindex(columns=SIDS).fillna(False)
        if self.datetime_index:
            df.index = date_util.to_datetime(df.index)
            return df.astype(bool)
        return df

    @abc.abstractmethod
    def filter(self, startdate, enddate=None, parent=None):
        """Override (**mandatory**) to filter out a universe within two endpoints.

        :param startdate: The *left* (may not be the actual) endpoint
        :type startdate: str, int
        :param enddate: The right endpoint. Default: None, defaults to the last date
        :type enddate: str, int, None
        :param DataFrame parent: The super- or parent-universe to be filtered. Default: None
        :rtype: DataFrame
        """

        raise NotImplementedError

    def filter_daily(self, date, offset=True, parent=None):
        """Filter out a universe on a certain day. A helper method.

        :param date: The base point
        :type date: str, int
        :param int offset: The offset w.r.t. the ``date``. The actual date is calculated from ``date`` and ``offset``. Default: 0
        :param DataFrame parent: The super- or parent-universe to be filtered. Default: None
        :rtype: Series
        """

        date = mongo_util.compliment_datestring(str(date), -1, self.date_check)
        di, date = mongo_util.parse_date(DATES, date, -1)
        date = DATES[di-offset]
        return self.filter(date, date).iloc[0]


class DataFilter(FilterBase):
    """Base class for filters based on data(s).

    :param list datas: Its element is 2/3-tuple as (dname, fetcherclass[, kwargs]). The purpose is to
    instantiate a fetcher object by calling ``fetcherclass(**kwargs)`` and then use the fetching methods
    to fetch data ``dname``
    :param function synth: Function to synthesis these fetched datas
    :param int window: Used as in ``pd.rolling_apply(arg, window, ...)``. It is also used in determining
    data fetching window, thus is worthy to be seperated from ``rule``
    :param function rule: When called in ``rule(window)``, it returns a function that can be applied on
    DataFrame objects. Thus ``rule(window)(df)`` should be equivalent to
    ``pd.rolling_apply(df, window, func, ...)``
    :param int delay: Delay of the underlying data. Default: 1, which means, loosely speaking, universe
    on ``DATES[di]`` is filtered out using datas up to ``DATES[di-1]``
    """

    def __init__(self, datas, synth, window, rule, delay=1, **kwargs):
        FilterBase.__init__(self, **kwargs)
        self.delay = delay
        self.rule = rule
        self.window = window
        self.synth = synth
        self.datas = []
        for data in datas:
            dname, fetcherclass = data[0], data[1]
            dct = {'datetime_index': self.datetime_index,
                   'reindex': self.reindex,
                   'debug_on': self.logger.level == logging.DEBUG,
                   'date_check': self.date_check}
            if len(data) == 3:
                dct.update(data[2])
            self.datas.append(partial(fetcherclass(**dct).fetch_window, dname))

    def filter(self, startdate, enddate=None, parent=None):
        univ_window = mongo_util.cut_window(
                DATES,
                mongo_util.compliment_datestring(str(startdate), -1, self.date_check),
                mongo_util.compliment_datestring(str(enddate), 1, self.date_check) if enddate is not None else None)
        si, ei = map(DATES.index, [univ_window[0], univ_window[-1]])
        data_window = DATES[si-self.delay-(self.window-1): ei-self.delay+1]

        dfs = []
        for data in self.datas:
            df = data(data_window)
            df.index = DATES[si-(self.window-1): ei+1]
            dfs.append(df)
        df = self.synth(*dfs)

        if parent is not None:
            if isinstance(parent.index, DatetimeIndex):
                parent = parent.ix[date_util.to_datetime(df.index)]
            else:
                parent = parent.ix[date_util.to_datestr(df.index)]
            parent = parent.fillna(method='bfill').fillna(False)
            df[~parent] = None

        df = self.rule(self.window)(df)
        if parent is not None:
            df[~parent] = False
        df = df.iloc[self.window-1:]
        df.index = univ_window
        return self.format(df)


class SimpleDataFilter(DataFilter):
    """Base class for filters based on a **single** data.

    :param tuple data: Like ``(dname, fetcherclass[, kwargs])``
    """

    def __init__(self, data, window, rule, delay=1, **kwargs):
        DataFilter.__init__(self, [data], lambda x: x, window, rule, delay=delay, **kwargs)
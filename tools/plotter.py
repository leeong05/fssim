"""
.. moduleauthor:: Li, Wang <wangziqi@foreseefund.com>
"""

import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import magic

from orca.mongo.kday import UnivFetcher
univ_fetcher = UnivFetcher(datetime_index=True, reindex=True)

from orca.perf.performance import (
        Performance,
        IntPerformance,
        )
from orca.perf.plotter import Plotter
from orca.utils.io import read_frame


if __name__ == '__main__':
    import argparse
    import cPickle

    parser = argparse.ArgumentParser()
    parser.add_argument('alpha', help='Alpha file')
    parser.add_argument('--ftype', help='File type', choices=('csv', 'pickle', 'msgpack'))
    parser.add_argument('--atype', help='Alpha type', choices=('daily', 'intraday', 'perf'))
    parser.add_argument('--univ', help='Universe name', type=str)
    parser.add_argument('--which', help='Only used for intraday alpha', choices=('daily', 'trading', 'holding'), default='trading')
    parser.add_argument('-i', '--index', type=str,
        help='Name of the index, for example: HS300. Set this only when --longonly is turned on')
    parser.add_argument('-q', '--quantile', type=float,
        help='When --longonly is turned on, this can be negative to choose the bottom quantile; when not, this sets a threshold to choose tail quantiles')
    parser.add_argument('-n', '--number', type=int,
        help='When --longonly is turned on, this can be negative to choose the bottom; when not, this sets a threshold to choose tail')
    parser.add_argument('-l', '--longonly', action='store_true',
        help='Whether to test this alpha as a longonly holding')
    parser.add_argument('-p', '--plot', default=['pnl'], nargs='+',
        help='What to plot? Could by any combination of ("pnl", "returns", "ic", "turnover", "ac")')
    parser.add_argument('-b', '--by', choices=('A', 'Q', 'M', 'W'), help='Summary period', default='A')
    parser.add_argument('-c', '--cost', type=float, default=0.001, help='Linear trading cost')
    parser.add_argument('--plot_index', help='Add index data for "pnl"/"returns" plot', action='store_true')
    parser.add_argument('--ma', type=int,
        help='For "ic"/"ac"/"turnover" plot, use simple moving average to smooth')
    parser.add_argument('--periods', help='Periods used in calculation of IC and AC', type=int, default=1)
    parser.add_argument('--pdf', help='Save plots in a PDF file', type=str)
    parser.add_argument('--png', type=str, help='PNG file to save the plot')
    parser.add_argument('-s', '--start', type=str, help='Starting date')
    parser.add_argument('-e', '--end', type=str, help='Ending date')
    args = parser.parse_args()

    if args.pdf and os.path.exists(args.pdf):
        with magic.Magic() as m:
            ftype = m.id_filename(args.pdf)
            if ftype[:3] != 'PDF':
                print 'The argument --pdf if exists must be a PDF file'
                exit(0)
    if args.png and os.path.exists(args.png):
        with magic.Magic() as m:
            ftype = m.id_filename(args.png)
            if ftype[:3] != 'PNG':
                print 'The argument --png if exists must be a PNG file'
                exit(0)

    if args.atype == 'perf':
        with open(args.alpha) as file:
            perf = cPickle.load(file)
            if hasattr(perf, 'freq'):
                args.atype = 'intraday'
            else:
                args.atype = 'daily'
    else:
        alpha = read_frame(args.alpha, args.ftype)
        if args.atype is None:
            if len(alpha.index) == len(np.unique(alpha.index.date)):
                args.atype = 'daily'
            else:
                args.atype = 'intraday'

        if args.atype == 'intraday':
            perf = IntPerformance(alpha)
        else:
            perf = Performance(alpha)

    if args.univ:
        dates = np.unique([dt.strftime('%Y%m%d') for dt in perf.alpha.index])
        univ = univ_fetcher.fetch_window(args.univ, dates)
        perf = perf.get_universe(univ)

    if args.longonly:
        if args.quantile:
            if args.quantile > 0:
                analyser = perf.get_qtop(args.quantile, index=args.index)
            else:
                analyser = perf.get_qbottom(-args.quantile, index=args.index)
        elif args.number:
            if args.number > 0:
                analyser = perf.get_ntop(args.number, index=args.index)
            else:
                analyser = perf.get_nbottom(-args.number, index=args.index)
    else:
        if args.quantile:
            analyser = perf.get_qtail(args.quantile)
        elif args.number:
            analyser = perf.get_ntail(args.number)
        else:
            analyser = perf.get_longshort()

    plotter = Plotter(analyser)
    figs = []
    if 'pnl' in args.plot:
        fig = plotter.plot_pnl(cost=args.cost, index=args.index, plot_index=args.plot_index,
                drawdown=True, startdate=args.start, enddate=args.end, which=args.which)
        figs.append(fig)
    if 'returns' in args.plot:
        fig = plotter.plot_returns(args.by, index=args.index, plot_index=args.plot_index,
                startdate=args.start, enddate=args.end, which=args.which)
        figs.append(fig)
    if 'ic' in args.plot:
        fig = plotter.plot_ic(n=args.periods, rank=True, ma=args.ma,
                startdate=args.start, enddate=args.end, which=args.which)
        figs.append(fig)
    if 'turnover' in args.plot:
        fig = plotter.plot_turnover(ma=args.ma, startdate=args.start, enddate=args.end, which=args.which)
        figs.append(fig)

    if args.pdf:
        pp = PdfPages(args.pdf)
        for fig in figs:
            pp.savefig(fig)
        pp.close()
        print 'Saved plots in {}'.format(args.pdf)
    elif args.png:
        for i, fig in enumerate(figs):
            fig.savefig(str(i)+'_'+args.png)
        print 'Saved plots in 0-{}_{}'.format(len(figs), args.pdf)
    else:
        plt.show()

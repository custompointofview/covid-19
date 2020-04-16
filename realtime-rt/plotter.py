#!/usr/bin/env python
import json
import os

import pandas as pd
import numpy as np

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, num2date
from matplotlib import dates as mdates
from matplotlib import ticker
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from scipy import stats as sps
from scipy.interpolate import interp1d


# from IPython.display import clear_output


class PlotUtils:
    # We create an array for every possible value of Rt
    R_T_MAX = 12
    r_t_range = np.linspace(0, R_T_MAX, R_T_MAX * 100 + 1)

    # Gamma is 1/serial interval
    # https://wwwnc.cdc.gov/eid/article/26/6/20-0357_article
    GAMMA = 1 / 4

    def __init__(self, path):
        self.dump_dir_path = path
        self.dump_info_dir_path = os.path.join(path, 'results')
        self.debug = False

    def create_dump_dir(self):
        if not os.path.exists(self.dump_dir_path):
            os.makedirs(self.dump_dir_path)
        if not os.path.exists(self.dump_info_dir_path):
            os.makedirs(self.dump_info_dir_path)

    def highest_density_interval(self, pmf, p=.95):
        # print("\tPreparing HDI...      ", end="", flush=True)
        # If we pass a DataFrame, just call this recursively on the columns
        if isinstance(pmf, pd.DataFrame):
            return pd.DataFrame([self.highest_density_interval(pmf[col]) for col in pmf],
                                index=pmf.columns)

        if all(np.isnan(pmf.values)):
            return pd.Series([0, 0], index=['Low', 'High'])
        cumsum = np.cumsum(pmf.values)
        best = None
        for i, value in enumerate(cumsum):
            for j, high_value in enumerate(cumsum[i + 1:]):
                if (high_value - value > p) and (not best or j < best[1] - best[0]):
                    best = (i, i + j + 1)
                    break
        low = pmf.index[best[0]]
        high = pmf.index[best[1]]
        series = pd.Series([low, high], index=['Low', 'High'])
        # print("[DONE]")
        return series

    def get_posteriors(self, sr, window=7, min_periods=1):
        print("\tPreparing posteriors...\t\t", end="", flush=True)
        lam = sr[:-1].values * np.exp(self.GAMMA * (self.r_t_range[:, None] - 1))

        # Note: if you want to have a Uniform prior you can use the following line instead.
        # I chose the gamma distribution because of our prior knowledge of the likely value
        # of R_t.

        # prior0 = np.full(len(r_t_range), np.log(1/len(r_t_range)))
        prior0 = np.log(sps.gamma(a=3).pdf(self.r_t_range) + 1e-14)

        likelihoods = pd.DataFrame(
            # Short-hand way of concatenating the prior and likelihoods
            data=np.c_[prior0, sps.poisson.logpmf(sr[1:].values, lam)],
            index=self.r_t_range,
            columns=sr.index)

        # Perform a rolling sum of log likelihoods. This is the equivalent
        # of multiplying the original distributions. Exponentiate to move
        # out of log.
        posteriors = likelihoods.rolling(window,
                                         axis=1,
                                         min_periods=min_periods).sum()
        posteriors = np.exp(posteriors)

        # Normalize to 1.0
        posteriors = posteriors.div(posteriors.sum(axis=0), axis=1)
        print("[DONE]")
        return posteriors

    def prepare_cases(self, cases, window=7):
        print('\tWindow size:', window)
        print("\tPreparing cases...\t\t", end="", flush=True)
        new_cases = cases.diff()
        if self.debug:
            print()
            print('NEW_CASES:', new_cases)

        smoothed = new_cases.rolling(window,
                                     win_type='gaussian',
                                     min_periods=1,
                                     center=True).mean(std=2).round()

        zeros = smoothed.index[smoothed.eq(0)]

        if len(zeros) == 0:
            idx_start = 0
        else:
            last_zero = zeros.max()
            idx_start = smoothed.index.get_loc(last_zero) + 1

        smoothed = smoothed.iloc[idx_start:]
        original = new_cases.loc[smoothed.index]

        if self.debug:
            print('ORIGINAL:', original, '-', original.shape)
            print('SMOOTHED:', smoothed, '-', smoothed.shape)

        if smoothed.shape[0] == 0:
            raise Exception('No sufficient data!!!')

        print("[DONE]")
        return original, smoothed

    @staticmethod
    def plot_rt(result, state_name, fig, ax):
        ax.set_title(f"{state_name}")

        # Colors
        ABOVE = [1, 0, 0]
        MIDDLE = [1, 1, 1]
        BELOW = [0, 0, 0]
        cmap = ListedColormap(np.r_[
                                  np.linspace(BELOW, MIDDLE, 25),
                                  np.linspace(MIDDLE, ABOVE, 25)
                              ])
        color_mapped = lambda y: np.clip(y, .5, 1.5) - .5

        index = result['ML'].index.get_level_values('date')
        values = result['ML'].values

        # Plot dots and line
        ax.plot(index, values, c='k', zorder=1, alpha=.25)
        ax.scatter(index,
                   values,
                   s=40,
                   lw=.5,
                   c=cmap(color_mapped(values)),
                   edgecolors='k', zorder=2)

        # Aesthetically, extrapolate credible interval by 1 day either side
        lowfn = interp1d(date2num(index),
                         result['Low'].values,
                         bounds_error=False,
                         fill_value='extrapolate')

        highfn = interp1d(date2num(index),
                          result['High'].values,
                          bounds_error=False,
                          fill_value='extrapolate')

        extended = pd.date_range(start=pd.Timestamp('2020-03-01'),
                                 end=index[-1] + pd.Timedelta(days=1))

        ax.fill_between(extended,
                        lowfn(date2num(extended)),
                        highfn(date2num(extended)),
                        color='k',
                        alpha=.1,
                        lw=0,
                        zorder=3)

        ax.axhline(1.0, c='k', lw=1, label='$R_t=1.0$', alpha=.25)

        # Formatting
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        ax.xaxis.set_minor_locator(mdates.DayLocator())

        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:.1f}"))
        ax.yaxis.tick_right()
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.margins(0)
        ax.grid(which='major', axis='y', c='k', alpha=.1, zorder=-2)
        ax.margins(0)
        ax.set_ylim(0.0, 3.5)
        ax.set_xlim(pd.Timestamp('2020-03-01'), result.index.get_level_values('date')[-1] + pd.Timedelta(days=1))
        fig.set_facecolor('w')

        ax.set_title(f'Real-time $R_t$ for {state_name}')
        ax.set_ylim(.5, 3.5)
        ax.xaxis.set_major_locator(mdates.WeekdayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

    def plot_state_cases_per_day(self, states, state_name, window):
        print('= Plotting cases/day...')
        fig, ax = plt.subplots(figsize=(600 / 72, 400 / 72))
        cases = states.xs(state_name).rename(f"{state_name} cases")
        original, smoothed = self.prepare_cases(cases, window)

        original.plot(title=f"{state_name} New Cases per Day",
                      c='k',
                      linestyle=':',
                      alpha=.5,
                      label='Actual',
                      legend=True,
                      figsize=(600 / 72, 400 / 72))

        ax = smoothed.plot(label='Smoothed',
                           legend=True)
        ax.get_figure().set_facecolor('w')

        # plt.show()
        plt.savefig(os.path.join(self.dump_dir_path, state_name + '_per_day.png'))
        plt.close(fig)
        print('= Done.')

    def plot_state_realtime_rt(self, states, state_name, window):
        print('= Plotting realtime...')
        fig, ax = plt.subplots(figsize=(600 / 72, 400 / 72))
        cases = states.xs(state_name).rename(f"{state_name} cases")

        original, smoothed = self.prepare_cases(cases, window)

        posteriors = self.get_posteriors(smoothed, window)

        hdis = self.highest_density_interval(posteriors)

        most_likely = posteriors.idxmax().rename('ML')

        # Look into why you shift -1
        result = pd.concat([most_likely, hdis], axis=1)
        result.tail()

        self.plot_rt(result, state_name, fig, ax)

        # plt.show()
        plt.savefig(os.path.join(self.dump_dir_path, state_name + '_realtime_rt.png'))
        plt.close(fig)
        print('= Done.')

    def plot_all_states(self, states, filter_region=None, no_lockdown=None, partial_lockdown=None):
        if filter_region is None:
            filter_region = []

        results = {}
        for state_name, cases in states.groupby(level='state'):
            if state_name == '-':
                print(f'Skipping {state_name}')
                continue

            print('=' * 75)
            print(f'Processing {state_name}')

            try:
                new, smoothed = self.prepare_cases(cases)
            except Exception as e:
                print('===', e)
                continue

            print('\tGetting Posteriors')
            posteriors = self.get_posteriors(smoothed)
            print('\tGetting HDIs')
            hdis = self.highest_density_interval(posteriors)
            print('\tGetting most likely values')
            most_likely = posteriors.idxmax().rename('ML')
            result = pd.concat([most_likely, hdis], axis=1)
            results[state_name] = result.droplevel(0)

        print("Done.")
        ncols = 4
        nrows = int(np.ceil(len(results) / ncols))

        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, nrows * 3))

        for i, (state_name, result) in enumerate(results.items()):
            self.plot_rt(result, state_name, fig, axes.flat[i])

        fig.tight_layout()
        fig.set_facecolor('w')
        plt.savefig(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt.png'))
        plt.close(fig)

        overall = None
        for state_name, result in results.items():
            r = result.copy()
            r.index = pd.MultiIndex.from_product([[state_name], result.index])
            if overall is None:
                overall = r
            else:
                overall = pd.concat([overall, r])

        overall.sort_index(inplace=True)
        overall.to_csv(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt.csv'))

        filtered = overall.index.get_level_values(0).isin(filter_region)
        mr = overall.loc[~filtered].groupby(level=0)[['ML', 'High', 'Low']].last()

        mr.sort_values('ML', inplace=True)
        figsize = ((15.9 / 50) * len(mr) + .1 + 1, 11)
        fig, ax = self.plot_standings(mr, figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt_ml.png'))
        plt.close(fig)

        mr.sort_values('High', inplace=True)
        figsize = ((15.9 / 50) * len(mr) + .1 + 1, 11)
        fig, ax = self.plot_standings(mr, figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt_high.png'))
        plt.close(fig)

        show = mr[mr.High.le(1.1)].sort_values('ML')
        figsize = ((15.9 / 50) * len(mr) + .1 + 1, 11)
        fig, ax = self.plot_standings(show, title='Likely Under Control', figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt_luc.png'))
        plt.close(fig)

        show = mr[mr.Low.ge(1.05)].sort_values('Low')
        figsize = ((15.9 / 50) * len(mr) + .1 + 1, 11)
        fig, ax = self.plot_standings(show, figsize=figsize, title='Likely Not Under Control',
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        ax.get_legend().remove()
        plt.savefig(os.path.join(self.dump_info_dir_path, 'all_counties_realtime_rt_lnuc.png'))
        plt.close(fig)

    @staticmethod
    def plot_standings(mr, figsize=None, title='Most Recent $R_t$ by State', no_lockdown=None, partial_lockdown=None):
        if partial_lockdown is None:
            partial_lockdown = []
        if no_lockdown is None:
            no_lockdown = []
        FULL_COLOR = [.7, .7, .7]
        NONE_COLOR = [179 / 255, 35 / 255, 14 / 255]
        PARTIAL_COLOR = [.5, .5, .5]
        ERROR_BAR_COLOR = [.3, .3, .3]
        if not figsize:
            figsize = ((15.9 / 50) * len(mr) + .1, 4)

        fig, ax = plt.subplots(figsize=figsize)

        ax.set_title(title)
        err = mr[['Low', 'High']].sub(mr['ML'], axis=0).abs()
        bars = ax.bar(mr.index,
                      mr['ML'],
                      width=.825,
                      color=FULL_COLOR,
                      ecolor=ERROR_BAR_COLOR,
                      capsize=2,
                      error_kw={'alpha': .5, 'lw': 1},
                      yerr=err.values.T)

        for bar, state_name in zip(bars, mr.index):
            if state_name in no_lockdown:
                bar.set_color(NONE_COLOR)
            if state_name in partial_lockdown:
                bar.set_color(PARTIAL_COLOR)

        labels = mr.index.to_series().replace({'District of Columbia': 'DC'})
        ax.set_xticklabels(labels, rotation=90, fontsize=11)
        ax.margins(0)
        ax.set_ylim(0, 2.)
        ax.axhline(1.0, linestyle=':', color='k', lw=1)

        leg = ax.legend(handles=[
            Patch(label='Full', color=FULL_COLOR),
            Patch(label='Partial', color=PARTIAL_COLOR),
            Patch(label='None', color=NONE_COLOR)
        ],
            title='Lockdown',
            ncol=3,
            loc='upper left',
            columnspacing=.75,
            handletextpad=.5,
            handlelength=1)

        leg._legend_box.align = "left"
        fig.set_facecolor('w')
        return fig, ax

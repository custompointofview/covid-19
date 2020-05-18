#!/usr/bin/env python
import json
import os
import sys

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

from retrying import retry
# from IPython.display import clear_output


class PlotUtils:
    # We create an array for every possible value of Rt
    R_T_MAX = 12
    r_t_range = np.linspace(0, R_T_MAX, R_T_MAX * 100 + 1)

    # Gamma is 1/serial interval
    # https://wwwnc.cdc.gov/eid/article/26/6/20-0357_article
    # https://www.nejm.org/doi/full/10.1056/NEJMoa2001316
    GAMMA = 1 / 7

    def __init__(self, path=None, start_date='2020-03-01', cap_limit=2.):
        self.dump_dir_path = path
        self.dump_info_dir_path = os.path.join(path, 'results')
        self.start_date = start_date
        self.cap_limit = cap_limit

        self.debug = False

    def set_path(self, path):
        self.dump_dir_path = path
        self.dump_info_dir_path = os.path.join(path, 'results')

    def create_dump_dir(self):
        if not os.path.exists(self.dump_dir_path):
            os.makedirs(self.dump_dir_path)
        if not os.path.exists(self.dump_info_dir_path):
            os.makedirs(self.dump_info_dir_path)

    def highest_density_interval(self, pmf, p=.9):
        # If we pass a DataFrame, just call this recursively on the columns
        if isinstance(pmf, pd.DataFrame):
            return pd.DataFrame([self.highest_density_interval(pmf[col], p=p) for col in pmf],
                                index=pmf.columns)

        cumsum = np.cumsum(pmf.values)
        if self.debug:
            print('pmf.values', pmf.values)
            print('cumsum:', cumsum)
        try:
            if all(np.isnan(cumsum)):
                return pd.Series([0, 1], index=[f'Low_{p * 100:.0f}', f'High_{p * 100:.0f}'])
        except TypeError:
            return pd.Series([0, 1], index=[f'Low_{p * 100:.0f}', f'High_{p * 100:.0f}'])

        # N x N matrix of total probability mass for each low, high
        total_p = cumsum - cumsum[:, None]
        if self.debug:
            print('total_p', total_p)

        # Return all indices with total_p > p
        lows, highs = (total_p > p).nonzero()
        if self.debug:
            print('lows', lows)
            print('highs', highs)
        if len(lows) == 0 and len(highs) == 0:
            lows, highs = total_p.nonzero()
            print('nonzero', total_p.nonzero())
            print('lows', lows)
            print('highs', highs)

            if len(lows) == 0 and len(highs) == 0:
                return pd.Series([0, 1], index=[f'Low_{p * 100:.0f}', f'High_{p * 100:.0f}'])

            low = pmf.index[lows[lows.min()]]
            high = pmf.index[highs[highs.min()]]
            print('low', low)
            print('high', high)

            return pd.Series([0, 1], index=[f'Low_{p * 100:.0f}', f'High_{p * 100:.0f}'])

        # Find the smallest range (highest density)
        best = (highs - lows).argmin()
        if self.debug:
            print('best', best)

        low = pmf.index[lows[best]]
        high = pmf.index[highs[best]]
        if self.debug:
            print('low', low)
            print('high', high)

        return pd.Series([low, high], index=[f'Low_{p * 100:.0f}', f'High_{p * 100:.0f}'])

    def get_posteriors(self, sr, sigma=0.15, window=7, min_periods=1):
        # (1) Calculate Lambda
        lam = sr[:-1].values * np.exp(self.GAMMA * (self.r_t_range[:, None] - 1))
        # (2) Calculate each day's likelihood
        likelihoods = pd.DataFrame(
            data=sps.poisson.pmf(sr[1:].values, lam),
            index=self.r_t_range,
            columns=sr.index[1:])
        # (3) Create the Gaussian Matrix
        process_matrix = sps.norm(loc=self.r_t_range,
                                  scale=sigma
                                  ).pdf(self.r_t_range[:, None])
        # (3a) Normalize all rows to sum to 1
        process_matrix /= process_matrix.sum(axis=0)
        # (4) Calculate the initial prior
        # prior0 = sps.gamma(a=4).pdf(self.r_t_range)
        prior0 = np.ones_like(self.r_t_range) / len(self.r_t_range)
        prior0 /= prior0.sum()

        # Create a DataFrame that will hold our posteriors for each day
        # Insert our prior as the first posterior.
        posteriors = pd.DataFrame(
            index=self.r_t_range,
            columns=sr.index,
            data={sr.index[0]: prior0}
        )

        # We said we'd keep track of the sum of the log of the probability
        # of the data for maximum likelihood calculation.
        log_likelihood = 0.0

        # (5) Iteratively apply Bayes' rule
        for previous_day, current_day in zip(sr.index[:-1], sr.index[1:]):
            # (5a) Calculate the new prior
            current_prior = process_matrix @ posteriors[previous_day]
            # (5b) Calculate the numerator of Bayes' Rule: P(k|R_t)P(R_t)
            numerator = likelihoods[current_day] * current_prior
            # (5c) Calculate the denominator of Bayes' Rule P(k)
            denominator = np.sum(numerator)
            if denominator == 0:
                posteriors[current_day] = numerator
                continue
            # Execute full Bayes' Rule
            posteriors[current_day] = numerator / denominator
            # Add to the running sum of log likelihoods
            try:
                log_likelihood += np.log(denominator)
            except Exception as e:
                log_likelihood += 0

        return posteriors, log_likelihood

    def prepare_cases(self, cases, window=7):
        # print('\tWindow size:', window)
        print("\tPreparing cases...\t\t", end="", flush=True)
        new_cases = cases.diff()
        if self.debug:
            print('new_cases:', new_cases.to_string())
        smoothed = new_cases.rolling(window,
                                     win_type='gaussian',
                                     min_periods=1,
                                     center=True).mean(std=2).round()
        if self.debug:
            print('smoothed:', smoothed.to_string())

        zeros = smoothed.index[smoothed.eq(0)]
        if self.debug:
            print('zeros:', zeros)

        if len(zeros) == 0:
            idx_start = 0
        else:
            last_zero = zeros.max()
            idx_start = smoothed.index.get_loc(last_zero) + 1

            # fix for when there is no new case for last couple of days
            if smoothed.iloc[idx_start:].shape[0] < window:
                idx_start = 0
                for x in smoothed:
                    if x == 0:
                        idx_start += 1
                    else:
                        break
                idx_start += 1

        smoothed = smoothed.iloc[idx_start:]
        original = new_cases.loc[smoothed.index]
        if self.debug:
            print('ORIGINAL:', original, '-', original.shape)
            print('SMOOTHED:', smoothed, '-', smoothed.shape)

        if smoothed.shape[0] == 0:
            raise Exception('No sufficient data!!!')

        print("[DONE]")
        return original, smoothed

    def choose_sigma(self, states, selected_state=None):
        sigmas = np.linspace(1 / 20, 1, 20)
        results = {}
        for state_name, cases in states.groupby(level='state'):
            if selected_state is not None and state_name != selected_state:
                continue
            print("= Processing sigma for " + state_name + "...")
            try:
                new, smoothed = self.prepare_cases(cases)
            except Exception as e:
                print('===', e)
                continue

            # Holds all posteriors with every given value of sigma
            # Holds the log likelihood across all k for each value of sigma
            result = {'posteriors': [], 'log_likelihoods': []}

            print("\tPreparing posteriors...\t\t", end="", flush=True)
            for sigma in sigmas:
                posteriors, log_likelihood = self.get_posteriors(smoothed, sigma=sigma)
                result['posteriors'].append(posteriors)
                result['log_likelihoods'].append(log_likelihood)
            print('[DONE]')

            # Store all results keyed off of state name
            results[state_name] = result

        # Each index of this array holds the total of the log likelihoods for
        # the corresponding index of the sigmas array.
        total_log_likelihoods = np.zeros_like(sigmas)

        # Loop through each state's results and add the log likelihoods to the running total.
        for state_name, result in results.items():
            total_log_likelihoods += result['log_likelihoods']

        # Select the index with the largest log likelihood total
        max_likelihood_index = total_log_likelihoods.argmax()

        # Select the value that has the highest log likelihood
        sigma = sigmas[max_likelihood_index]
        return results, sigma, max_likelihood_index

    def get_final_results(self, results, max_likelihood_index):
        final_results = None

        for state_name, result in results.items():
            print("= Processing results for " + state_name + "...\t", end="", flush=True)
            posteriors = result['posteriors'][max_likelihood_index]
            if self.debug:
                print('posteriors', posteriors)
            hdis_90 = self.highest_density_interval(posteriors, p=.9)
            hdis_50 = self.highest_density_interval(posteriors, p=.5)
            if self.debug:
                print('hdis_90', hdis_90)
                print('hdis_50', hdis_50)
            most_likely = posteriors.idxmax().rename('ML')
            result = pd.concat([most_likely, hdis_90, hdis_50], axis=1)
            if final_results is None:
                final_results = result
            else:
                final_results = pd.concat([final_results, result])
            print("[DONE]")

        return final_results

    def plot_rt(self, result, state_name, fig, ax):
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
                         result['Low_90'].values,
                         bounds_error=False,
                         fill_value='extrapolate')

        highfn = interp1d(date2num(index),
                          result['High_90'].values,
                          bounds_error=False,
                          fill_value='extrapolate')

        extended = pd.date_range(start=pd.Timestamp(self.start_date),
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
        ax.set_xlim(pd.Timestamp(self.start_date), result.index.get_level_values('date')[-1] + pd.Timedelta(days=1))
        fig.set_facecolor('w')

        ax.set_title(f'Real-time $R_t$ for {state_name}')
        ax.xaxis.set_major_locator(mdates.WeekdayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

    def plot_state_cases_per_day(self, states, state_name, window):
        print('= Plotting cases/day...')
        figsize = (800 / 72, 600 / 72)
        fig, ax = plt.subplots(figsize=figsize)
        cases = states.xs(state_name).rename(f"{state_name} cases")
        original, smoothed = self.prepare_cases(cases, window)

        original.plot(title=f"{state_name} New Cases per Day",
                      c='k',
                      linestyle=':',
                      alpha=.5,
                      label='Actual',
                      legend=True,
                      figsize=figsize)

        ax = smoothed.plot(label='Smoothed',
                           legend=True)
        ax.get_figure().set_facecolor('w')

        plt.savefig(os.path.join(self.dump_dir_path, state_name + '_per_day.png'))
        plt.close(fig)

    def plot_state_realtime_rt(self, states, state_name, window):
        fig, ax = plt.subplots(figsize=(600 / 72, 400 / 72))

        results, sigmas, max_likelihood_index = self.choose_sigma(states, state_name)
        if results == {}:
            return

        final_results = self.get_final_results(results=results, max_likelihood_index=max_likelihood_index)

        print('= Plotting realtime...\t\t\t', end="", flush=True)
        self.plot_rt(final_results, state_name, fig, ax)
        plt.savefig(os.path.join(self.dump_dir_path, state_name + '_realtime_rt.png'))
        plt.close(fig)
        print('[DONE]')

    def plot_all_states(self, states, dump_file_name=None, filter_region=None,
                        no_lockdown=None, partial_lockdown=None, ncols=4):
        if filter_region is None:
            filter_region = []

        results, sigmas, max_likelihood_index = self.choose_sigma(states)
        if results == {}:
            return
        final_results = self.get_final_results(results=results, max_likelihood_index=max_likelihood_index)

        print('= Saving data to csv...\t\t\t\t', end="", flush=True)
        dump_file_name = dump_file_name if dump_file_name is not None else 'all_counties_realtime_rt'
        final_results.to_csv(os.path.join(self.dump_info_dir_path, dump_file_name+'.csv'))
        print('[DONE]')

        print('= Sub-plotting Rt...\t\t\t\t', end="", flush=True)
        ncols = ncols
        nrows = int(np.ceil(len(results) / ncols))
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, nrows * 3))
        for i, (state_name, result) in enumerate(final_results.groupby('state')):
            self.plot_rt(result, state_name, fig, axes.flat[i])

        fig.tight_layout()
        fig.set_facecolor('w')
        plt.savefig(os.path.join(self.dump_info_dir_path, dump_file_name+'.png'))
        plt.close(fig)
        print('[DONE]')

        #######################
        # Plot standings
        #######################
        filtered = final_results.index.get_level_values(0).isin(filter_region)
        mr = final_results.loc[~filtered].groupby(level=0)[['ML', 'High_90', 'Low_90']].last()

        print('= Plotting Rt standings (ML)...\t\t\t', end="", flush=True)
        mr.sort_values('ML', inplace=True)
        figsize = ((15.9 / 50) * len(mr) + .1 + 4, 11)
        fig, ax = self.plot_standings(mr, title='Most Recent $R_t$ by State (sort by ML)', figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, dump_file_name+'_ml.png'))
        plt.close(fig)
        print('[DONE]')

        print('= Plotting Rt standings (High_90)...\t\t', end="", flush=True)
        mr.sort_values('High_90', inplace=True)
        fig, ax = self.plot_standings(mr, title='Most Recent $R_t$ by State (sort by High_90)', figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, dump_file_name+'_high.png'))
        plt.close(fig)
        print('[DONE]')

        print('= Plotting Rt standings (LUC High_90)...\t', end="", flush=True)
        show = mr[mr.High_90.le(1.0)].sort_values('ML')
        fig, ax = self.plot_standings(show, title='Likely Under Control (High_90)', figsize=figsize,
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, dump_file_name+'_luc.png'))
        plt.close(fig)
        print('[DONE]')

        print('= Plotting Rt standings (LNUC Low_90)...\t', end="", flush=True)
        show = mr[mr.Low_90.ge(1.0)].sort_values('Low_90')
        fig, ax = self.plot_standings(show, figsize=figsize, title='Likely NOT Under Control (Low_90)',
                                      no_lockdown=no_lockdown, partial_lockdown=partial_lockdown)
        plt.savefig(os.path.join(self.dump_info_dir_path, dump_file_name+'_lnuc.png'))
        plt.close(fig)
        print('[DONE]')

    def plot_standings(self, mr, figsize=None, title='Most Recent $R_t$ by State',
                       no_lockdown=None, partial_lockdown=None):
        if partial_lockdown is None:
            partial_lockdown = []
        if no_lockdown is None:
            no_lockdown = []
        FULL_COLOR = [.7, .7, .7]
        NONE_COLOR = [179 / 255, 35 / 255, 14 / 255]
        PARTIAL_COLOR = [.5, .5, .5]
        ERROR_BAR_COLOR = [.3, .3, .3]

        # Processing...
        if not figsize:
            figsize = ((15.9 / 50) * len(mr) + .1, 4)

        fig, ax = plt.subplots(figsize=figsize)

        ax.set_title(title)
        err = mr[['Low_90', 'High_90']].sub(mr['ML'], axis=0).abs()
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
        ax.set_ylim(0, self.cap_limit)
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

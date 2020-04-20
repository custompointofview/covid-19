#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd

import plotter
import sweeper


def plot_single_area(area, sw):
    print('-' * 58)
    print('-' * 20 + ' ' + area + ' ' + '-' * 20)
    print('= Getting data...')
    pu = plotter.PlotUtils(sw.png_dir_path)
    states, daily_cases_path = sw.get_daily_cases()
    if states is None:
        states = pd.read_csv(daily_cases_path,
                             usecols=[0, 1, 2],
                             index_col=['state', 'date'],
                             parse_dates=['date'],
                             squeeze=True).sort_index()
    state_name = area
    window = 7

    pu.plot_state_cases_per_day(states, state_name, window)
    pu.plot_state_realtime_rt(states, state_name, window)

    print('-' * 26 + ' DONE ' + '-' * 26)


def plot_all_in_one(area, sw, start_date='2020-03-01', cap_limit=2.):
    print('-' * 58)
    print('-' * 20 + ' ' + area + ' ' + '-' * 20)
    print('= Getting data...')
    pu = plotter.PlotUtils(sw.png_dir_path, start_date=start_date, cap_limit=cap_limit)
    states, daily_cases_path = sw.get_cases_by_county()
    if states is None:
        states = pd.read_csv(daily_cases_path,
                             usecols=[0, 1, 2],
                             index_col=['state', 'date'],
                             parse_dates=['date'],
                             squeeze=True).sort_index()
    pu.plot_all_states(states)
    print('-' * 26 + ' DONE ' + '-' * 26)


def plot_test_eu_incoherent_data():
    sw_eu = sweeper.SweeperEU()
    sw_eu.create_output_dirs()
    pu = plotter.PlotUtils(sw_eu.png_dir_path)
    pu.create_dump_dir()
    states, daily_cases_path = sw_eu.get_daily_cases_cssegi()

    state_name = 'France'
    print(states[state_name].to_string())

    window = 7
    pu.debug = True
    pu.plot_state_cases_per_day(states, state_name, window)
    pu.plot_state_realtime_rt(states, state_name, window)


def plot_test_ro_incoherent_data():
    sw_ro = sweeper.SweeperRO()
    sw_ro.create_output_dirs()
    pu = plotter.PlotUtils(sw_ro.png_dir_path, start_date='2020-04-01', cap_limit=4.)
    pu.create_dump_dir()
    daily_cases_path = sw_ro.get_cases_by_county()
    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()

    state_name = 'BR'
    # state_name = 'IS'
    print(states[state_name].to_string())

    window = 7
    pu.debug = True
    pu.plot_state_cases_per_day(states, state_name, window)
    pu.plot_state_realtime_rt(states, state_name, window)


if __name__ == "__main__":
    # Plotting zone
    plot_single_area(area='Romania', sw=sweeper.SweeperRO())
    plot_all_in_one(area='Romania Counties', sw=sweeper.SweeperRO(), start_date='2020-04-01', cap_limit=4.)
    # plot_single_area(area='Europe', sw=sweeper.SweeperEU())
    plot_all_in_one(area='Europe', sw=sweeper.SweeperEU())

    # Testing zone
    # plot_test_eu_incoherent_data()
    # plot_test_ro_incoherent_data()

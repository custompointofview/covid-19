#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd

import plotter
import sweeper


def plot_romania():
    print('*' * 75)
    print('*' * 10 + ' Plotting ROMANIA')
    print('*' * 75)

    sw_ro = sweeper.SweeperRO()
    pu = plotter.PlotUtils(sw_ro.png_dir_path)
    pu.create_dump_dir()

    print('= Getting data...')
    daily_cases_path = sw_ro.get_daily_cases()

    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()
    state_name = 'Romania'
    window = round(states.shape[0] / 2)

    pu.plot_state_cases_per_day(states, state_name, window)
    pu.plot_state_realtime_rt(states, state_name, window)
    print('= [DONE]')


def plot_romania_counties():
    print('*' * 75)
    print('*' * 10 + ' Plotting ROMANIA counties (one by one)')
    print('*' * 75)

    sw_ro = sweeper.SweeperRO()
    pu = plotter.PlotUtils(sw_ro.png_dir_path)
    pu.create_dump_dir()

    daily_cases_path = sw_ro.get_cases_by_county()

    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()
    insufficient_data = []
    for state in sw_ro.ROFilter:
        window = round(states[state].shape[0] / 2)
        print('-' * 50)
        print('-----   ' + state + '   -----')
        try:
            pu.plot_state_cases_per_day(states, state, window)
            pu.plot_state_realtime_rt(states, state, window)
        except Exception as e:
            print('===', e)
            insufficient_data.append(state)

    print('-' * 50)
    print('-----   States with Insufficient Data   -----')
    print(insufficient_data)
    print('-' * 50)


def plot_romania_counties_once():
    print('*' * 75)
    print('*' * 10 + ' Plotting ROMANIA counties (all in one)')
    print('*' * 75)
    sw_ro = sweeper.SweeperRO()
    pu = plotter.PlotUtils(sw_ro.png_dir_path)
    pu.create_dump_dir()
    daily_cases_path = sw_ro.get_cases_by_county()

    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()
    pu.plot_all_states(states)


def plot_europe():
    print('*' * 75)
    print('*' * 10 + ' Plotting EUROPE (one by one)')
    print('*' * 75)
    sw_eu = sweeper.SweeperEU()
    sw_eu.create_output_dirs()
    pu = plotter.PlotUtils(sw_eu.png_dir_path)
    pu.create_dump_dir()

    # daily_cases_path = sw_eu.get_daily_cases_ninja()
    daily_cases_path = sw_eu.get_daily_cases_cssegi()
    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()

    insufficient_data = []
    for state in sw_eu.EUFilter:
        window = round(states[state].shape[0] / 2)
        print('-' * 50)
        print('-----   ' + state + '   -----')
        try:
            pu.plot_state_cases_per_day(states, state, window)
            pu.plot_state_realtime_rt(states, state, window)
        except Exception as e:
            print('===', e)
            insufficient_data.append(state)

    print('-' * 50)
    print('-----   States with Insufficient Data   -----')
    print(insufficient_data)
    print('-' * 50)


def plot_europe_counties_once():
    print('*' * 75)
    print('*' * 10 + ' Plotting EUROPE (all in one)')
    print('*' * 75)
    sw_eu = sweeper.SweeperEU()
    sw_eu.create_output_dirs()
    pu = plotter.PlotUtils(sw_eu.png_dir_path)
    pu.create_dump_dir()

    # daily_cases_path = sw_eu.get_daily_cases_ninja()
    daily_cases_path = sw_eu.get_daily_cases_cssegi()
    states = pd.read_csv(daily_cases_path,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()
    #########
    # AS OF 16.04.2020
    FILTERED_REGIONS = []
    LOCKDOWN_NO = [
        'Sweden',
        'Belarus',
    ]
    LOCKDOWN_PARTIAL = [
        'Russia',
    ]
    #########
    pu.plot_all_states(states, filter_region=FILTERED_REGIONS,
                       no_lockdown=LOCKDOWN_NO, partial_lockdown=LOCKDOWN_PARTIAL)


if __name__ == "__main__":
    plot_romania()
    # plot_romania_counties()
    plot_romania_counties_once()
    # plot_europe()
    plot_europe_counties_once()

    print('*' * 74)
    print('*' * 32 + '   DONE   ' + '*' * 32)
    print('*' * 74)

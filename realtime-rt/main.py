#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from io import StringIO
from PIL import Image, ImageDraw, ImageFont

import pandas as pd

import plotter
import sweeper

from datetime import date


def plot_single_area(area, sw, source=None):
    print('-' * 58)
    print('-' * 20 + ' ' + area + ' ' + '-' * 20)
    print('= Getting data...')
    pu = plotter.PlotUtils(sw.png_dir_path)
    states, daily_cases_path = sw.get_daily_cases(source=source)
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


def plot_single_area_all_sources(area, sw, cap_limit=2.):
    print('-' * 58)
    print('-' * 20 + ' ' + area + ' ' + '-' * 20)
    print('= Getting data...')
    pu = plotter.PlotUtils(sw.png_dir_path, cap_limit=cap_limit)

    output = StringIO()
    header_set = False
    for name, source in sw.sources:
        print('= Gathering for:', name)
        states, daily_cases_path = sw.get_daily_cases(source=source)
        if states is None:
            with open(daily_cases_path, 'r') as f:
                contents = f.readlines()
                for index, line in enumerate(contents):
                    contents[index] = line.replace(area, area + '_' + name)

                if header_set:
                    contents = contents[1:]
                output.writelines(contents)
                header_set = True

    output.seek(0)
    states = pd.read_csv(output,
                         usecols=[0, 1, 2],
                         index_col=['state', 'date'],
                         parse_dates=['date'],
                         squeeze=True).sort_index()

    pu.plot_all_states(states, dump_file_name='all_sources_realtime_rt', ncols=3)
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
    states, daily_cases_path = sw_ro.get_cases_by_county()
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


def plot_update_date():
    img = Image.new('RGB', (250, 50), color=(255, 255, 255))

    fnt = ImageFont.load_default()
    d = ImageDraw.Draw(img)

    today = date.today()
    text = "Last Updated on: " + today.strftime("%B %d, %Y")

    d.text(xy=(10, 20), text=text, font=fnt, fill=(0, 0, 0))
    img.save('last_update_date.png')


if __name__ == "__main__":
    # Plotting zone

    # ROMANIA
    sw = sweeper.SweeperRO()

    # plot_single_area(area='Romania', sw=sw, source=sw.GETDailyCasesCODE)
    plot_all_in_one(area='Romania Counties', sw=sw, start_date='2020-04-01', cap_limit=4.)
    plot_single_area_all_sources(area='Romania', sw=sw, cap_limit=4.)

    # EUROPE
    # plot_single_area(area='Europe', sw=sweeper.SweeperEU())
    plot_all_in_one(area='Europe', sw=sweeper.SweeperEU())

    # DATE
    plot_update_date()

    # Testing zone
    # plot_test_eu_incoherent_data()
    # plot_test_ro_incoherent_data()

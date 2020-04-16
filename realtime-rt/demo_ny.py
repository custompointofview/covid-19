#!/usr/bin/env python
import pandas as pd
from matplotlib import pyplot as plt

import plotter

pu = plotter.PlotUtils('')

url = 'https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-states.csv'
states = pd.read_csv(url,
                     usecols=[0, 1, 3],
                     index_col=['state', 'date'],
                     parse_dates=['date'],
                     squeeze=True).sort_index()
state_name = 'New York'

cases = states.xs(state_name).rename(f"{state_name} cases")

original, smoothed = pu.prepare_cases(cases)

original.plot(title=f"{state_name} New Cases per Day",
              c='k',
              linestyle=':',
              alpha=.5,
              label='Actual',
              legend=True,
              figsize=(600/72, 400/72))

ax = smoothed.plot(label='Smoothed',
                   legend=True)
ax.get_figure().set_facecolor('w')

plt.show()

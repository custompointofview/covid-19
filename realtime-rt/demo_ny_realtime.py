#!/usr/bin/env python
import pandas as pd
import plotter

from matplotlib import pyplot as plt

pu = plotter.PlotUtils('')
fig, ax = plt.subplots(figsize=(600 / 72, 400 / 72))

url = 'https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-states.csv'
states = pd.read_csv(url,
                     usecols=[0, 1, 3],
                     index_col=['state', 'date'],
                     parse_dates=['date'],
                     squeeze=True).sort_index()
state_name = 'New York'

cases = states.xs(state_name).rename(f"{state_name} cases")

original, smoothed = pu.prepare_cases(cases)

posteriors = pu.get_posteriors(smoothed)

hdis = pu.highest_density_interval(posteriors)

most_likely = posteriors.idxmax().rename('ML')

# Look into why you shift -1
result = pd.concat([most_likely, hdis], axis=1)
result.tail()

pu.plot_rt(result, state_name, fig, ax)

plt.show()

#!/usr/bin/env python
import datetime
import os
import csv, json
import re

import pandas as pd
import requests as req


class SweeperEU:
    # JSON format historical data for world countries (frequently updated)
    GETDailyCasesNINJA = "https://corona.lmao.ninja/v2/historical"
    GETDailyCasesCSSEGI = "https://github.com/CSSEGISandData/COVID-19/raw/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"

    EUFilter = ["Russia", "Germany", "UK", "France", "Italy", "Spain", "Ukraine", "Poland", "Romania",
                "Netherlands", "Belgium", "Czechia", "Greece", "Portugal", "Sweden", "Hungary",
                "Belarus", "Austria", "Serbia", "Switzerland", "Bulgaria", "Denmark", "Finland", "Slovakia", "Norway",
                "Ireland", "Croatia", "Moldova", "Bosnia", "Albania", "Lithuania", "Macedonia",
                "Slovenia", "Latvia", "Estonia", "Montenegro", "Luxembourg", "Malta", "Iceland", "Andorra", "Monaco",
                "Liechtenstein", "San Marino", "Holy See"]

    def __init__(self):
        self.info_dir_path = "collections"
        self.png_dir_path = "plots/europe"
        self.create_output_dirs()

    def create_output_dirs(self):
        if not os.path.exists(self.info_dir_path):
            os.makedirs(self.info_dir_path)
        if not os.path.exists(self.png_dir_path):
            os.makedirs(self.png_dir_path)

    def get_daily_cases_cssegi(self):
        resp = pd.read_csv(self.GETDailyCasesCSSEGI)
        resp = resp.drop(['Lat', 'Long'], axis=1)
        ncountries = resp['Country/Region'].unique().tolist()
        dfa = pd.DataFrame()
        for i, country in enumerate(ncountries):
            if country not in self.EUFilter:
                continue
            dfc = resp[resp['Country/Region'] == country].copy()
            if len(dfc) > 1:
                dfc = dfc.drop(['Province/State'], axis=1).groupby('Country/Region').sum().reset_index()
            else:
                dfc = dfc.drop(['Province/State'], axis=1)
            dfc2 = dfc.melt(id_vars=["Country/Region"],
                            var_name="Date",
                            value_name="cases")
            dfc2 = dfc2.rename({'Country/Region': 'state', 'Date': 'date'}, axis=1)
            dfa = dfa.append(dfc2)
        dfa['date'] = pd.to_datetime(dfa['date'])
        states = dfa.set_index(['state', 'date']).squeeze()
        csv_file_path = os.path.join(self.info_dir_path, "eu_daily_cases_cssegi.csv")
        states.to_csv(csv_file_path)
        return csv_file_path

    def get_daily_cases_ninja(self):
        resp = req.get(self.GETDailyCasesNINJA)
        data = json.loads(resp.text)

        csv_file_path = os.path.join(self.info_dir_path, "eu_daily_cases_ninja.csv")
        data_file = open(csv_file_path, "w")
        f = csv.writer(data_file)
        f.writerow(["date", "state", "cases"])
        for elem in data:
            state = elem['country']
            if state not in self.EUFilter:
                continue
            if elem['province'] is not None:
                continue
            for date, cases in elem['timeline']['cases'].items():
                date = re.sub('/20$', '/2020', date)
                now_date = datetime.datetime.strptime(date, '%m/%d/%Y')
                date = now_date.strftime('%Y-%m-%d')
                f.writerow([date, state, cases])

        return csv_file_path


class SweeperRO:
    # JSON format with important data by day in Romania
    GETDailyCases = "https://covid19.geo-spatial.org/api/dashboard/getDailyCases"
    # JSON downloaded from https://datelazi.ro/ - historical data about cases per county
    GETHistoryInfoJSON = "ro_history_15-04-2020.json"
    # JSON format with important data by day in Romania
    GETHistoryInfo = "https://api1.datelazi.ro/api/v2/data"

    ROFilter = ["AB", "AG", "AR", "B", "BC", "BH", "BN", "BR", "BT", "BV", "BZ", "CJ", "CL", "CS", "CT", "CV", "DB",
                "DJ", "GJ", "GL", "GR", "HD", "HR", "IF", "IL", "IS", "MH", "MM", "MS", "NT", "OT", "PH", "SB", "SJ",
                "SM", "SV", "TL", "TM", "TR", "VL", "VN", "VS"]

    def __init__(self):
        self.info_dir_path = "collections"
        self.png_dir_path = "plots/romania"
        self.create_output_dirs()

    def create_output_dirs(self):
        if not os.path.exists(self.info_dir_path):
            os.makedirs(self.info_dir_path)
        if not os.path.exists(self.png_dir_path):
            os.makedirs(self.png_dir_path)

    def get_daily_cases(self):
        # relevant information only for country
        resp = req.get(self.GETDailyCases)
        data = json.loads(resp.text)
        data = data['data']['data']
        # print(json.dumps(data, indent=4, sort_keys=True))

        state = 'Romania'
        csv_file_path = os.path.join(self.info_dir_path, "ro_daily_cases.csv")
        data_file = open(csv_file_path, "w")
        f = csv.writer(data_file)
        f.writerow(["date", "state", "cases"])
        for elem in data:
            f.writerow([elem['Data'], state, elem['Cazuri active']])
        return csv_file_path

    def get_cases_by_county(self):
        # json_file_path = os.path.join(self.info_dir_path, self.GETHistoryInfoJSON)
        # with open(json_file_path, "r", encoding='ISO-8859-1') as data_file:
        #     data = json.load(data_file)
        resp = req.get(self.GETHistoryInfo)
        data = json.loads(resp.text)
        data = data['historicalData']
        data = {k: v for k, v in data.items() if v["countyInfectionsNumbers"] != {}}

        for k, v in data.items():
            if "20202" in k:
                k_r = k.replace("20202", "2020")
                data[k_r] = v
                del data[k]

        csv_file_path = os.path.join(self.info_dir_path, "ro_daily_cases_county.csv")
        data_file = open(csv_file_path, "w")
        f = csv.writer(data_file)
        f.writerow(["date", "state", "cases"])

        state_date_max = {}
        for k in sorted(data.keys()):
            v = data[k]
            for state, cases in v["countyInfectionsNumbers"].items():
                if state not in state_date_max:
                    state_date_max[state] = (k, cases)
                max_date = state_date_max[state][0]
                max_cases = state_date_max[state][1]

                now_date = datetime.datetime.strptime(k, '%Y-%m-%d')
                old_date = datetime.datetime.strptime(max_date, '%Y-%m-%d')
                if now_date > old_date:
                    if cases < max_cases:
                        cases = max_cases
                state_date_max[state] = (k, cases)

                f.writerow([k, state, cases])

        return csv_file_path

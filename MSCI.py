import re
import requests
from datetime import date, timedelta
import pandas as pd


class MSCI():
    '''
    Download end-of-day pricing data for MSCI Indexes.
    '''

    def __init__(self, update_codes=False):
        self.api_url = 'https://app2.msci.com/products'
        if update_codes:
            self.update_index_codes()
        else:
            self.indexes = pd.read_pickle('indexes.pkl')

    def update_index_codes(self):
        '''
        Update index codes, which provide a mapping from index names to
        the needed lookup codes to query server. Creates a dict that is
        saved as a pd.DataFrame in index_codes.json.pkl.
        '''
        print('Updating index codes...', end=' ')

        # First get list of market codes
        url = (self.api_url +
               '/index-data-search/resources/index-data-search/' +
               'js/data/index-panel-data.json')
        resp = requests.get(url)
        markets = resp.json()['market']
        markets = pd.DataFrame(markets).set_index('id').squeeze()

        # Now get list of indexes in each scope & market
        index_params = {
            'index_size': 12,
            'index_style': 'None',
            'index_suite': 'C'
        }
        
        idxs = []
        for index_scope in ['Region', 'Country']:
            for index_market in markets.index:
                index_params['index_scope'] = index_scope
                index_params['index_market'] = index_market

                url = self.api_url + '/service/index/indexmaster/searchIndexes'
                resp = requests.get(url, params=index_params)

                idx = pd.DataFrame(resp.json()['indexes'])
                idx.insert(0, 'index_scope', index_scope)
                idx.insert(0, 'index_market', markets[index_market])
                idxs.append(idx)
        idxs = pd.concat(idxs).dropna()
        idxs['msci_index_code'] = pd.to_numeric(idxs['msci_index_code'],
                                                downcast='integer')
        idxs.to_pickle('indexes.pkl')
        self.indexes = idxs
        print('Done.')

    def search(self, q):
        rslt = self.indexes[self.indexes.index_name.str.contains(
            q, flags=re.IGNORECASE)]
        cols = ['index_name', 'msci_index_code', 'index_scope', 'index_market']
        if len(rslt) > 0:
            print(rslt[cols].to_string(index=False))
        else:
            print('No match found.')

    def get_index(self, market, start_date=None, end_date=None, freq='d'):
        '''Download closing price data for index.

        Parameters
        ----------
        market : str
            Name of market, as defined by MSCI. Names are typically in
            all-caps. Available markets are visible in the .indexes property.

        start_date: str or datetime.date
            Data start date. If a string, format is YYYYMMDD. If none provided,
            defaults to today.

        end_date: str
            Data end date. If a string, format is YYYYMMDD. If none provided,
            defaults to five years ago.

        freq: str
            Frequency. (d)aily, (m)onthly, or (a)nnual. Default is "d".
        '''

        index_code = (self.indexes[self.indexes['index_name'] == market]
                      .iloc[0]
                      .at['msci_index_code'])

        freqs = {'d': 'DAILY', 'm': 'END_OF_MONTH', 'a': 'ANNUAL'}

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = (date.today() - timedelta(5*365.25))

        if isinstance(start_date, date):
            start_date = start_date.strftime('%Y%m%d')
        if isinstance(end_date, date):
            end_date = end_date.strftime('%Y%m%d')

        params = {
            'currency_symbol': 'USD',
            'index_variant': 'STRD',
            'start_date': start_date,
            'end_date': end_date,
            'data_frequency': freqs[freq],
            'index_codes': index_code
        }

        resp = requests.get(self.api_url +
                            '/service/index/indexmaster/getLevelDataForGraph',
                            params=params)
        if resp.ok:
            prices = pd.DataFrame(resp.json()['indexes']['INDEX_LEVELS'])
            prices.index = pd.to_datetime(prices['calc_date'].astype(str))
            del prices['calc_date']
            prices = prices.squeeze()
            prices.index.name = ''
            prices.name = market
            return prices
        else:
            print('Problem downloading data for {}'.format(market))

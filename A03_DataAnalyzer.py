# Investment Data Analyzer

'''
The purpose of this program is to take the file we made in the previous steps
and calculate numerous risk metrics based on it. Then, we will take those 
new results and write them back to the same CSV file.
'''

import pandas as pd
import datetime as dt
import numpy as np
from A04_Functions import InvestmentFunctions
import sqlite3 
import logging 

logging.basicConfig(filename = 'D01_Log.txt', level = logging.INFO, format = '%(asctime)s | %(levelname)s | %(message)s')

# Define a new class to analyze the data and calculate the risk metrics
class DataAnalyzer:

    # Define a method to initialize the class
    def __init__(self): 
        self.conn = sqlite3.connect('C01_Database.db') # Connects to database
        self.now = dt.datetime.now() # Gets the current date
        self.current_month = self.now.month - 1 # Gets the current month

        self.current_year = self.now.year # Gets the current year 
        self.date_id = str(self.current_month) + str(self.current_year) # Creates the date ID 
        df = pd.read_sql_query('SELECT * FROM Symbol', self.conn) # Reads the data from symbol

        self.cost_basis_dict = (df.set_index('Symbol_ID')['Updated_Cost_Basis'].to_dict()) # Creates a dictionary for the cost basis
        self.file_path = 'your_file_path_here' # Sets the file path to the bank statement
        self.Inv_Func = InvestmentFunctions() # Initializes the investment functions class

    # Define another function to get the data needed to calculate the risk metrics 
    def data_format(self):

        # Obtain general portfolio overview data and transaction data
        self.overview = self.Inv_Func.data['Portfolio_Overview']
        self.df_trans = self.Inv_Func.data['Transactions']

        # Specify the objects and variables to return 
        logging.info(f'6) Successfully retrieved the data from the repository for analysis')

        # Return the data 
        return self.overview, self.df_trans 

    # Define the function to begin analyzing the data 
    def summary_metrics(self):

        # Define a try block to begin calculating the metrics 
        try:
            # Next, we are going to define some variables needed for the metric calculations 
            self.overview = self.overview.sort_values(['Symbol_ID', 'Date_ID']).copy()
            self.overview['Total_Value'] = pd.to_numeric(self.overview['Total_Value'], errors = 'coerce')
            self.overview['Previous_Total_Value'] = pd.to_numeric(self.overview.groupby('Symbol_ID')['Total_Value'].shift(1), errors = 'coerce')

            # ---------------MONTHLY RETURN----------------
            self.overview['Monthly_Return'] = (((self.overview['Total_Value'] - self.overview['Previous_Total_Value']) / self.overview['Previous_Total_Value'])).round(4)
            
            # ---------------SUMMARY DATAFRAME----------------
            self.latest_rows = self.overview.groupby('Symbol_ID').tail(1).copy() # Makes the latest rows object

            self.summary = pd.DataFrame()
            self.summary['Symbol_ID'] = self.latest_rows['Symbol_ID'].values
            self.summary['Latest_Total_Value'] = (pd.to_numeric(self.latest_rows['Total_Value'], errors = 'coerce').values)

            self.summary['Previous_Total_Value'] = (pd.to_numeric(self.latest_rows['Previous_Total_Value'], errors='coerce').values)
            self.summary['Cost Basis'] = (self.summary['Symbol_ID'].map(self.cost_basis_dict).values)

            # ---------------GAIN / LOSS----------------
            self.summary['Gain / Loss'] = (self.summary['Latest_Total_Value'] - self.summary['Cost Basis']).round(2)
            self.summary['Gain / Loss (%)'] = ((self.summary['Gain / Loss'] / self.summary['Cost Basis']) * 100).round(2)

            # ---------------DIVIDEND YIELD----------------
            income = pd.to_numeric(self.Inv_Func.data['Transactions'].groupby('Symbol_ID')['Amount'].sum(), errors = 'coerce') # Obtain total income per symbol 
            shares_latest = pd.to_numeric(self.Inv_Func.data['Portfolio_Overview'].sort_values('Date_ID').groupby('Symbol_ID')['Shares'].last(), errors = 'coerce') 

            div_per_share = income / shares_latest
            share_price = self.summary['Latest_Total_Value'] / shares_latest.values
            self.summary['Dividend Yield (%)'] = ((div_per_share / share_price) * 100).round(2) # Calculate dividend yield 

            # Return the variables we need later
            logging.info(f'7) Successfully calculated the summary metrics')
            return self.overview, self.summary, self.latest_rows # Return the variables 

        # Now, we are going to provide an except block for some error handling 
        except Exception as e:
            print(f'There was an error calculating the summary metrics: {e}')
            raise 

    def time_series_metrics(self):
        
        # Define a try block to begin calculating the time-series metrics
        try:
            # ---------------S&P 500 RETURN---------------
            self.sp500_return = self.Inv_Func.get_sp500_return() # Gets the S&P 500 return for the previous period 
            
            # ---------------SHARPE RATIO---------------
            self.sharpe_dict = self.Inv_Func.sharpe_ratio_calc()

            # ---------------SECTOR WEIGHTS / ASSET CLASSES---------------
            self.tickers = self.Inv_Func.get_tickers()
            self.sector_weights = self.Inv_Func.get_etf_sector_weights()
            self.asset_classes = self.Inv_Func.get_asset_classes()

            # Return the variables needed by the next function
            logging.info(f'8) Successfully calculated the time series metrics')
            return self.sp500_return, self.sharpe_dict, self.sector_weights, self.asset_classes
        
        # Provide an except block for some error handling
        except Exception as e:
            print(f'There was an error calculating the time-series metrics: {e}')
            raise 

    def output_data(self):

        # Next, we are going to map all of the risk metrics to their associated months 
        self.overview['Gain / Loss'] = np.nan
        self.overview['Gain / Loss (%)'] = np.nan
        self.overview['Dividend Yield (%)'] = np.nan
        self.overview['Sharpe Ratio'] = np.nan

        # Now, we are going to index the latest_rows variable 
        latest_indices = self.latest_rows.index

        # Now, we are going to add each of the new risk metrics to the file 
        self.overview.loc[latest_indices, 'Gain / Loss'] = self.overview.loc[latest_indices, 'Symbol_ID'].map(self.summary.set_index('Symbol_ID')['Gain / Loss'])
        self.overview.loc[latest_indices, 'Gain / Loss (%)'] = self.overview.loc[latest_indices, 'Symbol_ID'].map(self.summary.set_index('Symbol_ID')['Gain / Loss (%)'])
        self.overview.loc[latest_indices, 'Dividend Yield (%)'] = self.overview.loc[latest_indices, 'Symbol_ID'].map(self.summary.set_index('Symbol_ID')['Dividend Yield (%)'])
        self.overview.loc[latest_indices, 'Sharpe Ratio'] = self.overview.loc[latest_indices, 'Symbol_ID'].map(self.sharpe_dict)
        self.overview.loc[latest_indices, 'SP500 Return (%)'] = self.sp500_return

        # Finally, we are going to write these new results to the file 
        self.current_data = self.overview.loc[latest_indices].copy()
        self.current_data = self.current_data.drop(columns = ['ID', 'Shares', 'Total_Value', 'Previous_Total_Value'])
        self.current_data = self.current_data.rename(columns = {'Gain / Loss': 'Gain_Loss', 'Gain / Loss (%)': 'Gain_Loss (%)',
                    'Dividend Yield (%)': 'Dividend_Yield', 'Sharpe Ratio': 'Sharpe_Ratio', 'SP500 Return (%)': 'S&P500_Return'})

        # Write the data to the SQL database
        if self.Inv_Func.check_existing_data('Metrics') == True:
            logging.info(f'9) There is existing data in the metrics table for this period. Skipping the append step')
        else:
            self.current_data['Date_ID'] = self.date_id
            self.current_data['Month'] = self.current_month
            self.current_data['Year'] = self.current_year

            logging.info(f'9) Successfully wrote the metrics to the database')
            self.current_data.to_sql('Metrics', self.conn, if_exists = 'append', index = False)

        # Write the sector weights to the SQL database as well
        self.sector_weights.to_sql('Sector_Weights', self.conn, if_exists = 'replace', index = False)
        self.asset_classes.to_sql('Asset_Classes', self.conn, if_exists = 'replace', index = False)

        # Ensure that we update the log
        logging.info(f'----------Data Pipeline Ended----------')

# Run the class
if __name__ == '__main__':
    analyzer = DataAnalyzer()
    analyzer.data_format()
    analyzer.summary_metrics()
    analyzer.time_series_metrics()
    analyzer.output_data()
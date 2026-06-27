# Investment Data Analyzer

'''
The purpose of this program is to take the file we made in the previous steps
and calculate numerous risk metrics based on it. Then, we will take those 
new results and write them back to the same CSV file.
'''

import pandas as pd
import datetime as dt
import numpy as np
from A04_Functions import get_sp500_return, get_rfr, get_etf_sector_weights, sharpe_ratio_calc, get_asset_classes, get_tickers
import sqlite3 
import logging 

# Connect to the database and set up logging configuration
conn = sqlite3.connect('C01_Database.db')
logging.basicConfig(filename = 'D01_Log.txt', level = logging.INFO, format = '%(asctime)s | %(levelname)s | %(message)s')

# Obtain the date infomration so that we can add this later
now = dt.datetime.now()
current_month = now.month - 1
current_year = now.year

# Create the date ID 
date_id = int(f'{current_month}{current_year}')
cost_basis_dict = pd.read_sql_query('SELECT * FROM Symbol', conn)
cost_basis_dict = cost_basis_dict.set_index('Symbol_ID')['Updated_Cost_Basis'].to_dict()

def data_format(conn):
    # Obtain general portfolio overview data and transaction data
    df = pd.read_sql_query(f'SELECT * FROM Portfolio_Overview', conn)
    df_trans = pd.read_sql_query(f'SELECT * FROM Transactions', conn)

    # Specify the objects and variables to return 
    logging.info(f'6) Successfully read the data from the repository for analysis')
    return df, df_trans # Return the data frame 

# Define the function to begin analyzing the data 
def summary_metrics(df, cost_basis_dict, df_trans):
    try:
        # Next, we are going to define some variables needed for the metric calculations 
        df = df.sort_values(['Symbol_ID', 'Date_ID']).copy()
        df['Total_Value'] = pd.to_numeric(df['Total_Value'], errors = 'coerce')
        df['Previous_Total_Value'] = pd.to_numeric(df.groupby('Symbol_ID')['Total_Value'].shift(1), errors = 'coerce')

        # The first metric we are going to calculate is the monthly return
        df['Monthly_Return'] = (((df['Total_Value'] - df['Previous_Total_Value']) / df['Previous_Total_Value']) * 100).round(2)

        # Now we are going to obtain the latest rows for each symbol
        latest_rows = df.groupby('Symbol_ID').tail(1).copy()

        # Create the summary data frame 
        summary = pd.DataFrame()
        summary['Symbol_ID'] = latest_rows['Symbol_ID'].values
        summary['Symbol_ID'] = latest_rows['Symbol_ID'].values

        summary['Latest_Total_Value'] = (pd.to_numeric(latest_rows['Total_Value'], errors='coerce').values)
        summary['Previous_Total_Value'] = (pd.to_numeric(latest_rows['Previous_Total_Value'], errors='coerce').values)
        summary['Cost Basis'] = (summary['Symbol_ID'].map(cost_basis_dict).values)

        # The next metric we are going to calculate is the gain / loss and the % of it as well
        summary['Gain / Loss'] = (summary['Latest_Total_Value'] - summary['Cost Basis']).round(2)
        summary['Gain / Loss (%)'] = ((summary['Gain / Loss'] / summary['Cost Basis']) * 100).round(2)

        # The next metric we are going to calculate is the dividend yield on the df since we require ALL data 
        income = pd.to_numeric(df_trans.groupby('Symbol_ID')['Amount'].sum(), errors = 'coerce') # Obtain total income per symbol 
        shares_latest = pd.to_numeric(df.sort_values('Date_ID').groupby('Symbol_ID')['Shares'].last(), errors = 'coerce') 

        div_per_share = income / shares_latest
        share_price = summary['Latest_Total_Value'] / shares_latest.values
        summary['Dividend Yield (%)'] = ((div_per_share / share_price) * 100).round(2) # Calculate dividend yield 

        # Return the variables we need later
        logging.info(f'7) Successfully calculated the summary metrics')
        return df, summary, latest_rows # Return the variables 

    # Now, we are going to provide an except block for some error handling 
    except Exception as e:
        print(f'There was an error calculating the summary metrics: {e}')
        raise 

def time_series_metrics(df, conn):
    try:
        # Get ALL yahoo finance time-dependent data by calling their functions 
        sp500_return = get_sp500_return(now) # Gets the S&P 500 return for the previous period 
        df['S&P500_Return'] = sp500_return
        rfr = get_rfr() # Gets the risk free rate as of latest date 
        
        # Now, we are going to call the sharpe ratio and irr functions 
        sharpe_dict = sharpe_ratio_calc(df, rfr)

        # Initialize a list of tickers to use in our function 
        tickers = get_tickers(df)
        sector_weights = get_etf_sector_weights(tickers)
        asset_classes = get_asset_classes(tickers)

        # Return the variables needed by the next function
        logging.info(f'8) Successfully calculated the time series metrics')
        return sp500_return, sharpe_dict, sector_weights, asset_classes
    
    # Provide an except block for some error handling
    except Exception as e:
        print(f'There was an error calculating the time-series metrics: {e}')
        raise 

def output_data(df, summary, sp500_return, sharpe_dict, latest_rows, sector_weights, asset_classes):

    # Next, we are going to map all of the risk metrics to their associated months 
    df['Gain / Loss'] = np.nan
    df['Gain / Loss (%)'] = np.nan
    df['Dividend Yield (%)'] = np.nan
    df['Sharpe Ratio'] = np.nan

    # Now, we are going to index the latest_rows variable 
    latest_indices = latest_rows.index

    # Now, we are going to add each of the new risk metrics to the file 
    df.loc[latest_indices, 'Gain / Loss'] = df.loc[latest_indices, 'Symbol_ID'].map(summary.set_index('Symbol_ID')['Gain / Loss'])
    df.loc[latest_indices, 'Gain / Loss (%)'] = df.loc[latest_indices, 'Symbol_ID'].map(summary.set_index('Symbol_ID')['Gain / Loss (%)'])
    df.loc[latest_indices, 'Dividend Yield (%)'] = df.loc[latest_indices, 'Symbol_ID'].map(summary.set_index('Symbol_ID')['Dividend Yield (%)'])
    df.loc[latest_indices, 'Sharpe Ratio'] = df.loc[latest_indices, 'Symbol_ID'].map(sharpe_dict)
    df.loc[latest_indices, 'SP500 Return (%)'] = sp500_return

    # Finally, we are going to write these new results to the file 
    df = df.drop(columns = ['Shares', 'Total_Value', 'Previous_Total_Value'])
    df = df.rename(columns = {'ID': 'Metric_ID', 'Gain / Loss': 'Gain_Loss', 'Gain / Loss (%)': 'Gain_Loss (%)',
                   'Dividend Yield (%)': 'Dividend_Yield', 'Sharpe Ratio': 'Sharpe_Ratio', 'SP500 Return (%)': 'S&P500_Return'})

    # Add the month and year columns and write to SQL 
    df['Month'] = current_month; df['Year'] = current_year
    df = df[df['Date_ID'] == date_id]

    # Write the data to the SQL database
    df.to_sql('Metrics', conn, if_exists = 'append', index = False)

    # Write the sector weights to the SQL database as well
    sector_weights.to_sql('Sector_Weights', conn, if_exists = 'replace', index = False)
    asset_classes.to_sql('Asset_Classes', conn, if_exists = 'replace', index = False)

    # Ensure that we update the log
    logging.info(f'9) Successfully wrote the metrics to the database')
    logging.info(f'----------Data Pipeline Ended----------')

# Now, we must call all the functions 
df, df_trans = data_format(conn)
df, summary, latest_rows = summary_metrics(df, cost_basis_dict, df_trans)
sp500_return, sharpe_dict, sector_weights, asset_classes = time_series_metrics(df, conn)
output_data(df, summary, sp500_return, sharpe_dict, latest_rows, sector_weights, asset_classes)
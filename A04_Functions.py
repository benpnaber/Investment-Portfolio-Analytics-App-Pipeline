# Investment Functions

'''
The purpose of this file is to house numerous functions that are used to support the 
data analysis process that is conducted by my investment portfolio pipeline 
'''


# Import the necessary modules 
import pandas as pd 
import datetime as dt 
import yfinance as yf 
import numpy as np 
from pyxirr import xirr
import sys 

# Define the first function to get the tickers that are needed
def get_tickers(df):

    # Get all the unique tickers in the portfolio
    tickers = df['Symbol_ID'].unique().tolist()

    # Now, we need to return the tickers
    return tickers 

# Define a function to get the S&P 500 return 
def get_sp500_return(now): # Now must be a datetime object 
    end = now.replace(day=1) - dt.timedelta(days=1) # Gets last day of the previous month
    start = end.replace(day=1) - dt.timedelta(days=1) # Gets the last day of two months ago 

    # Define a try block to download the S&P return 
    try:
        while start.weekday() > 4: # Weekday 4 is Friday (we do not want weekends) 
            start -= dt.timedelta(days=1)
        sp500 = yf.download('^GSPC', start = start - dt.timedelta(days = 5), end = end + dt.timedelta(days = 1), progress = False)['Close']

        start_price = sp500.loc[:start].iloc[-1] # Get the first price of the period 
        end_price = sp500.loc[:end].iloc[-1] # Get the last price of the period 
        return ((end_price - start_price) / start_price) * 100

    # Define an except block for error handling 
    except Exception as e:
        print('There was an error downloading the S&P return: ', e)
        sys.exit()  

# Define a function to obtain the risk free rate 
def get_rfr():

    import yfinance as yf
    import sys
    # We are going to define a try block to download the risk free rate 
    try:
        rfr = yf.download('^IRX', period = '1mo', progress = False) # IRX is the 3-month treasury yield 
        rfr_annual = rfr['Close'].iloc[-1] / 100 # Divide the risk free rate by 100 to get % form

        # Convert the risk free rate to monthly 
        rfr_monthly = (1 + rfr_annual)**(1/12) - 1 # Because it is an annualized rate, we must diivde by 12 
        rfr_monthly = rfr_monthly.iloc[0]
        return rfr_monthly # Return the monthly risk free rate 
    
    except Exception as e: # Define an except block to provide error handling 
        print('There was an error downloading the risk free rate', e)
        sys.exit() 

# Define a function to get the sharpe ratio
def sharpe_ratio_calc(df, rfr): 
    sharpe_dict = {} # Initialize a dictionary 
    for name, group in df.groupby('Symbol_ID'): # Name represents each symbol and group represents each grouped data frame 
        x = group['Monthly_Return'].dropna() # Groups NA in monthly returns for the current grouped data frame 

        # Define an if statement that provides error handling features 
        if len(x) < 2:
            sharpe_dict[name] = np.nan
            continue 

        # Next, we are going to calculate the values for the sharpe ratio 
        try:
            average = x.mean() # Calculates the mean 
            standard_dev = x.std(ddof = 1) # Ddof = 1 sets # of observations to sample rather than population total

            # Now, we will assign the value 
            sharpe_ratio = round((average - (rfr / 12)) / standard_dev, 4)    
            sharpe_dict[name] = sharpe_ratio # Assign values to the dictionary

            # Now, we are going to provide an except block for some error handling
        except ZeroDivisionError:
            print('There has been a divide-by-0 error with the calculation')
    return sharpe_dict # Return it 

# Next, define a function to obtain the sector weightings 
def get_etf_sector_weights(tickers): 
    all_dfs = []

    for ticker in tickers:
        etf = yf.Ticker(ticker)
        data = etf.funds_data.sector_weightings

        if data is not None:
            df = pd.DataFrame(list(data.items()), columns=['Sector', 'Weight'])
            df['Ticker'] = ticker
            all_dfs.append(df)

    # Combine and pivot
    final_df = pd.concat(all_dfs, ignore_index = True) 
    sector_weights = final_df.pivot(index = 'Ticker', columns = 'Sector', values = 'Weight').reset_index().rename(columns = {'Ticker': 'Symbol_ID'})

    # Return the individual sector weights
    return sector_weights

# Define another function get the aggregate sector weights for the portfolio 
def get_portfolio_sector_weights(overview, sector_weights):

    # Pull cost basis from DB, exclude non-equity holdings, and merge on ticker
    overview = (overview[~overview['Symbol_ID'].isin(['AAA', 'BBB'])] [['Symbol_ID', 'Total_Value']])
    
    sector_weights = sector_weights.merge(overview[['Symbol_ID', 'Total_Value']], left_on = 'Symbol_ID', right_on = 'Symbol_ID', how = 'left').set_index('Symbol_ID')
    sector_weights = sector_weights.rename(columns = {'Total_Value': 'Amount'})

    # Calculate portfolio-weighted sector exposures
    tot_val = sector_weights['Amount'].sum()
    sector_cols = [col for col in sector_weights.columns if col != 'Amount']
    
    weights = sector_weights[sector_cols].multiply(sector_weights['Amount'] / tot_val, axis = 0)
    weights = weights.sum(axis = 0)

    weights = weights.reset_index() 
    weights.columns = ['Sector', 'Weight']

    # Now, we are going to return the weights 
    return weights

def best_buy_sell(hypo_weights, sector_weights, tickers):

    # Find sectors exceeding the 20% threshold
    sector_overweight = hypo_weights[hypo_weights['Weight'] > 0.20]

    # Read ETF sector compositions
    individual_weights = sector_weights

    # Initialize dictionaries
    etf_scores = {}

    # Calculate a score for each ETF
    for ticker in tickers:

        # Get sector data for this ETF
        etf_data = individual_weights[individual_weights['Symbol_ID'] == ticker]

        # Skip if ETF not found
        if etf_data.empty:
            continue

        score = 0

        # Loop through all overweight sectors
        for _, row in sector_overweight.iterrows():

            sector = row['Sector']
            overweight_amount = row['Weight'] - 0.20

            # Add weighted penalty
            score += (etf_data[sector].iloc[0] * overweight_amount)

        etf_scores[ticker] = score

    # Best sell = highest score
    best_sell = max(etf_scores, key = etf_scores.get)

    # Best buy = lowest score
    best_buy = min(etf_scores, key=etf_scores.get)
    return {'Best_Sell': best_sell,'Best_Buy': best_buy}

# The next function we are going to define is to retrieve the asset classes of the holdings in the portfolio
def get_asset_classes(tickers, overview):

    # Create an empty dictionary to store the asset classes
    asset_classes = []

    # Define a loop to go through all tickers and retrieve the data
    for ticker in tickers:

        etf = yf.Ticker(ticker)
        info = etf.funds_data.asset_classes
        
        # Now, we are going to convert the info into a dataframe
        info = pd.DataFrame([info], columns = list(info.keys()))
        info['Symbol_ID'] = ticker

        # Append it to the list
        asset_classes.append(info)

    # Now, we need to concatenate all the data frames into one list
    final_df = pd.concat(asset_classes, ignore_index = True)

    # Now, we are going to select the symbol ID and total value from overview
    overview = (overview[overview['Date_ID'] == overview['Date_ID'].max()][['Symbol_ID', 'Total_Value']])
    final_df = final_df.merge(overview, left_on = 'Symbol_ID', right_on = 'Symbol_ID', how = 'left')

    # Now, we need to calculate the overall weights of each asset class in the portfolio
    asset_class = [col for col in final_df.columns if col not in ['Symbol_ID', 'Total_Value']]
    final_df['Total_Value']= pd.to_numeric(final_df['Total_Value'], errors = 'coerce')

    # Calculate portfolio-level weights in one shot (no nested loop needed)
    total_portfolio_value = final_df['Total_Value'].sum()
    for asset in asset_class:
        final_df[asset + '_Weight'] = (final_df[asset] * final_df['Total_Value']) / total_portfolio_value

    # Keep only Symbol_ID and weight columns
    weight_cols = [col for col in final_df.columns if col.endswith('_Weight')]
    final_df = final_df[['Symbol_ID'] + weight_cols]

    # Now, we need to rename the columns to be easier to read
    final_df = final_df.rename(columns = {'cashPosition_Weight': 'Cash_Weight', 'stockPosition_Weight': 'Stock_Weight', 
                                          'bondPosition_Weight': 'Bond_Weight', 'preferredPosition_Weight': 'Preferred_Weight',
                                          'convertiblePosition_Weight': 'Convertible_Weight', 'otherPosition_Weight': 'Other_Weight'})
    
    # Now, we are going to sum the values
    result = final_df.drop(columns = ['Symbol_ID']).sum().reset_index()
    result.columns = ['Asset_Class', 'Weight']

    # Now, we need to return the final object
    return result
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
import sqlite3

# Define a class to hold all these helper functions
class InvestmentFunctions:

    # Define the __init__method to initialize the class
    def __init__(self):
        self.conn = sqlite3.connect('C01_Database.db') # Done for now
        self.now = dt.datetime.now() # Gets the current date and time 
        self.date_id = int(f'{self.now.month - 1}{self.now.year}') # Creates the date ID 

        # Call the helper functions
        self._get_data_from_db() # Call the get data function 
        self.get_tickers() # Gets the tickers

    # Define a helper function to get the tables and data from the database
    def _get_data_from_db(self):

        # Make an empty dictinary to hold the data
        self.data = {} 

        # Use the conn from init to create the cursor
        self.cursor = self.conn.cursor() 
        self.tables = self.cursor.execute('SELECT name FROM sqlite_master WHERE type = "table"').fetchall() # Gets all table names

        self.tables = [table[0] for table in self.tables] # Unpack the tuples into a list of table names 
        for i in self.tables:
            self.data[i] = self.cursor.execute(f'SELECT * FROM {i}').fetchall() # Gets all the data 

            # Get the column names out
            columns = columns = [col[1] for col in self.cursor.execute(f'PRAGMA table_info({i})').fetchall()] # Gets the column names
            self.data[i] = pd.DataFrame(self.data[i], columns = columns) # Converts the data into a data frame 

    # Define the first function to get the tickers that are needed
    def get_tickers(self):

        # Get all the unique tickers in the portfolio
        self.tickers = self.data['Portfolio_Overview']['Symbol_ID'].unique().tolist()
        return self.tickers 

    # Define a function to get the S&P 500 return 
    def get_sp500_return(self): 

        # Get the end and start date of the previous month 
        end = self.now.replace(day = 1) - dt.timedelta(days = 1) # Gets last day of the previous month
        start = end.replace(day = 1) - dt.timedelta(days =1) # Gets the last day of two months ago 

        # Define a try block to download the S&P return 
        try:
            while start.weekday() > 4: # Weekday 4 is Friday (we do not want weekends) 
                start -= dt.timedelta(days = 1)

            # Download the data
            sp500 = yf.download('^GSPC', start = start, end = end, progress = False)['Close'].squeeze()
            start_price = sp500.iloc[0] # Get the first price of the period 

            end_price = sp500.iloc[-1] # Get the last price of the period 
            self.market_return = (end_price - start_price) / start_price

            # Now, we are going to return the market return
            return self.market_return

        # Define an except block for error handling 
        except Exception as e:
            print('There was an error downloading the S&P return: ', e)
            raise

    # Define a function to obtain the risk free rate 
    def get_rfr(self):

        # We are going to define a try block to download the risk free rate 
        try:
            self.rfr = yf.download('^IRX', period = '1mo', progress = False) # IRX is the 3-month treasury yield 
            rfr_annual = self.rfr['Close'].iloc[-1] / 100 # Divide the risk free rate by 100 to get % form

            # Convert the risk free rate to monthly 
            self.rfr_monthly = (1 + rfr_annual) ** (1 / 12) - 1 # Because it is an annualized rate, we must diivde by 12 
            self.rfr_monthly = self.rfr_monthly.iloc[0]

            # Return the risk free rate
            return self.rfr_monthly 
        
        except Exception as e: # Define an except block to provide error handling 
            print('There was an error downloading the risk free rate', e)
            raise

    # Define a function to get the sharpe ratio
    def sharpe_ratio_calc(self): 

        # Create an empty dictionary and get the risk free monthly
        self.sharpe_dict = {} # Initialize a dictionary 
        self.rfr_monthly = self.get_rfr()
        
        for name, group in self.data['Metrics'].groupby('Symbol_ID'): # Name represents each symbol and group represents each grouped data frame 
            x = group['Monthly_Return'].dropna() # Groups NA in monthly returns for the current grouped data frame 

            # Define an if statement that provides error handling features 
            if len(x) < 2:
                self.sharpe_dict[name] = np.nan
                continue 

            # Next, we are going to calculate the values for the sharpe ratio 
            try:
                average = x.mean() # Calculates the mean 
                standard_dev = x.std(ddof = 1) # Ddof = 1 sets # of observations to sample rather than population total

                # Now, we will assign the value 
                self.sharpe_ratio = round((average - self.rfr_monthly) / standard_dev, 4)    
                self.sharpe_dict[name] = self.sharpe_ratio # Assign values to the dictionary

            # Provide the corresponding except block 
            except ZeroDivisionError:
                print('There has been a divide-by-0 error with the calculation')

        # Return the data 
        return self.sharpe_dict 

    # Write another function to calculate the geometric mean
    def geometric_mean(self):

        # Initialize a new dictionary
        geo_means = {} 

        # Get the metrics data and group it by date ID and symbol ID
        metrics = self.data['Metrics'] # Retrieves metrics
        metrics = metrics.groupby('Symbol_ID')

        # Now, we are going to calculate the geometric mean
        for symbol_id, group in metrics:
            returns = group['Monthly_Return']  
            returns = returns.dropna() 

            # Calculate the mean
            geo_mean = (1 + returns).prod() ** (1 / len(returns)) - 1 if len(returns) != 0 else 0
            geo_means[symbol_id] = geo_mean
        
        # Convert the dictionary to a data frame
        geo_means_df = (pd.DataFrame.from_dict(geo_means, orient = 'index', columns = ['Geo_Mean_Return'])
                        .reset_index().rename(columns = {'index': 'Symbol_ID'}))
        
        # Return the data
        return geo_means_df

    # Next, define a function to obtain the sector weightings 
    def get_etf_sector_weights(self): 

        # Initialize an empty list to hold data frames
        all_dfs = []
        self.get_tickers()

        for ticker in self.tickers:
            etf = yf.Ticker(ticker)
            data = etf.funds_data.sector_weightings

            if data is not None:
                df = pd.DataFrame(list(data.items()), columns = ['Sector', 'Weight'])
                df['Ticker'] = ticker
                all_dfs.append(df)

        # Combine and pivot
        final_df = pd.concat(all_dfs, ignore_index = True) 
        self.sector_weights = final_df.pivot(index = 'Ticker', columns = 'Sector', values = 'Weight').reset_index().rename(columns = {'Ticker': 'Symbol_ID'})

        # Return the individual sector weights
        return self.sector_weights

    # Define another function get the aggregate sector weights for the portfolio 
    def get_portfolio_sector_weights(self, overview = None, etf_sector_weights = None):

        # Evaluate if the overview object is none
        if overview is None:
            overview = self.data['Portfolio_Overview']

        # Evaluate if etf sector weights is none and if it is, call the function 
        if etf_sector_weights is None:
            self.get_etf_sector_weights()
        else:
            self.sector_weights = etf_sector_weights.copy()

        # Pull the cost basis from the DB, exclude non-equity holdings, and merge on ticker
        overview = overview[~overview['Symbol_ID'].isin(['BND', 'GLD'])][['Symbol_ID', 'Total_Value']]
        
        self.sector_weights = self.sector_weights.merge(overview, on = 'Symbol_ID', how = 'left').set_index('Symbol_ID')
        self.sector_weights = self.sector_weights.rename(columns = {'Total_Value': 'Amount'})
        self.sector_weights['Amount'] = pd.to_numeric(self.sector_weights['Amount'], errors='coerce')

        # Calculate portfolio-weighted sector exposures
        tot_val = self.sector_weights['Amount'].sum()
        sector_cols = [col for col in self.sector_weights.columns if col != 'Amount']
        
        self.weights = self.sector_weights[sector_cols].multiply(self.sector_weights['Amount'] / tot_val, axis = 0)
        self.weights = self.weights.sum(axis = 0)

        self.weights = self.weights.reset_index() 
        self.weights.columns = ['Sector', 'Weight']

        # Return the data frame of sector weights 
        return self.weights

    # Define a function to determine the best buy or sell (NOTE: DOES NOT USE SELF B/C IT IS RUN IN the R SHINY APP, NOT PYTHON)
    def best_buy_sell(self, hypo_weights, sector_weights, tickers):

        # Find sectors exceeding the 20% threshold
        sector_overweight = hypo_weights[hypo_weights['Weight'] > 0.20]

        # Read ETF sector compositions
        individual_weights = sector_weights

        # Initialize dictionaries
        etf_scores = {}

        # Calculate a score for each ETF
        for ticker in tickers:
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
    def get_asset_classes(self):

        # Create an empty dictionary to store the asset classes and define a for loop
        asset_classes = [] # Initialize a new list 

        for ticker in self.tickers:
            etf = yf.Ticker(ticker)
            info = etf.funds_data.asset_classes
                
            # Now, we are going to convert the info into a dataframe
            info = pd.DataFrame([info], columns = list(info.keys()))
            info['Symbol_ID'] = ticker
            asset_classes.append(info) # Append it to the list

        # Now, we need to concatenate all the data frames into one list
        self.asset_classes = pd.concat(asset_classes, ignore_index = True)
        return self.asset_classes # Returns the data 
    
    # Define a new function to calculate the aggregate asset class weights
    def get_portfolio_class_weights(self, overview = None, asset_classes = None ): 

        # Evaluate if overview is none 
        if overview is None:
            overview = (self.data['Portfolio_Overview'].loc[self.data['Portfolio_Overview']['Date_ID'] == self.data['Portfolio_Overview']['Date_ID'].max()]
                        [['Symbol_ID', 'Total_Value']])
        else:
            overview = overview[['Symbol_ID', 'Total_Value']]

        # Properly assign the asset classes data object
        if asset_classes is None:
            final_df = self.get_asset_classes() 
        else:
            final_df = asset_classes.copy() 

        # Merge the final dataframe onto the overview object
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
        self.result = final_df.drop(columns = ['Symbol_ID']).sum().reset_index()
        self.result.columns = ['Asset_Class', 'Weight']

        # Now, we need to return the final object
        return self.result

    # Define another function to identify the main sector (highest concentration) for each ticker 
    def primary_sector(self):

        # Initialize a new dictionary
        largest_sectors = {} 

        # Get the sector weights data 
        sectors = self.data['Sector_Weights']
        for ticker in self.tickers:

            # Get only the numeric cols
            num_cols = [col for col in sectors.columns if col != 'Symbol_ID']
            row  = sectors[sectors['Symbol_ID'] == ticker]

            # Provide some error handling
            if row.empty:
                largest_sectors[ticker] = None
                continue

            # Find the sector in the table that is the largest per ticker 
            biggest_sector = row[num_cols].iloc[-1].idxmax()
            biggest_sector = biggest_sector.replace('_', ' ').title() 
            largest_sectors[ticker] = biggest_sector

        # Convert this to a data frame and return it
        largest_sectors_df = (pd.DataFrame.from_dict(largest_sectors, orient = 'index', columns = ['Primary_Sector'])
                        .reset_index().rename(columns = {'index': 'Symbol_ID'}))
        return largest_sectors_df
    
    # Define another function that determines IF SOME TABLES already have data for this month and year so if we run the pipeline twice, we do not duplicate data
    def check_existing_data(self, table):

        # Get the current month and year
        data = self.cursor.execute(f'SELECT * FROM {table} WHERE Date_ID = {self.date_id}').fetchall() # Gets all the data for the current month and year 
        if len(data) > 0: 
            return True # Meaning the date_ID is in the data 
        else:
            return False
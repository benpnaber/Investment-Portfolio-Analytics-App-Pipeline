# Investment Portfolio Management System

'''
The purpose of this script is to analyze a OFX csv download file from your bank, extract valuable insights,
format all data into one table, and write the results to a SQL database.
'''

# Import the modules
import pandas as pd 
import datetime as dt 
import sqlite3
import logging 
import io
from A04_Functions import InvestmentFunctions

# Connect to the database
logging.basicConfig(filename = 'D01_Log.txt', level = logging.INFO, format = '%(asctime)s | %(levelname)s | %(message)s')
logging.info('----------Date Pipeline Started----------')

# Define a new class for the investent parser
class InvestmentParser:

    # Define the init method to initialize the class
    def __init__(self):
        self.conn = sqlite3.connect('sqlite3_file') # Connects to database
        self.now = dt.datetime.now() # Gets the current date
        self.current_month = self.now.month - 1 # Gets the current month

        self.current_year = self.now.year # Gets the current year 
        self.date_id = str(self.current_month) + str(self.current_year) # Creates the date ID 
        self.cost_basis = pd.read_sql_query('SELECT * FROM Symbol', self.conn) # Reads the symbol table 

        self.file_path = 'your_file_path_here' # Sets the file path to the bank statement
        self.Inv_Func = InvestmentFunctions() # Initializes the investment functions class

    # Now, we are going to define the function to do the parsing of the statements 
    def parse_csv(self):

        # We are going to define some try blocks to provide error handling
        try:
            with open(self.file_path, 'r') as f: # Opens the file 
                lines = f.readlines() # Creates a list of all lines in the CSV file 
        except Exception as e:
            logging.error(f'There was an error reading the data: {e}')
            raise 
        
        # There are 2 tables in the csv file. The first table contains general information, the second one contains transaction data 
        # We need to split the file (and the corresponding tables) into two separate dataframes, and find the index of the row where the second table starts 
        try:
            split_index = next(i for i, line in enumerate(lines) if 'Trade Date' in line) # Returns the index of the the line with trade (forceably iterates)
        
            holdings_text = ''.join(lines[1:split_index]) # Concatenates a list of strings into one string 
            transactions_text = ''.join(lines[split_index:]) # The quotes at the beginning denote the separator so there is none here 

            self.df_holdings = pd.read_csv(io.StringIO(holdings_text), header = None) # Creates an in memory file object that read_csv can read
            self.df_transactions = pd.read_csv(io.StringIO(transactions_text), header = None) # Same thing here 

            # Update the log
            logging.info('1) Successfully read the the bank statement')

        # Now, we are going to provide an except block in case of an error 
        except Exception as e:
            logging.error(f'There was an error splitting the tables {e}', exc_info = True)
            raise 

    # Now, we are going to define a function to format the data 
    def data_format(self): 

        # Take the holdings and transactions data frames and select their columns as well as format them 
        try:
            # Select the relevant columns from each data frame and rename them 
            self.df_holdings = self.df_holdings.iloc[:, [2, 3, 5]]
            self.df_transactions = self.df_transactions.iloc[:, [1, 3, 6, 9]]

            self.df_holdings.columns = ['Symbol_ID', 'Shares', 'Total_Value']
            self.df_transactions.columns = ['Date', 'Transaction_Type', 'Symbol_ID', 'Amount']

            # Create the date ID column in the transactions table and filter to the relevant transaction types
            transaction_type = ['Dividend', 'Buy', 'Sell']
            self.df_transactions['Date_ID'] = self.date_id # Makes the date ID column
            self.transactions = (self.df_transactions['Date_ID'] == self.date_id) & (self.df_transactions['Transaction_Type'].isin(transaction_type))

            # Filter transactions to only include transaction types and remove unnecessary tickers transactions (this is a money market fund which is not relevant to our analysis)
            self.transactions = self.df_transactions[self.transactions]
            self.transactions = self.transactions[self.transactions['Symbol_ID'] != 'any_unnecessary_symbols']

            # Now, we need to filter only the dividend transactions into a new dataframe 
            self.df_transactions = self.df_transactions[self.df_transactions['Transaction_Type'] == 'Dividend']
            self.df_transactions['Amount'] = pd.to_numeric(self.df_transactions['Amount'])

            # Now, we need to merge df_dividends with df1 to get the investment names associated with each dividend transaction 
            self.df_merged = pd.merge(self.df_transactions, self.df_holdings, left_on = 'Symbol_ID', right_on = 'Symbol_ID', how = 'right') 
            self.df_merged = self.df_merged.loc[:, ['Symbol_ID', 'Shares', 'Total_Value', 'Amount']] # Select only the relevant columns 

            # Now, we are going to fill all dividend amounts with 0 if there is none 
            missing_dividends = (self.df_merged['Symbol_ID'].isna() & self.df_merged['Amount'].notna()).sum()
        
            if missing_dividends > 0: 
                logging.error(f'There are {missing_dividends} missing dividend amounts', exc_info = True)
                raise 
            else:
                self.df_merged = self.df_merged.dropna(subset = ['Symbol_ID'])

            # Return the variables that we need later
            return self.df_merged
    
        # Now, we are going to provide an except block in case of an error 
        except Exception as e:
            logging.error(f'There was an error with column selection and data formatting {e}', exc_info = True)
            raise 
    
    def _cost_basis_calc(self):

        # Define a try block to proivde error handling
        try:
            df_symbol = self.Inv_Func.data['Symbol'] # Get the symbol table 
            old_cost_basis = (df_symbol.set_index('Symbol_ID')['Updated_Cost_Basis'].astype(float).round(2).fillna(0))

            # Total dividend amounts by symbol and get the new basis 
            dividend_amounts = (self.df_merged[self.df_merged['Amount'].notna()].groupby('Symbol_ID')['Amount'].sum())
            self.new_cost_basis = old_cost_basis.add(dividend_amounts, fill_value = 0)

            # Return the new cost basis 
            logging.info(f'3) Successfully updated {len(self.new_cost_basis)} rows')

            # Return the data 
            return self.new_cost_basis
        
        # Now, we are going to provide an except block in case of an error
        except Exception as e:
            logging.error(f'There was an error calculating the new cost basis {e}', exc_info = True)
            raise

    def write_sql(self):

        # Add the current month, the current year, return, and cost basis columns to the data frame 
        self.df_merged['Date_ID'] = str(self.current_month) + str(self.current_year)

        # Now, we are going to define another try block to provide some error handling 
        try:
            # Rename the columns so they match the column names in the SQL database
            df_symbol = self.df_merged[['Symbol_ID']]
            self.df_merged = self.df_merged[['Date_ID', 'Symbol_ID', 'Shares', 'Total_Value']]

            # ---------------TRANSACTION DATA WRITE-----------------
            if self.Inv_Func.check_existing_data('Transactions') == True: 
                logging.info('2) There is existing data in the transactions table for this period. Skipping the append step')
            else:
                logging.info('2) Successfully appended data to transactions table')
                self.transactions.to_sql('Transactions', self.conn, if_exists = 'append', index = False)

            # ---------------PORTFOLIO DATA WRITE-----------------
            if self.Inv_Func.check_existing_data('Portfolio_Overview') == True:
                logging.info('4) There is existing data in the portfolio table for this period. Skipping the append step')
            else:
                self.df_merged = self.df_merged[self.df_merged['Symbol_ID'] != 'any_unnecessary_symbols']
                self.df_merged['Date_ID'] = str(self.current_month) + str(self.current_year)

                self.df_merged.to_sql('Portfolio_Overview', self.conn, if_exists = 'append', index = False)
                logging.info('4) Successfully appended the data to portfolio table')

            # --------------SYMBOL DATA WRITE-----------------
            if self.Inv_Func.check_existing_data('Transactions') == True: # We do transactions instead of symbol b/c symbol is based on transsactions
                logging.info('5) There is existing data in the Transactions / Symbol table for this period. Skipping the overwrite step')
            else:
                updated_cost_basis = self._cost_basis_calc() # Calculate the new cost basis
                df_symbol = self.df_merged[['Symbol_ID']] # Make the data fame with relevant columns 
               
                df_symbol['Updated_Cost_Basis'] = df_symbol['Symbol_ID'].map(updated_cost_basis) # Update the cost basis
                df_symbol.to_sql('Symbol', self.conn, if_exists = 'replace', index = False)
                logging.info('5) Successfully overwrote the data to symbol table')

        except Exception as e:
            logging.error(f'There was an error writing the data to the SQL database {e}',exc_info = True)
            raise 

        # Close the database connection
        self.conn.close()

# Call the class
if __name__ == '__main__':
    parser = InvestmentParser()
    parser.parse_csv()
    parser.data_format()
    parser.write_sql()
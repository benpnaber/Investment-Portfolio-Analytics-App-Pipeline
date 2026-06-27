# Investment Portfolio Management System

'''
The purpose of this script is to analyze a downloadable brokerage account statement, extract valuable insights,
format all data into one table, and write the results to a SQL database.
'''

# Import the modules
import pandas as pd 
import datetime as dt 
import sqlite3
import logging 
import io

# Connect to the database
conn = sqlite3.connect('C01_Database.db')
logging.basicConfig(filename = 'D01_Log.txt', level = logging.INFO, format = '%(asctime)s | %(levelname)s | %(message)s')
logging.info('----------Date Pipeline Started----------')

# Obtain the date information so that we can add this to our analysis later 
now = dt.datetime.now()
current_month = now.month - 1
current_year = now.year

# Create the date ID with the month and year
date_id = str(current_month) + str(current_year) 

# Finally, intialize the variables used in this program
cost_basis_dict = pd.read_sql_query('SELECT * FROM Symbol', conn)

# Now, we are going to define the function to do the parsing of the statements 
def parse_csv(file_path = None):

    # Set the file path to the  statement
    file_path = '/Path/To/Financial/Statement.csv'

    # We are going to define some try blocks to provide error handling
    try:
        with open(file_path, 'r') as f: # Opens the file 
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

        df_holdings = pd.read_csv(io.StringIO(holdings_text), header = None) # Creates an in memory file object that read_csv can read
        df_transactions = pd.read_csv(io.StringIO(transactions_text), header = None) # Same thing here 

        # Update the log
        logging.info('1) Successfully read the the statement')

    # Now, we are going to provide an except block in case of an error 
    except Exception as e:
        logging.error(f'There was an error splitting the tables {e}', exc_info = True)
        raise 

    # Select only the relevant columns from each data frame 
    try:
        df_holdings = df_holdings.iloc[:, [2, 3, 5]]
        df_transactions = df_transactions.iloc[:, [1, 3, 6, 9]]

        df_holdings.columns = ['Symbol_ID', 'Shares', 'Total_Value']
        df_transactions.columns = ['Date', 'Transaction_Type', 'Symbol_ID', 'Amount']

        # Create the date ID column in the transactions table 
        df_transactions['Date_ID'] = date_id

        # Now, in df_transactions, we need to find all transaction types that are dividends, buy, and sell, and filter them into a new dataframe 
        transaction_type = ['Dividend', 'Buy', 'Sell']
        transactions = df_transactions[df_transactions['Transaction_Type'].isin(transaction_type)]
    
        # Now, we are going to write each series of symbol transactions to a differnet sheet in an excel file 
        transactions.to_sql('Transactions', conn, if_exists = 'append', index = False)
        logging.info('2) Successfully appended data to transactions table')

        # Now, we need to filter only the dividend transactions into a new dataframe 
        df_transactions = df_transactions[df_transactions['Transaction_Type'] == 'Dividend']
        df_transactions['Amount'] = pd.to_numeric(df_transactions['Amount'])

        # Now, we need to merge df_dividends with df1 to get the investment names associated with each dividend transaction 
        df_merged = pd.merge(df_transactions, df_holdings, left_on = 'Symbol_ID', right_on = 'Symbol_ID', how = 'right') 
        df_merged = df_merged.loc[:, ['Symbol_ID', 'Shares', 'Total_Value', 'Amount']] # Select only the relevant columns 

        # Now, we are going to fill all dividend amounts with 0 if there is none 
        missing_dividends = (df_merged['Symbol_ID'].isna() & df_merged['Amount'].notna()).sum()
    
        if missing_dividends > 0: 
            logging.error(f'There are {missing_dividends} missing dividend amounts', exc_info = True)
            raise 
        else:
            df_merged = df_merged.dropna(subset = ['Symbol_ID'])

        # Return the variables that we need later
        return df_merged
 
    # Now, we are going to provide an except block in case of an error 
    except Exception as e:
        logging.error(f'There was an error with column selection and data formatting {e}', exc_info = True)
        raise 
    
def cost_basis_calc(df_merged):

    # Read symbol table and get the existing cost basis 
    df_symbol = pd.read_sql_query('SELECT * FROM Symbol', conn)
    old_cost_basis = (df_symbol.set_index('Symbol_ID')['Updated_Cost_Basis'].astype(float).round(2).fillna(0))

    # Total dividend amounts by symbol and get the new basis 
    dividend_amounts = (df_merged[df_merged['Amount'].notna()].groupby('Symbol_ID')['Amount'].sum())
    new_cost_basis = old_cost_basis.add(dividend_amounts, fill_value = 0)

    # Return the new cost basis 
    logging.info(f'3) Successfully updated {len(new_cost_basis)} rows')
    return new_cost_basis

def write_sql(df_merged, current_month, current_year, new_cost_basis, conn):

    # Add the current month, the current year, return, and cost basis columns to the data frame 
    df_merged['Date_ID'] = str(current_month) + str(current_year)
    df_merged['Updated_Cost_Basis'] = new_cost_basis


    # Now, we are going to define another try block to provide some error handling 
    try:
        # Rename the columns so they match the column names in the SQL database
        df_symbol = df_merged[['Symbol_ID', 'Updated_Cost_Basis']]
        df_symbol['Updated_Cost_Basis'] = (df_merged['Symbol_ID'].map(new_cost_basis))
        df_merged = df_merged[['Date_ID', 'Symbol_ID', 'Shares', 'Total_Value']]

        # Write to the SQL database using pandas
        df_merged.to_sql('Portfolio_Overview', conn, if_exists = 'append', index = False)
        logging.info('4) Successfully appended the data to portfolio table')

        # Write to the symbol table and get the sector weights
        df_symbol.to_sql('Symbol', conn, if_exists = 'replace', index = False)
        logging.info('5) Successfully overwrote the data to symbol table')

    except Exception as e:
        logging.error(f'There was an error writing the data to the SQL database {e}',exc_info = True)
        raise 

    # Close the database connection
    conn.close()

# Call the functions 
df_merged = parse_csv()
new_cost_basis = cost_basis_calc(df_merged)
write_sql(df_merged, current_month, current_year, new_cost_basis, conn)
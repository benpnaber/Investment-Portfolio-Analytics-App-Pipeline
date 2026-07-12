# Investment-Portfolio-Analytics-App-Pipeline

## Data Pipeline

The data pipeline is written entirely in Python and is designed to automate the collection, processing, and analysis of investment portfolio data. The pipeline consists of four core scripts, each serving a distinct role within the workflow:

* `Investment_Runner.py`
* `Investment_Parser.py`
* `Investment_DataAnalyzer.py`
* `Investment_Functions.py`

Together, these scripts transform raw brokerage statement data into structured datasets enriched with portfolio performance and risk analytics.

### Investment_Runner.py

`Investment_Runner.py` acts as the orchestration layer for the pipeline. It coordinates the execution of the parser and analytics scripts, ensuring that raw statement data is processed, analyzed, and prepared for downstream consumption through a single automated workflow.

### Investment_Parser.py

`Investment_Parser.py` serves as the entry point of the pipeline. The script reads raw brokerage statement data and parses the information into two structured datasets:

* Holdings Table
* Transactions Table

After extraction, the parser performs a series of data cleaning and transformation steps, including:

* Renaming columns for consistency
* Removing redundant or invalid records
* Standardizing data formats
* Calculating portfolio metrics such as updated cost basis values, which incorporate dividend activity and position changes

The result is a set of clean, structured datasets that can be used for further analysis.

### Investment_DataAnalyzer.py

`Investment_DataAnalyzer.py` processes the parsed portfolio data and calculates a variety of performance and risk metrics designed to provide a comprehensive view of portfolio health and investment effectiveness.

Key analytics include:

* Monthly Returns
* Percentage Gain/Loss
* Sharpe Ratio
* Risk-Adjusted Performance Metrics
* Portfolio Performance Measurements

These calculations enrich the underlying datasets and create the analytical foundation used by the portfolio visualization and reporting components of the project.

### Investment_Functions.py

`Investment_Functions.py` contains reusable helper functions that support both the parsing and analytics processes. Centralizing common functionality improves code maintainability, reduces duplication, and simplifies future enhancements to the pipeline.

### R Shiny Dashboard

The project includes an interactive R Shiny dashboard that serves as the visualization and reporting layer of the portfolio analytics pipeline. After the Python pipeline processes brokerage data and stores the results in a SQLite database, the Shiny application retrieves the data and presents it through an intuitive, interactive interface.

The dashboard allows users to explore portfolio performance across multiple dimensions, including:

Portfolio Overview
Holdings and Asset Allocation
Sector Allocation
Transaction History
Monthly Returns
Dividend Yield
Sharpe Ratio
Security Value Over Time
Individual Security Performance

Interactive filtering enables users to analyze metrics by individual security or portfolio sector, while dynamic visualizations provide insights into historical performance, risk-adjusted returns, and portfolio composition.

By separating the analytical backend (Python) from the presentation layer (R Shiny), the application provides a modular architecture where the data pipeline handles ingestion and computation, while the dashboard delivers an accessible interface for portfolio monitoring and decision-making.

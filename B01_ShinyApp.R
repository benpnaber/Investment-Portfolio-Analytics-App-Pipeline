# Investment Data Pipeline Shiny App

# Set the python to the environment variable
Sys.setenv(RETICULATE_PYTHON = "set_environment_variable_here")

# Load the libraries
library(tidyverse)
library(shiny)
library(bslib)
library(RSQLite)
library(DBI)
library(waterfalls)
library(dygraphs)
library(treemapify)
library(reticulate)

# Remove all in-memory objects
rm(list = ls())

# Create the connection to the database
conn <- dbConnect(SQLite(), "path_to_your_database_file")

# Read the data from the database 
overview <- dbReadTable(conn, "Portfolio_Overview") %>%
  mutate(Total_Value = as.numeric(Total_Value))
basis <- dbReadTable(conn, "Symbol") 
trans <- dbReadTable(conn, "Transactions")
metrics <- dbReadTable(conn, "Metrics")
sector_weights <- dbReadTable(conn, "Sector_Weights")
asset_classes <- dbReadTable(conn, "Asset_Classes")

# Source the investment functions file here
source_python("A04_Functions.py")
inv_func <- InvestmentFunctions()
date_id <- paste0(month(Sys.Date()) - 1, year(Sys.Date()))

tickers <- inv_func$get_tickers()
primary_sectors <- inv_func$primary_sector()
tickers_in_sector <- primary_sectors %>%
  pull(Primary_Sector) %>%
  sort()

# Make the UI for the shinyapp
ui <- page_navbar(
  title = "Ben's Investment Portfolio Overview",
  id = "navbarID", 
  theme = bs_theme(version = 5, bootswatch = "lux"),
  
  # Make a panel for the read me and basic information about the app
  nav_panel("Readme",
            
            h1("Investment Data Pipeline & Portfolio Dashboard"),
            p("This app is a personal investment tracking system built to give a complete, self-owned view of my portfolio. It takes raw bank and brokerage statements and turns them into structured, queryable data rather than relying on a third-party finance tool. The goal has always been full ownership over ingestion, analysis, and visualization, without depending on an out-of-the-box BI platform. From there, it calculates a wide range of metrics and visualizes everything through this dashboard."),
            p("The backend is a Python data pipeline made up of a few core scripts, each with a distinct role. A parser script reads the original statement data and formats it into a clean, structured form that the rest of the pipeline can work with. An analyzer script then takes that formatted data and calculates portfolio metrics like returns, cost basis, and performance over time. A runner script ties these two together, executing the parser and analyzer in sequence so the database stays current with each new statement."),
            p("A shared functions file supports both the parser and analyzer, and handles the more complex calculations that get reused across the pipeline. This includes things like the Sharpe ratio, which required working through some tricky scalar-versus-DataFrame bugs and proper annualization along the way. It also pulls in outside market data such as S&P 500 returns and the risk-free rate to provide useful benchmarks. On top of that, it computes per-security sector and asset class weights, which power the treemap charts elsewhere in this app."),
            p("All of this output gets written to a single local SQLite database, which acts as the shared data layer between the Python pipeline and this Shiny app. Keeping everything in one file made it simple to query from R using reticulate without duplicating logic across languages. Both the parser and analyzer log their execution using Python's logging module, so it's easy to confirm each run completed successfully. That logging has also made debugging much faster whenever something like a unique constraint or a data type mismatch pops up."),
            p("The rest of this dashboard reads directly from that database to power everything you see, from sector and asset class treemaps to portfolio value over time. A cost basis breakdown highlights which holdings are contributing the most to the portfolio's overall basis. A waterfall chart shows the biggest individual drivers behind overall gains and losses for a given period. Filters throughout also let you explore hypothetical buy and sell scenarios and see how they'd shift the portfolio's overall exposure before making a real trade."),
            
            # Add an action button to run the python data pipeline
            div(style = "border: 2px solid #ddd; border-radius: 10px; padding: 15px; display: inline-block;",
              actionButton(inputId = "runner", label = "Click to run the data pipeline", class = "btn btn-success"
                          )
            )
            
  ),
  
  # Make a panel for all of the charts
  nav_panel("Portfolio At-a-Glance",
    layout_sidebar(sidebar = sidebar(
      
        # Add a header for the filters
        h2("Filters"),
        
        # Add the slider inputs for the number of top and bottom highlighted bars displayed
        sliderInput(inputId = "top_tickers", min = 0, max = 6, value = 3,
                    label = "Highlighted Top Bars"),
        sliderInput(inputId = "bottom_tickers", min = 0, max = 6, value = 3,
                    label = "Highlighted Bottom Bars"),
        
        fillable = TRUE,
        h2("Overview"),
        p("This page provides an at-a-glance overview of the portfolio's current state and historical performance. It summarizes key metrics including total invested capital, unrealized gains and losses, portfolio growth over time, individual security weights, and the primary value drivers behind overall returns.")
      ), 
      
      # Create the 2x2 grid right here 
      uiOutput("dynamic_grid")
    ) 
  ),
  
  # Create another panel for the metrics page
  nav_panel("Metrics Dashboard",
            layout_sidebar(sidebar = sidebar(
              
              # Build out the filters section 
              h2("Filters"),
              radioButtons(inputId = "ticker_sector", label = NULL,
                           choices = c("Ticker", "Sector"), inline = TRUE),
              conditionalPanel(condition = "input.ticker_sector == 'Ticker'",
                               selectInput(inputId = "ticker", label = "Select a Ticker", choices = sort(tickers))),
              conditionalPanel(condition = "input.ticker_sector == 'Sector'",
                               selectInput(inputId = "sector", label = "Select a Sector", choices = tickers_in_sector)),
              helpText("Note: Only sectors where at least one ticker holds a majority allocation are shown"),
              
              # Build out the overview section
              h2("Overview"),
              p("This dashboard provides a detailed view of individual security performance and key portfolio metrics. It includes geometric monthly returns, dividend yields, rolling Sharpe ratios, and historical security values, allowing you to evaluate performance, income generation, and risk-adjusted returns at either the individual ticker or sector level."),
            ),
            uiOutput("metrics_grid")
            )
  ),
  
  # Add another page for the tree map
  nav_panel("Portfolio Sector Weights",
    layout_sidebar(sidebar = sidebar(width = 285,
      
      # Add a header for the filters
      h2("Filters"),
      
      # Add the filters to the sidebar
      radioButtons(inputId = "sell_or_buy", label = NULL, choices = c("Sell", "Buy"), inline = TRUE),
      conditionalPanel(condition = "input.sell_or_buy == 'Sell'",
                      selectInput(inputId = "ticker_to_sell", label = "Selected Ticker to Sell",
                                    choices = sort(tickers)),
                      sliderInput(inputId = "dollar_amount", label = "How much to Sell ($)", value = 0,
                                  min = 0, max = 1)),
      
      conditionalPanel(condition = "input.sell_or_buy == 'Buy'",
                       selectInput(inputId = "ticker_to_buy", label = "Selected Ticker to Buy",
                                   choices = sort(tickers)),
                       sliderInput(inputId = "input_amount", label = "How much to Buy ($)", value = 0,
                                   min = 0, max = 10000)),
      helpText("Note: Non-equity holdings are excluded from sector weight analysis"),
      actionButton(inputId = "recommendation", label = "Best Sell or Buy"),
      
      # Add the overview section to the sidebar
      h2("Overview"),
      p("This treemap displays the weighted sector allocation of the portfolio, where each rectangle represents a sector and its size is proportional to the portfolio's total exposure to that sector across all held ETFs. Sector weights are calculated by blending each ETF's individual sector composition with its share of the total portfolio value.")
                                    ),
    # Add the chart component
    card(card_header("Portfolio Sector Exposure"),
        plotOutput("sector_treemap")),
                )
  ),
  
  # Create another panel for the asset class treemap
  nav_panel("Asset Class Weights",
            layout_sidebar(sidebar = sidebar(
              
              # Add a header for the filters section
              h2("Filters"),
              
              # Add the flters for this chart
              radioButtons(inputId = "asset_sell_buy", label = NULL, choices = c("Sell", "Buy"), inline = TRUE),
              conditionalPanel(condition = "input.asset_sell_buy == 'Sell'",
                               selectInput(inputId = "asset_sell", label = "Select a Ticker to Sell", 
                                           choices = sort(tickers)),
                               sliderInput(inputId = "asset_dollar", label = "How Much to Sell ($)",
                                           value = 0, min = 0, max = 1)),
              
              conditionalPanel(condition = "input.asset_sell_buy == 'Buy'",
                               selectInput(inputId = "asset_buy", label = "Select a Ticker to Buy", 
                                           choices = sort(tickers)),
                               sliderInput(inputId = "asset_dollar_buy", label = "How Much to Buy ($)",
                                           value = 0, min = 0, max = 10000)),
              
              # Now, we are going to add the overview section to this page
              h2("Overview"),
              p("The asset class treemap breaks down portfolio allocation across major investment categories, with each rectangle sized proportionally to its portfolio weight. This makes it easy to spot concentration risk and assess diversification at a glance — without digging into the numbers.")
                                            ),
  
              # Now, we are going to add a card header for the chart
              card(card_header("Asset Class Exposure"),
                               plotOutput("asset_treemap"))
                          ),
            )
) 

# Make the server for the shiny app that we need
server <- function(input, output, session) {
  
  # Write the code which is what the button will run when it is clicked on 
  observeEvent(input$runner, {
    
    # Run the python file that initiates the data pipeline
    py_run_file("Investment_Runner.py")
  })

  # Create the grid we need
  output$dynamic_grid <- renderUI({
    layout_columns(
      col_widths = c(6, 6, 6, 6),
      
      card(card_header("Cost Basis Analysis"),
        plotOutput("costbasis")),
      
      card(card_header("Portfolio Value Over Time"),
        dygraphOutput("dygraph")),
      
      card(card_header("Value Drivers (Waterfall)"),
        plotOutput("waterfall")),
      
      card(card_header("Current Portfolio Weights"),
        plotOutput("weights"))
    )
  })
  
  # ----------COST BASIS PLOT----------
  costbasis_plot <- reactive({
      
    basis_highlight <- basis %>%
      arrange(desc(Updated_Cost_Basis)) %>%
      mutate(Highlight = case_when(row_number() <= input$top_tickers ~ paste("Top", input$top_tickers),
                                     row_number() > n() - input$bottom_tickers ~ paste("Bottom", input$bottom_tickers),
                                     TRUE ~ "Other"))
      
    ggplot(data = basis_highlight) +
      geom_col(aes(x = reorder(Symbol_ID, -Updated_Cost_Basis), y = Updated_Cost_Basis,
        fill = Highlight)) +
      scale_fill_manual(values = setNames(c("darkblue", "darkorange", "grey70"),
        c(paste("Top", input$top_tickers), paste("Bottom", input$bottom_tickers), "Other"))) + 
      scale_y_continuous(labels = scales::dollar, expand = expansion(mult = c(0, 0.1))) +
      labs(x = NULL, y = "Cost Basis") +
      theme_minimal() +
      theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
            legend.position = "none", text = element_text(size = 14))
  })
  
  output$costbasis <- renderPlot({costbasis_plot()})

  # ----------DYGRAPH PORTFOLIO VALUE----------
  dygraph_plot <- reactive({
      
    if (length(month(Sys.Date()) - 1) == 1) {
      pattern = "^\\d{1}"
    } else {
      pattern = "^\\d{2}"
    }
    
    total_val_data <- overview %>%
      group_by(Date_ID) %>%
      summarise(Total_Port_Value = sum(as.numeric(Total_Value))) %>%
      ungroup() %>%
      mutate(Month = str_extract(Date_ID, pattern = pattern)) %>%
      mutate(Year = str_extract(Date_ID, pattern = "\\d{4}$"))
    
    ts <- ts(total_val_data$Total_Port_Value, start = c(2026, 1), frequency = 12)
    
    dygraph(ts) %>%
      dyRangeSelector() %>%
      dyAxis("y", label = "Total Portfolio Value")
  })
  
  output$dygraph <- renderDygraph({dygraph_plot()})

  # ----------WATERFALL CHART----------
  waterfall_plot <- reactive({
      
    waterfall_data <- metrics %>%
      filter(Date_ID == as.integer(paste0(month(Sys.Date()) - 1, year(Sys.Date())))) %>%
      filter(!is.na(Gain_Loss)) %>%
      arrange(desc(Gain_Loss)) %>%
      select(Symbol_ID, Gain_Loss)
    
    waterfall(waterfall_data, values = waterfall_data$Gain_Loss, labels = waterfall_data$Symbol_ID,
      calc_total = TRUE, total_axis_text = "Net G/L", fill_by_sign = TRUE, rect_border = NA) +
      scale_y_continuous(labels = scales::dollar) +
      labs(x = NULL, y = "Gain/Loss") +
      theme_minimal(base_size = 14) +
      theme(panel.grid.minor = element_blank(),
            text = element_text(size = 14))
  })
  
  output$waterfall <- renderPlot({waterfall_plot()})

  # ----------WEIGHTS BAR CHART----------
  weight <- reactive({
    
    weight_data <- overview %>%
      filter(Date_ID == paste(month(Sys.Date()) - 1, year(Sys.Date()), sep = "")) %>%
      group_by(Symbol_ID) %>%
      summarise(Current_Value = sum(as.numeric(Total_Value))) %>%
      ungroup() %>%
      mutate(Total_Port_Value = sum(Current_Value),
             Weight = Current_Value / Total_Port_Value) %>%
      arrange(desc(Weight)) %>%
      mutate(Highlight = case_when(row_number() <= input$top_tickers ~ paste("Top", input$top_tickers),
        row_number() > n() - input$bottom_tickers ~ paste("Bottom", input$bottom_tickers),
        TRUE ~ "Other"
      ))
    
    ggplot(data = weight_data) +
      geom_col(aes(x = reorder(Symbol_ID, -Weight), y = Weight, fill = Highlight)) +
      geom_text(aes(x = reorder(Symbol_ID, -Weight), y = Weight, 
                    label = round(Weight * 100, 2)), vjust = -0.5, size = 4.5) +
      scale_fill_manual(values = setNames(c("#5a189a", "#2ca25f", "grey70"),
        c(paste("Top", input$top_tickers), paste("Bottom", input$bottom_tickers), "Other"))) + 
      scale_y_continuous(labels = scales::percent) +
      labs(x = NULL, y = "Portfolio Weight") +
      theme_minimal(base_size = 14) +
      theme(legend.position = "none", text = element_text(size = 16),
            panel.grid.minor = element_blank(), panel.grid.major.x = element_blank())
  })
  
  output$weights <- renderPlot({weight()})
  
  # ----------SECTOR WEIGHTS TREEMAP----------
  current_overview <- overview %>%
    filter(Date_ID == date_id)
  
  hypothetical_overview <- reactiveVal(current_overview)
  
  observe({
    req(input$sell_or_buy)
    updated <- current_overview  # always start fresh from real data
    
    if (input$sell_or_buy == "Sell") {
      req(input$ticker_to_sell)
      updated[updated$Symbol_ID == input$ticker_to_sell, "Total_Value"] <-
        as.numeric(updated[updated$Symbol_ID == input$ticker_to_sell, "Total_Value"]) - input$dollar_amount
      
    } else {
      req(input$ticker_to_buy)
      updated[updated$Symbol_ID == input$ticker_to_buy, "Total_Value"] <-
        as.numeric(updated[updated$Symbol_ID == input$ticker_to_buy, "Total_Value"]) + input$input_amount
    }
    
    hypothetical_overview(updated)
  })
  
  output$sector_treemap <- renderPlot({
    
    # Make the hypothetical overview object required
    req(hypothetical_overview())
    
    # Call the python function to get the updated weights
    hypo_weights <- inv_func$get_portfolio_sector_weights(hypothetical_overview(), sector_weights)
    
    # Alter the names of the sectors in the column
    hypo_weights <- hypo_weights %>%
      mutate(Sector = recode(Sector,
                             "technology" = "Technology", "basic_materials" = "Basic Materials",
                             "communication_services" = "Communication Services", "consumer_cyclical" = "Consumer Cyclical",
                             "consumer_defensive" = "Consumer Defensive", "energy" = "Energy",
                             "financial_services" = "Financial Services", "healthcare" = "Healthcare",
                             "industrials" = "Industrials", "realestate" = "Real Estate",
                             "utilities" = "Utilities")) %>%
      mutate(Text_Color = ifelse(Weight < median(Weight), "white", "black"))
    
    # Make the tree map of the sector weights
    ggplot(data = hypo_weights %>% arrange(desc(Weight))) +
    geom_treemap(aes(area = Weight, fill = Sector)) +
    geom_treemap_text(aes(area = Weight, label = paste0(Sector, "\n", round(Weight * 100, 1), "%"), 
                        colour = Text_Color), fontface = "bold") +
    scale_colour_identity() + 
    scale_fill_viridis_d(option = "mako") +
    theme(legend.position = "none")
  })
  
  # Add a way to dynamically change the amounts for buy and sell
  observe({
    
    # Require the input selected symbol for this code to run
    req(input$ticker_to_sell)
    
    # Filter the data down to the symbol
    latest_value <- overview %>%
      filter(Symbol_ID == input$ticker_to_sell) %>%
      arrange(desc(Date_ID)) %>%
      slice(1) %>%
      pull(Total_Value)
    
    # Update the numeric input value based on the max 
    updateSliderInput(session, "dollar_amount", max = latest_value)
  })
  
  # Add what the action button does by calling the function
  recommendation_result <- reactiveVal(NULL)
  
  # Run the observe event function which calls the function
  observeEvent(input$recommendation, {
    tryCatch({
      
      hypo_weights <- inv_func$get_portfolio_sector_weights(hypothetical_overview(), sector_weights)
      result <- inv_func$best_buy_sell(hypo_weights, sector_weights, tickers)
      
      showModal(modalDialog(
        title = "Recommended Trade",
        paste("Best ETF to Sell:", result$Best_Sell),
        br(),
        paste("Best ETF to Buy:", result$Best_Buy),
        easyClose = TRUE
      ))
      
    }, error = function(e) {
      showModal(modalDialog(title = "Error", conditionMessage(e), easyClose = TRUE))
    })
  })
  
  # ----------ASSET CLASS TREEMAP----------
  asset_overview <- reactiveVal(current_overview) # FILTERED VARIABLE USED ABOVE
  
  observe({
    req(input$asset_sell_buy)
    asset_updated <- current_overview
    
    if (input$asset_sell_buy == "Sell") {
      asset_updated[asset_updated$Symbol_ID == input$asset_sell, "Total_Value"] <-
        as.numeric(asset_updated[asset_updated$Symbol_ID == input$asset_sell, "Total_Value"]) - input$asset_dollar
      
    } else {
        asset_updated[asset_updated$Symbol_ID == input$asset_buy, "Total_Value"] <-
        as.numeric(asset_updated[asset_updated$Symbol_ID == input$asset_buy, "Total_Value"]) + input$asset_dollar_buy
    }
    
    asset_overview(asset_updated)
  })
  
  output$asset_treemap <- renderPlot({
    
    # Make the asset overview required
    req(asset_overview())
    
    # Get the hypothetical asset class weights
    hypo_classes <- inv_func$get_portfolio_class_weights(asset_overview(), asset_classes)
    
    # We need to rename the names of the sectors
    hypo_classes <- hypo_classes %>%
      mutate(Asset_Class = recode(Asset_Class, "Cash_Weight" = "Cash Weight", "Stock_Weight" = "Stock Weight",
                                  "Bond_Weight" = "Bond Weight", "Preferred_Weight" = "Preferred Weight",
                                  "Convertible_Weight" = "Convertible Weight", "Other_Weight" = "Other Weight")) %>%
      mutate(Text_Color = ifelse(Weight < mean(Weight), "white", "black"))
    
    # Make the treemap itself
    ggplot(data = hypo_classes %>% arrange(desc(Weight))) +
      geom_treemap(aes(area = Weight, fill = Asset_Class)) +
      geom_treemap_text(aes(area = Weight, label = paste0(Asset_Class, "\n", round(Weight * 100, 1), "%"),
                        colour = Text_Color), fontface = "bold") +
      scale_colour_identity() +
      scale_fill_viridis_d(option = "magma") +
      theme(legend.position = "none")
  })
  
  # Add a way to dynamically change the amounts for buy and sell
  observe({
    
    # Require the input selected symbol for this code to run
    req(input$asset_sell)
    
    # Filter the data down to the symbol
    latest_value <- overview %>%
      filter(Symbol_ID == input$asset_sell) %>%
      arrange(desc(Date_ID)) %>%
      slice(1) %>%
      pull(Total_Value)
    
    # Update the numeric input value based on the max 
    updateSliderInput(session, "asset_dollar", max = latest_value)
  })
  
  # ----------METRICS DASHBOARD----------
  output$metrics_grid <- renderUI({
    layout_columns(
      col_widths = c(6, 6, 6, 6),
      
      card(card_header("Portfolio Monthly Returns"),
           plotOutput("monthlyreturn")),
      
      card(card_header("Security Value Over Time"),
           plotOutput("dividendyield")),
      
      card(card_header("Portfolio Dividend Yield"),
           plotOutput("divyield")),
      
      card(card_header("Rolling Sharpe Ratio"),
           plotOutput("sharperatio"))
    
    )
  })
  
  # Obtain the filtered value and ticker / sector
  ticker_or_sector <- reactive({
    
    # Write if statements to evaluate what we are going to display
    if (input$ticker_sector == "Ticker") {
      overview_filtered <- overview %>%
        filter(Symbol_ID == input$ticker)
      
    } else if (input$ticker_sector == "Sector") {
      new_primary_sectors <- primary_sectors %>%
        filter(Primary_Sector == input$sector)
      
      overview_filtered <- overview %>%
        filter(Symbol_ID %in% new_primary_sectors$Symbol_ID)
    } 
  })
  
  # Make the monthly returns plot
  mreturn <- reactive({
    
    # Write an if statement to evaluate what to display
    if (input$ticker_sector == "Sector") { 
      filtered <- ticker_or_sector()
      req(filtered) # Provides a guard against NULL 
    
      # Format the data
      returns <- inv_func$geometric_mean() %>%
        filter(Symbol_ID %in% filtered$Symbol_ID) %>%
        mutate(Symbol_ID = fct_reorder(Symbol_ID, Geo_Mean_Return, .desc = TRUE)) %>%
        filter(abs(Geo_Mean_Return) > 0.0001)
    
      } else {
      returns <- inv_func$geometric_mean() %>%
        mutate(Symbol_ID = fct_reorder(Symbol_ID, Geo_Mean_Return, .desc = TRUE)) %>%
        filter(abs(Geo_Mean_Return) > 0.0001)
    }
    
    # Build the chart
    ggplot(data = returns) + 
      geom_col(aes(x = Symbol_ID, y = Geo_Mean_Return, fill = Geo_Mean_Return)) +
      scale_y_continuous(labels = scales::percent) + 
      scale_fill_gradient2(low = "grey70", mid = "grey90", high = "#2ca25f", midpoint = 0, guide = "none") + 
      labs(x = NULL, y = "Geometric Return") +
      theme_minimal() + 
      theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
            text = element_text(size = 14))
  })
  
  output$monthlyreturn <- renderPlot({mreturn()})
  
  # Make the chart for the security values over time 
  ticker_value <- reactive({
    
      # Build the ggplot object
      ggplot(data = ticker_or_sector()) + 
        geom_line(aes(x = Date_ID, y = Total_Value, group = Symbol_ID,
                      color = Symbol_ID)) +
        labs(x = NULL, y = "Total Value") + 
        theme_minimal() + 
        theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
              text = element_text(size = 14), legend.position = "bottom", legend.title = element_blank())
  })
  
  output$dividendyield <- renderPlot({ticker_value()})
  
  # Build the final plot of the app for the dividend yield
  div_yield <- reactive({
    
    # We are going to do some data formatting 
    metrics_filtered <- metrics %>%
      filter(Date_ID == date_id)
    
    # Build the ggplot object
    ggplot(data = metrics_filtered, aes(x = reorder(Symbol_ID, Dividend_Yield), y = Dividend_Yield)) +
      geom_segment(aes(xend = Symbol_ID, y = 0, yend = Dividend_Yield), color = "grey60", linewidth = 0.8) +
      geom_point(color = "darkblue", size = 3) +
      labs(x = NULL, y = "Dividend Yield") +
      theme_minimal() +
      theme(panel.grid.minor = element_blank(), panel.grid.major.y = element_blank(),
            text = element_text(size = 14))
  })
  
  output$divyield <- renderPlot({div_yield()})
  
  # Build a plot for the sharpe ratio
  sharpe_ratio <- reactive({
    
    # Write an if statement to evaluate how we are going to filter the data
    if (input$ticker_sector == "Sector") { 
      filtered <- ticker_or_sector()
      req(filtered) # Provides a safeguard 
      
      # Format the data
      metrics_filtered <- metrics %>%
        filter(Symbol_ID %in% filtered$Symbol_ID) %>%
        filter(Date_ID == date_id)
      
    } else {
      metrics_filtered <- metrics %>%
        filter(Date_ID == date_id)
    }
    
    # Build the ggplot object
    ggplot(data = metrics_filtered) + 
      geom_col(aes(x = reorder(Symbol_ID, -Sharpe_Ratio), y = Sharpe_Ratio, fill = Sharpe_Ratio)) +
      scale_fill_gradient2(low = "grey70", mid = "grey90", high = "darkblue", midpoint = 0, guide = "none") + 
      labs(x = NULL, y = "Sharpe Ratio") +
      theme_minimal() +
      theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
            text = element_text(size = 14))
  })
  
  output$sharperatio <- renderPlot({sharpe_ratio()})
}

shinyApp(ui, server)
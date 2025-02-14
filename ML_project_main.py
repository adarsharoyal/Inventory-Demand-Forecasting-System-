import streamlit as st
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.callbacks import EarlyStopping
from keras.models import Sequential
from keras.layers import LSTM, Dense
import plotly.graph_objects as go
import plotly.figure_factory as ff
import plotly.express as px
import sqlite3
import hashlib
import time
import chardet
import warnings
warnings.filterwarnings("ignore")

# This must be the first command in your app, and must be set only once
st.set_page_config(page_title="ML Project" , layout="wide", page_icon = "icon2.png", initial_sidebar_state="expanded")

#Helper function to create a connection to SQLite
def get_connection():
    conn = sqlite3.connect('users_data.db')   # This will create the database file
    return conn

# Helper function to create a users table
def create_users_table():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        email TEXT UNIQUE,
                        password TEXT
                    );''')
    conn.commit()
    conn.close()

# Helper function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()   

# Save a new user's details into the database
def save_user_to_db(username, email, password):
    conn = get_connection()
    hashed_password = hash_password(password)

    # Only insert username and email if provided
    if username:
        conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_password))
    else:
        conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (None, email, hashed_password))

    conn.commit()
    conn.close()

# Check if a user exists in the database
def is_user_exists(username=None, email=None):
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
    user = cursor.fetchone()
    conn.close()
    return user is not None

# Validate login credentials
def validate_login(username_or_email, password):
    conn = get_connection()
    hashed_password = hash_password(password)
    cursor = conn.execute(
        "SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?",
        (username_or_email, username_or_email, hashed_password)
    )
    user = cursor.fetchone()
    conn.close()
    return user

def migrate_users_table():
    conn = get_connection()
    
    # Step 1: Create a new temporary table with the desired schema
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users_temp (
            username TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT
        );
    ''')
    
    # Step 2: Copy data from the old table to the new table, leaving email as NULL for old entries
    conn.execute('''
        INSERT INTO users_temp (username, password)
        SELECT username, password FROM users;
    ''')
    
    conn.commit()
    
    # Step 3: Drop the old table and rename the new table
    conn.execute("DROP TABLE users;")
    conn.execute("ALTER TABLE users_temp RENAME TO users;")
    
    conn.commit()
    conn.close()

# Update the user's password in the database
def update_user_password(identifier, new_password, by_email=False):
    conn = get_connection()
    hashed_password = hash_password(new_password)
    if by_email:
        conn.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, identifier))
    else:
        conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_password, identifier))
    conn.commit()
    conn.close()

# Call the function to ensure the users table is created before any operations
migrate_users_table()
create_users_table()

# Session state for login management
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "signed_up" not in st.session_state:
    st.session_state.signed_up = False
if "show_data" not in st.session_state:
    st.session_state.show_data = False
if "reset_password" not in st.session_state:
    st.session_state.reset_password = False

st.markdown("""
    <style>
        /* Light Mode */
        :root {
            --background-color: #00FFFFFF;
            --text-color: #000000;
            --input-background-color: #e8f0fe;
            --button-color: #4CAF50;
        }

        /* Dark Mode */
        @media (prefers-color-scheme: dark) {
            :root {
                --background-color: #121212;
                --text-color: #EAEAEA;
                --input-background-color: #1A1A1A;
                --button-color: #FF3E3E;
            }
        }
        /* Style for the tabs */
        div[role="tab"] {
            font-weight: bold;
        }
        div[data-baseweb="tab"] {
            font-size: 1.2em; /* Adjust the font size */
            width: 20%; /* To adjust the width, 20percent for five evenly spaced tabs */
            font-weight: bold;
        }
        div[data-baseweb="tab-list"] {
            display: flex;
            justify-content: space-around; /* Evenly distribute tabs */
        }
        div[data-baseweb="tab"] > button {
            font-weight: bold; /* Make text bold */
            color: #1E90FF; /* Change tab text color if desired */
        }
        div[role="tab"][aria-selected="true"] {
            color: #1E90FF;
            border-bottom: 2px solid #ff4b4b;
        }
        div[role="tab"][aria-selected="false"] {
            color: #808080;
        }
        .streamlit-expanderHeader {
            background-color: #1E90FF;  /* Bright Blue */
            color: white;
        }

        /* Apply styles */
        .main { background-color: var(--background-color) !important; }
        .stTextInput input { background-color: var(--input-background-color) !important; color: var(--text-color) !important; }
        .stButton button { background-color: var(--button-color) !important; color: #FFFFFF; }
        .stForm .stFormHeader p { color: var(--text-color) !important; }
    </style>
""", unsafe_allow_html=True)

def signup_page():
    st.title("Sign Up")

    # Dropdown selection for sign-up method
    signup_option = st.selectbox("Choose your sign-up method", ["Username and Password", "Email and Password"])

    with st.form(key='signup_form'):
        username = ""
        email = ""

        # Display fields based on the selected sign-up method
        if signup_option == "Username and Password":
            username = st.text_input("Enter a username", "")
        elif signup_option == "Email and Password":
            email = st.text_input("Enter your email address", "")

        password = st.text_input("Enter a password", type='password')
        signup_button = st.form_submit_button("Sign Up")

        # Sign-up logic based on chosen method
        if signup_button:
            if signup_option == "Username and Password" and username and password:
                if is_user_exists(username=username):
                    st.error("Username already exists. Please log in or choose a different username.")
                else:
                    save_user_to_db(username, None, password)  # Pass username and None for email
                    st.session_state.signed_up = False
                    st.session_state.logged_in = False
                    st.success("Account created! Redirecting to login...")
                    time.sleep(1)
                    st.rerun()

            elif signup_option == "Email and Password" and email and password:
                if is_user_exists(email=email):
                    st.error("Email already exists. Please log in or use a different email.")
                else:
                    save_user_to_db(None, email, password)  # Pass None for username and email
                    st.session_state.signed_up = False
                    st.session_state.logged_in = False
                    st.success("Account created! Redirecting to login...")
                    time.sleep(1)
                    st.rerun()
            
            else:
                st.error("Please fill in the required fields and select one sign-up option.")

    st.markdown("<div style='text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)
    st.write("Already have an account?")
    if st.button("Go to Login"):
        st.session_state.signed_up = False  # Toggle the signup page state
        st.rerun()

def reset_password_page():
    st.title("Reset Password")
    st.write("Reset your password using either your Username or Email.")

    with st.form(key='reset_form'):
        username = st.text_input("Enter your username (optional)")
        email = st.text_input("Enter your email address (optional)")
        new_password = st.text_input("Enter a new password", type='password')
        confirm_password = st.text_input("Confirm new password", type='password')
        reset_button = st.form_submit_button("Reset Password")

        if reset_button:
            user_exists = is_user_exists(username, email)
            if not is_user_exists(username, email):
                st.error("No account found with the provided username or email.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                identifier = username if username else email
                update_user_password(identifier, new_password)
                st.success("Password has been reset! Redirecting to login...")
                time.sleep(1)
                st.session_state.reset_password = False
                st.rerun()

    st.markdown("<div style='text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)
    st.write("Remembered your password?")
    if st.button("Go to Login"):
        st.session_state.reset_password = False
        st.rerun()

def login_page():
    st.title("Login")
    # Using form to help browsers detect login actions
    with st.form(key='login_form'):
        username_or_email = st.text_input("Username or Email")
        password = st.text_input("Password", type='password')
        login_button = st.form_submit_button("Login")

        if login_button:
            user = validate_login(username_or_email, password)
            if user:
                st.session_state.logged_in = True
                st.success("Login successful!")
                time.sleep(1)
                st.rerun()  # Force re-render to move to the main app
            else:
                st.error("Incorrect username, email or password.")

    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    with col1:
        st.markdown("<div style='text-align: center; margin-top: 30px;'>", unsafe_allow_html=True)
        st.write("Don't have an account?")
        if st.button("Go to Sign Up"):
            st.session_state.signed_up = True  # Toggle the signup page state
            st.rerun() 

    with col4:
        st.markdown("<div style='text-align: center; margin-top: 30px;'>", unsafe_allow_html=True)
        st.write("Forgot your password?")
        if st.button("Reset Password"):
            st.session_state.reset_password = True
            st.rerun()
       

def toggle_data_visibility():
    st.session_state.show_data = not st.session_state.show_data

def is_date_column(column):
    try:
        pd.to_datetime(column)
        return True
    except (ValueError, TypeError):
        return False

# Main app function
def app():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = True 

    st.image(r"logo2.png", width=100)
    st.header("Welcome to the Web Application")
    st.image(r"banner3.jpeg", use_column_width=True)
    st.title("Demand Forecasting & Inventory Optimization📈")

    
    # 2. Provide a default dataset (Holidays)
    st.subheader("Default Datasets (provided by developer)")
    data = {
        'Date': [
            '2024-01-01', '2024-01-13', '2024-01-13', '2024-04-26', 
            '2024-03-08', '2024-04-02', '2024-04-10', '2024-04-17', 
            '2024-05-03', '2024-07-13', '2024-07-17', '2024-08-19', 
            '2024-09-07', '2024-09-08', '2024-10-12', '2024-10-02', 
            '2024-10-31', '2024-11-15', '2024-12-25', '2024-08-15'
        ],
        'Holiday Name': [
        'New Year', 'Lohri', 'Makar Sankranti', 'Republic Day', 
        'Shivratri', 'Ugadi', 'Rama Navami', 'Good Friday', 
        'Ramzan Id/Eid-ul-Fitar', 'Bakr Id/Eid ul-Adha', 'Muharram', 
        'Janmashtami', 'Ganesh Chaturthi', 'Onam', 
        'Mahatma Gandhi Jayanti', 'Navratri', 
        'Diwali', 'Guru Nanak Jayanti', 'Christmas', 
        'Independence Day'
        ],
        'Holiday Impact': [
        'High', 'Medium', 'Low', 'High', 
        'Low', 'Medium', 'Low', 'High', 
        'Low', 'Medium', 'Low', 'High', 
        'High', 'Low', 'High', 'Medium', 
        'Low', 'High', 'Medium', 'Low'
        ],
        'Weather Condition': [
        'Fog', 'Sunny', 'Humid', 'Cloudy', 
        'Sunny', 'Partly Cloudy', 'Clear', 'Clear', 
        'Sunny', 'Sunny', 'Fog', 'Cloudy', 
        'Sunny', 'Sunny', 'Fog', 'Cloudy', 
        'Clear', 'Sunny', 'Sunny', 'Sunny'
        ],
        'Temperature (°C)': [
        17, 25, 23, 19, 
        27, 22, 30, 29, 
        21, 31, 25, 24, 
        28, 29, 22, 21, 
        30, 28, 25, 26
        ],
        'Weather Impact': [
        'Medium', 'Low', 'Medium', 'Low', 
        'Low', 'Low', 'Medium', 'Low', 
        'High', 'Low', 'Medium', 'Medium', 
        'Low', 'Medium', 'Low', 'Medium', 
        'Low', 'Medium', 'Low', 'Medium'
        ],
        'Promotion Name': [
        'Winter Sale', 'No Promotion', 'No Promotion', 'Republic Day Offer', 
        'No Promotion', 'Holi Festival Discount', 'No Promotion', 'No Promotion', 
        'Eid Celebration Discount', 'Independence Day Sale', 'No Promotion', 
        'No Promotion', 'Ganesh Chaturthi Promo', 'No Promotion', 
        'Onam Special Offer', 'No Promotion', 'Navratri Special', 
        'Diwali Discount', 'No Promotion', 'Christmas Bonanza'
        ],
        'Discount Percentage (%)': [
        10, 0, 0, 15, 
        0, 30, 0, 0, 
        35, 40, 0, 0, 
        25, 0, 40, 25, 
        50, 0, 50, 0
        ],
        'Promotion Impact': [
        'Medium', 'None', 'None', 'Medium', 
        'None', 'Medium', 'None', 'None', 
        'High', 'High', 'None', 
        'None', 'High', 'None', 
        'Medium', 'Medium', 'Very High', 
        'None', 'Very High', 'None'
        ],
        'Economical Indicator': [
            'High',    # New Year
            'Medium',  # Lohri
            'Low',     # Makar Sankranti
            'High',    # Republic Day
            'Low',     # Shivratri
            'Medium',  # Ugadi
            'Low',     # Rama Navami
            'High',    # Good Friday
            'High',    # Eid-ul-Fitr
            'Medium',  # Bakr Id
            'Low',     # Muharram
            'Medium',  # Janmashtami
            'High',    # Ganesh Chaturthi
            'Medium',  # Onam
            'Low',     # Mahatma Gandhi Jayanti
            'Medium',  # Navratri
            'High',    # Diwali
            'Medium',  # Guru Nanak Jayanti
            'High',    # Christmas
            'High'    # Independence Day
        ]
    }
    external_factors_df = pd.DataFrame(data)
    external_factors_df['Date'] = pd.to_datetime(external_factors_df['Date'])

    customer_data = {
    'Customer ID': [1, 2, 3, 4, 5],
    'Customer Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eva'],
    'Age': [28, 34, 22, 45, 30],
    'Gender': ['Female', 'Male', 'Male', 'Male', 'Female'],
    'Location': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'],
    'Purchase History': ['Electronics', 'Clothing', 'Books', 'Grocery', 'Sports'],
    'Preferred Holidays': [
        'New Year', 'Christmas', 'Diwali', 
        'Independence Day', 'Lohri'
    ],
    'Spending Habit': ['Medium', 'High', 'Low', 'Medium', 'High']
    }
    customer_info_df = pd.DataFrame(customer_data)

    button_label = "Hide datasets" if st.session_state.show_data else "Show datasets"

    if st.button("Show datasets" if not st.session_state.show_data else "Hide datasets", on_click=toggle_data_visibility):
        pass
    st.markdown("&nbsp;"*5, unsafe_allow_html=True)

    if st.session_state.show_data:
        col1, col2 = st.columns(2)
    
        with col1:
            st.write("### External Factors Dataset")
            st.dataframe(external_factors_df)

        with col2:
            st.write("### Customer Info Dataset")
            st.write("Edit the Customer Info dataset as needed and use it for predictions.")
            edited_customer_info_df = st.data_editor(customer_info_df, 
                                           num_rows="dynamic", 
                                           use_container_width=True)

        st.markdown("<br>" * 2, unsafe_allow_html=True)
    
    # User-side data upload (shopkeepers, retailers, etc.)
    st.subheader("Upload Sales Data (Max 5 CSV/XLSX files)")
    uploaded_files = st.file_uploader("Upload datasets (CSV/XLSX)", type=["csv", "xlsx"], accept_multiple_files=True)
    st.markdown("<p style='font-family: Arial; font-size: 18px; color: tomato; text-align: center'>[NOTE]: The  uploaded  dataset/s  must  contain  'Sales  related column'  and  'Date  related  column'</p>", unsafe_allow_html=True)
    
    if uploaded_files:
        if len(uploaded_files) > 5:
            st.error("You can upload a maximum of 5 files only.")
        else:
            datasets = {}
            total_size = 0
            for uploaded_file in uploaded_files:
                if uploaded_file.size > 0:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            raw_data = uploaded_file.read(10000)
                            encoding = chardet.detect(raw_data)['encoding']
                            uploaded_file.seek(0)  # Reset file pointer
                            total_size += uploaded_file.size
                            datasets[uploaded_file.name] = pd.read_csv(uploaded_file)
                        elif uploaded_file.name.endswith('.xlsx'):
                            datasets[uploaded_file.name] = pd.read_excel(uploaded_file)
                    except pd.errors.EmptyDataError:
                        st.error(f"{uploaded_file.name} is empty or has no columns to parse.")
                    except UnicodeDecodeError:
                        st.warning(f"Failed to read {uploaded_file.name} with default encoding. Trying with ISO-8859-1.")
                        datasets[uploaded_file.name] = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
                    except Exception as e:
                        st.error(f"Error loading {uploaded_file.name}: {e}")
                else:
                    st.error(f"{uploaded_file.name} is an empty file.")                   

            # Displaying data preview
            for name, data in datasets.items():
                st.write(f"**{name}**")
                st.write("Here is a preview of your dataset:")
                st.write(data.head())

            # Evaluate data size
            total_size = sum([df.memory_usage().sum() for df in datasets.values()])
            st.write(f"**Total size of data: {total_size / (1024 ** 2):.2f} MB**")

            # Handle session state for evaluation and model selection
            if "evaluated" not in st.session_state:
                st.session_state.evaluated = False
            
            # Provide an evaluation button
            evaluate_button = st.button("Evaluate Data")
            st.markdown("<br>" * 1, unsafe_allow_html=True)

            if evaluate_button or st.session_state.evaluated:
                st.session_state.evaluated = True
                st.write("Performing Inventory Optimization and Sales Prediction...")  

                tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dataset 1", "Dataset 2", "Dataset 3", "Dataset 4", "Dataset 5"])
                datasets_list = list(datasets.items())
                for index, (name, dataset) in enumerate(datasets_list):
                    current_tab = tab1 if index == 0 else tab2 if index == 1 else tab3 if index == 2 else tab4 if index == 3 else tab5
                    
                    with current_tab:
                        st.markdown("<br>" * 1, unsafe_allow_html=True)
                        # Inventory Optimization
                        st.subheader("Inventory Optimization")
                        safety_stock_level = st.slider("Select Safety Stock Level", min_value=100, max_value=1000, value=300, key=f"safety_stock_{name}")
                        lead_time = 7
                        possible_sales_columns = [
                            # General Sales and Quantity Terms
                            'Sales', 'sales', 'SalesQuantity', 'salesquantity', 'QuantitySold', 'quantitysold', 'ProjectedSales', 'projected_sales',
                            'TotalSales', 'totalsales', 'TotalQuantity', 'totalquantity', 'Quantity', 'quantity', 'ExpectedSales', 'expected_sales', 'HistoricalSales', 'historical_sales',

                            # Sales Revenue and Units Sold Terms
                            'Revenue', 'revenue', 'SalesRevenue', 'salesrevenue', 'GrossSales', 'grosssales', 'NetSales', 'netsales',
                            'UnitsSold', 'unitssold', 'ItemsSold', 'itemssold', 'VolumeSold', 'volumesold',
                            
                            # Demand Forecast Terms
                            'DemandForecast', 'demandforecast', 'SalesForecast', 'salesforecast', 'ForecastQuantity', 'forecastquantity',
                            'ForecastSales', 'forecastsales', 'PredictedSales', 'predictedsales', 'ProjectedDemand', 'projecteddemand',
                            'ExpectedDemand', 'expecteddemand', 'FutureDemand', 'futuredemand', 'ForecastedDemand', 'forecasted_demand',

                            # Supply Chain and Order Terms
                            'OrderQuantity', 'orderquantity', 'ReorderQuantity', 'reorder_quantity', 'Backorder', 'backorder', 'OnOrder', 'onorder', 'PendingOrders', 'pendingorders',
                            'ReplenishmentQuantity', 'replenishmentquantity', 'FulfilledOrders', 'fulfilledorders', 'ShippedQuantity', 'shippedquantity',
                            'OrderFulfillment', 'orderfulfillment', 'StockQuantity', 'stockquantity', 'PurchaseQuantity', 'purchase_quantity',

                            # Specific Business Terms
                            'RetailSales', 'retailsales', 'WholesaleSales', 'wholesalesales', 'DistributorSales', 'distributorsales',
                            'DealerSales', 'dealersales', 'ShopkeeperSales', 'shopkeepersales', 'ManufacturerSales', 'manufacturersales',
    
                            # Other Possible Terms Related to Inventory and Demand
                            'Dollars', 'dollars', 'Profit', 'profit', 'Rupees', 'rupees', 'Amount', 'amount', 'Demand', 'demand', 'DemandQuantity', 'demandquantity', 'Supply', 'supply', 'SalesVolume', 'salesvolume', 'MarketDemand', 'marketdemand',
                            'SeasonalDemand', 'seasonaldemand', 'CustomerOrders', 'customerorders', 'OrderVolume', 'ordervolume',
                            'OrderDemand', 'orderdemand', 'SalesTarget', 'salestarget', 'SalesVolume', 'salesvolume', 'InventoryLevel', 'inventory_level', 'StockLevel', 'stock_level', 'Backlog', 'backlog',                 
                        ]
                        sales_column = next((col for col in possible_sales_columns if col in dataset.columns), None)

                        if sales_column:
                            dataset.rename(columns={sales_column: 'Sales'}, inplace=True)
                            dataset['Reorder Level'] = np.where(dataset['Sales'] < safety_stock_level, "Reorder", "Sufficient")
            
                            st.write(f"Reorder Level for {name}:")
                            st.write(dataset[['Sales', 'Reorder Level']].head())
            
                            # Inventory Optimization Models (Before Date Processing)
                            st.write(f"Safety Stock Level selected: {safety_stock_level}")

                            selectbox_key = f"selectbox_model_{name}"
                            selected_model = st.selectbox("Select Model for Inventory Optimization", options=["Random Forest", "ARIMA"], index=0, key=selectbox_key)
                            if selected_model == "Random Forest":
                                if 'Sales' in dataset.columns:
                                    X = dataset.index.to_frame(name='Day')  # Use index as feature for simple prediction
                                    y = dataset['Sales']
                                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                    
                                    # Random Forest Model
                                    rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
                                    rf_model.fit(X_train, y_train)
                    
                                    # Predict over lead time to estimate Reorder Point
                                    lead_time_sales_rf = rf_model.predict([[i] for i in range(1, lead_time + 1)])
                                    avg_forecast_rf = lead_time_sales_rf.mean()
                                    safety_stock_rf = 1.65 * (dataset['Sales'].std() * np.sqrt(lead_time))
                                    reorder_point_rf = avg_forecast_rf + safety_stock_rf

                                    st.subheader(f"Random Forest Recommended Reorder Point for {name}")
                                    st.write("Random Forest Safety Stock Level:", safety_stock_rf)
                                    st.write("Random Forest Reorder Point:", reorder_point_rf)
                    
                            elif selected_model == "ARIMA":
                                try:
                                    arima_model = ARIMA(dataset['Sales'], order=(5, 1, 0))  # Adjust (p, d, q) as needed
                                    arima_results = arima_model.fit()
                    
                                    # Calculate Safety Stock for lead time with ARIMA forecast variability
                                    forecast_arima = arima_results.forecast(steps=lead_time)
                                    avg_forecast = forecast_arima.mean()
                                    safety_stock_arima = 1.65 * (forecast_arima.std() * np.sqrt(lead_time))
                                    reorder_point_arima = avg_forecast + safety_stock_arima

                                    st.subheader(f"ARIMA Recommended Safety Stock Level for {name}")
                                    st.write("ARIMA Safety Stock Level:", safety_stock_arima)
                                    st.write("ARIMA Reorder Point:", reorder_point_arima)               
                                except Exception as e:
                                    st.warning("ARIMA model encountered an issue.")
                                    st.error(e)
        
                        else:
                            st.warning(f"Sales column not found in the dataset {name}. Please upload a dataset that contains sales column.")
                            
                        st.markdown("<br>", unsafe_allow_html=True)    
                        # Ensure dataset has been loaded
                        if len(datasets) > 0:
                            possible_date_columns = [
                            'date', 'datetime', 'timestamp', 'time', 
                            'order date', 'Order Date', 'Order_Date', 
                            'purchasedate', 'PurchaseDate', 'purchase date', 'Purchase Date', 
                            'sale date', 'Sale Date', 
                            'transaction date', 'Transaction Date', 
                            'ship date', 'Ship Date', 
                            'invoice date', 'Invoice Date',
                            'paydate', 'PayDate', 'pay date', 'Pay Date', 
                            'payment date', 'Payment Date', 
                            'dispatch date', 'Dispatch Date', 
                            'delivery date', 'Delivery Date', 
                            'saledate', 'SaleDate', 'sale date', 'Sale Date', 
                            'date of sale', 'Date Of Sale', 
                            'sold date', 'Sold Date', 
                            'event date', 'Event Date', 
                            'start date', 'Start Date', 
                            'end date', 'End Date', 
                            'close date', 'Close Date',
                            'salesdate', 'SalesDate' 
                            'registration date', 'Registration Date', 
                            'signup date', 'Signup Date', 
                            'login date', 'Login Date', 
                            'last purchase date', 'Last Purchase Date', 
                            'last login date', 'Last Login Date', 
                            'fiscal year', 'Fiscal Year', 
                            'reporting date', 'Reporting Date', 
                            'report date', 'Report Date', 
                            'due date', 'Due Date', 
                            'last updated', 'Last Updated', 
                            'expiry date', 'Expiry Date', 
                            'effective date', 'Effective Date', 
                            'date of birth', 'Date of Birth'
                            ]
                            normalized_possible_dates = [col.lower().replace(' ', '_') for col in possible_date_columns]

                            # Check if a column related to Date exists
                            date_column = None
                            for col in dataset.columns:
                                normalized_col = col.lower().replace(' ', '_')
                                if normalized_col in normalized_possible_dates:
                                    date_column = col  # Store the actual column name from the dataset
                                    break 
                        
                            if date_column is None:
                                st.error(f"No Date-related column found in the {name} dataset. Upload valid dataset.")
                                continue
                            else:                                # Convert the identified date column to datetime format with dayfirst=True
                                dataset[date_column] = pd.to_datetime(dataset[date_column], dayfirst=True, errors='coerce')
                                dataset['DayOfYear'] = dataset[date_column].dt.dayofyear

                                with current_tab:
                                    st.subheader(f"Date Processing for {name}")
                                    st.success(f"Successfully processed the dataset with {date_column} as the date-related column.")
                                    st.write(dataset[['DayOfYear', date_column]].head())
                                    st.markdown("<br>" * 1, unsafe_allow_html=True)
                                # Sales Prediction
                                if 'Sales' in dataset.columns:
                                    X = dataset[['DayOfYear']]
                                    y = dataset['Sales']
                                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42) # Optional: Debugging check

                                    with current_tab:
                                        name = f"Dataset {index + 1}"
                                        st.subheader(f"Sales prediction for {name}")
                                        
                                        selected_model = st.selectbox(
                                            f"Choose a forecasting model for {name}:", ["None", "Linear Regression", "Random Forest", "ARIMA", "LSTM (Long-Short-Term-Memory)"],
                                            key = f"model_{index}"
                                        )

                                        if selected_model != "None":
                                            model = None
                                            y_pred = None
                                            y_pred_rescaled = None
                                            y_test_rescaled = y_test    

                                            # Linear regression model
                                            if selected_model == "Linear Regression":
                                                model = LinearRegression()
                                                model.fit(X_train, y_train)
                                                y_pred = model.predict(X_test)
                                                y_pred_rescaled = y_pred  

                                                # Linear Regression specific recommendation
                                                st.subheader("Sales Recommendations")
                                                st.write(f"Model: {selected_model}")
                                                st.write("""
                                                    Recommendation:  Linear regression suggests that the sales trend is relatively stable. 
                                                    Based on this model, consider using previous sales data to project inventory needs 
                                                    for the future. Adjust inventory based on seasonal sales patterns.
                                                """)

                                            elif selected_model == "Random Forest":
                                                model = RandomForestRegressor(n_estimators=100, random_state=42)
                                                model.fit(X_train, y_train)
                                                y_pred = model.predict(X_test)
                                                y_pred_rescaled = y_pred 

                                                st.subheader("Sales Recommendations")
                                                st.write(f"Model: {selected_model}")
                                                st.write("""
                                                    Recommendation:  The Random Forest model is sensitive to fluctuations in sales, 
                                                    which means it captures potential surges in demand or downturns. Based on this model, 
                                                    you might want to keep a buffer stock to accommodate unexpected sales increases. 
                                                    Consider promotions during predicted high-demand periods to maximize revenue.
                                                """)

                                            elif selected_model == "ARIMA":
                                                y_train_series = dataset.set_index(date_column)['Sales']  # Set the date column as index for time series
                                                arima_model = ARIMA(y_train_series, order=(5, 1, 0))
                                                model = arima_model.fit()  # Fitting the model
                                                y_pred = model.forecast(steps=len(X_test)) 
                                                y_pred_rescaled = y_pred  # Assuming ARIMA predicts in the original scale of sales

                                                st.subheader("Sales Recommendations")
                                                st.write(f"Model: {selected_model}")
                                                st.write("""
                                                    Recommendation:  ARIMA detects seasonal trends and cyclical patterns in your sales data. 
                                                    If the forecast predicts sales growth in certain months, consider ramping up production or 
                                                    inventory. Conversely, if sales are expected to dip, adjust marketing and sales strategies 
                                                    to counteract the decline.
                                                """)
                            
                                            elif selected_model == "LSTM (Long-Short-Term-Memory)":
                                                # LSTM model for time series forecasting
                                                scaler = MinMaxScaler(feature_range=(0, 1))
                                                scaled_data = scaler.fit_transform(data[['Sales']])

                                                time_steps = 10  # Adjust as needed
                                                X, y = [], []

                                                for i in range(len(scaled_data) - time_steps):
                                                    X.append(scaled_data[i:i+time_steps, 0])
                                                    y.append(scaled_data[i+time_steps, 0])

                                                X, y = np.array(X), np.array(y)

                                                # Reshape X for LSTM (samples, time_steps, features)
                                                X = X.reshape((X.shape[0], X.shape[1], 1))

                                                # Split data
                                                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                                                # Build LSTM model
                                                model = Sequential()
                                                model.add(LSTM(20, return_sequences=False, input_shape=(time_steps, 1)))
                                                model.add(Dense(1))

                                                # Compile model
                                                model.compile(optimizer='adam', loss='mean_squared_error')

                                                # Train the model
                                                model.fit(X_train, y_train, epochs=5, batch_size=32, validation_data=(X_test, y_test))

                                                # Perform predictions for the test data
                                                y_pred = model.predict(X_test)

                                                # Rescale the predictions back to the original scale
                                                y_pred_rescaled = scaler.inverse_transform(y_pred)
                                                y_test_rescaled = scaler.inverse_transform(y_test.reshape(-1, 1))

                                                # Early stopping to prevent overtraining
                                                early_stop = EarlyStopping(monitor='loss', patience=2, restore_best_weights=True)

                                                # LSTM specific recommendation
                                                st.subheader("Sales Recommendations")
                                                st.write(f"Model: {selected_model}")
                                                st.write("""
                                                        Recommendation:  LSTM is great for capturing longer-term dependencies in your sales data. 
                                                        This model can detect long-range patterns, such as yearly seasonality. Based on this, 
                                                        it's recommended to optimize both short-term and long-term sales strategies. 
                                                        For example, if sales are expected to increase over several months, consider promotional 
                                                        events or product launches.
                                                """)
                                    
                                            if y_pred_rescaled is not None and y_test_rescaled is not None:
                                                # Flatten arrays for plotting
                                                y_test_rescaled_flat = np.array(y_test_rescaled).flatten()
                                                y_pred_rescaled_flat = np.array(y_pred_rescaled).flatten()

                                                # Visualize prediction
                                                fig = go.Figure(data=go.Scatter(x=y_test_rescaled_flat, y=y_pred_rescaled_flat, mode='markers'))
                                                fig.update_layout(
                                                    title="Predicted vs Actual Sales",
                                                    xaxis_title="Actual Sales",
                                                    yaxis_title="Predicted Sales"
                                                )
                                                st.plotly_chart(fig)

                                                # 8. Model Suggestions for large datasets
                                                total_size = dataset.memory_usage(deep=True).sum()
                                                if total_size > 50 * (1024 ** 2):  # if dataset is larger than 50MB
                                                    st.warning("Your dataset is large. For better performance, consider using models like LSTM or XGBoost.")
                                                    continue

                                            st.markdown("<br>" * 1, unsafe_allow_html=True)
                                            st.subheader("Future Sales Forecast")
                                            forecast_days = st.slider(f"Select days for future forecast for {name}", 1, 30, 7, key = f"forecast_days_{index}")
                                            # Future Sales Forecast for LSTM
                                            if selected_model == "LSTM (Long-Short-Term-Memory)":
                                                # Prepare for future prediction using the last available time window from the dataset
                                                last_sequence = scaled_data[-time_steps:]  # Using the last `time_steps` rows

                                                future_predictions = []
                                                for _ in range(forecast_days):
                                                    last_sequence_reshaped = last_sequence.reshape((1, time_steps, 1))
        
                                                    # Predict the next value
                                                    next_prediction = model.predict(last_sequence_reshaped)[0, 0]
                                                    future_predictions.append(next_prediction)
                                                    last_sequence = np.roll(last_sequence, -1)
                                                    last_sequence[-1] = next_prediction

                                                # Rescale the predictions back to the original scale
                                                future_predictions_rescaled = scaler.inverse_transform(np.array(future_predictions).reshape(-1, 1))
                                                # Generate future dates
                                                future_dates = pd.date_range(start=dataset[date_column].max(), periods=forecast_days + 1, freq='D')[1:]

                                                # Create a DataFrame with the forecasted sales
                                                forecast_df = pd.DataFrame({'Date': future_dates, 'Forecasted Sales': future_predictions_rescaled.flatten()})

                                                st.write("Forecasted Sales for the next few days:")
                                                st.write(forecast_df)

                                            # Handle forecasting for Linear Regression, Random Forest, and ARIMA models
                                            elif selected_model in ["Linear Regression", "Random Forest", "ARIMA"]:
                                                future_X = pd.DataFrame({
                                                    'DayOfYear': [(X['DayOfYear'].max() + i) % 365 for i in range(forecast_days)]
                                                })

                                                if selected_model == "ARIMA":
                                                    future_pred = model.forecast(steps=forecast_days)

                                                else:  # Linear Regression or Random Forest
                                                    future_pred = model.predict(future_X)

                                                # Generate future dates
                                                future_dates = pd.date_range(start=dataset[date_column].max(), periods=forecast_days + 1, freq='D')[1:]

                                                date_column = col  
                                                dataset[date_column] = pd.to_datetime(dataset[date_column])  # Ensure it's in datetime format
                                                future_dates = pd.date_range(start=dataset[date_column].max(), periods=forecast_days + 1, freq='D')[1:]

                                                # Create a DataFrame with the forecasted sales
                                                forecast_df = pd.DataFrame({'Date': future_dates, 'Forecasted Sales': future_pred})

                                                st.write("Forecasted Sales for the next few days:")
                                                st.write(forecast_df)
                                                st.markdown("<br>" * 1, unsafe_allow_html=True)

                                            st.download_button(f"Download Forecast Data", forecast_df.to_csv(index=False), file_name="forecasted_sales_{name}.csv", key=f"download_{name}_{index}")
                                else:
                                    st.error("Please add Sales column in your dataset for performing sales predictions.")
                                    continue
                        else: 
                            print("No datasets uploaded!")

def show_about():
    st.title("About This App📉")
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Sales Prediction Models:")
    st.write("""
        
    In this application, we use a variety of machine learning models for sales predictions. Here's a breakdown of the models:

    1. **Linear Regression**:
       - Assumes a linear relationship between features and sales.
        
    2. **Random Forest**:
       - A robust ensemble model that aggregates results from multiple decision trees.
        
    3. **ARIMA (AutoRegressive Integrated Moving Average)**:
       - A time series model for detecting trends and seasonality.

    4. **LSTM (Long Short-Term Memory)**:
       - Captures long-term dependencies in time series data.
    """)    
    
    st.write("---")
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("**Inventory Optimization Models**:")
    st.write("""
             
    This app also provides inventory optimization using machine learning models. Here’s an overview of the models used:

    1. **Random Forest for Inventory Optimization**:
       - Uses a machine learning approach to forecast sales for a specified lead time.
       - Helps in calculating reorder points by considering historical sales data and variability.
       - Safety Stock Level: Accounts for variability in demand to ensure stock is sufficient.

    2. **ARIMA for Inventory Optimization**:
       - A time series forecasting model specifically tailored for sequential data.
       - It estimates future demand over the lead time, helping to establish reorder points.
       - Safety Stock Level: Calculates safety stock to account for demand fluctuations during the lead time.
    """)

    st.write("---")
    st.subheader("**User Management**:")
    st.write("""         
    - Secure login and signup are implemented using hashed passwords.
    - Users can update passwords, and session management is included to ensure data security.
    """)
    st.write("---")
    st.subheader("**Future Improvements**:")
    st.write("""   
    - We're working on incorporating external factors like marketing campaigns and holidays.
    - New models like **XGBoost** and **Prophet** are in development for more accurate predictions.
    """)
    st.write("")
    st.image(r"future imp2.png", caption='Empowering Growth Through Data-Driven Insights and Forecasting', width=700, clamp=True, channels='RGB')

def show_ask_question():
    st.title("Ask a Question")
    category = st.selectbox("Select Category of Your Question", 
                            ["General Inquiry", "Sales Prediction Models", "Inventory Optimization", "User Account", "Technical Support"])
    question = st.text_area("Ask your question here:")
    user_email = st.text_input("Your Email (optional, if you want a direct response):")

    st.write("")
    col1, col2, col3, col4 = st.columns([1,1,2,1])
    with col3:
        if st.button("Submit Question"):
            if question:
                # Add logic to store the question in the database with category and optional contact info
                conn = sqlite3.connect("user_data.db")
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, category TEXT, question TEXT, email TEXT)")
                cursor.execute("INSERT INTO questions (category, question, email) VALUES (?, ?, ?)", (category, question, user_email))
                conn.commit()
                conn.close()

                st.success("Your question has been submitted. We'll get back to you soon!")
            else:
                st.error("Please enter a question before submitting.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("Frequently Asked Questions")
    st.write("""
    **Q: What models are used in the sales prediction section?**
    """)
    st.write("A: We use Linear Regression, Random Forest, ARIMA, and LSTM for sales predictions.")
    
    st.write("**Q: How do I reset my password?**")
    st.write("A: Use the 'Forgot Password' option on the login page to reset your password.")
    
    st.write("**Q: What is the purpose of the inventory optimization feature?**")
    st.write("""A: It helps businesses maintain sufficient stock levels by recommending reorder points and safety stock levels.
    """) 

    if st.session_state.get("user_logged_in"):
        st.subheader("Your Past Questions")
        conn = sqlite3.connect("user_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT category, question FROM questions WHERE email=?", (st.session_state.get("user_email"),))
        questions = cursor.fetchall()
        conn.close()
        
        if questions:
            for cat, ques in questions:
                st.write(f"- **Category**: {cat}")
                st.write(f"  **Question**: {ques}")
        else:
            st.info("You haven't submitted any questions yet.")

def show_feedback():
    st.title("We Value Your Feedback")
    st.subheader("Rate Your Experience")
    st.write("How would you rate your experience with our Sales Predictions App?")
    

    if 'rating' not in st.session_state:
        st.session_state.rating = 0

    col1, col2, col3, col4, col5 = st.columns(5)
    star_button_css = """
        <style>
            /* Styling the star buttons based on the key */
            div[data-testid="star1"] button {
                background-color: #C0C0C0; /* Silver color */
                font-size: 2em;
                border: none;
                cursor: pointer;
                border-radius: 5px;
                padding: 10px;
            }
            div[data-testid="star1"] button:hover {
                background-color: #A9A9A9; /* Darker silver on hover */
            }

            div[data-testid="star2"] button {
                background-color: #C0C0C0;
                font-size: 2em;
                border: none;
                cursor: pointer;
                border-radius: 5px;
                padding: 10px;
            }
            div[data-testid="star2"] button:hover {
                background-color: #A9A9A9;
            }

            div[data-testid="star3"] button {
                background-color: #C0C0C0;
                font-size: 2em;
                border: none;
                cursor: pointer;
                border-radius: 5px;
                padding: 10px;
            }
            div[data-testid="star3"] button:hover {
                background-color: #A9A9A9;
            }

            div[data-testid="star4"] button {
                background-color: #C0C0C0;
                font-size: 2em;
                border: none;
                cursor: pointer;
                border-radius: 5px;
                padding: 10px;
            }
            div[data-testid="star4"] button:hover {
                background-color: #A9A9A9;
            }

            div[data-testid="star5"] button {
                background-color: #C0C0C0;
                font-size: 2em;
                border: none;
                cursor: pointer;
                border-radius: 5px;
                padding: 10px;
            }
            div[data-testid="star5"] button:hover {
                background-color: #A9A9A9;
            }
        </style>
    """
    st.markdown(star_button_css, unsafe_allow_html=True)
    with col1:
        if st.button('⭐', key='star1'):
            st.session_state.rating = 1
    with col2:
        if st.button('⭐', key='star2'):
            st.session_state.rating = 2
    with col3:
        if st.button('⭐', key='star3'):
            st.session_state.rating = 3
    with col4:
        if st.button('⭐', key='star4'):
            st.session_state.rating = 4
    with col5:
        if st.button('⭐', key='star5'):
            st.session_state.rating = 5

    if st.session_state.rating > 0:
        st.write(f"You selected: {'⭐' * st.session_state.rating}")

    st.subheader("Leave Your Comments")
    feedback = st.text_area("Please provide your feedback regarding the app:")
    if st.button("Submit Feedback"):
        if feedback or st.session_state.rating:
            st.success(f"Thank you for your feedback! You rated the app {st.session_state.rating} stars.😊")
        else:
            st.error("Please provide either a rating or some written feedback.")
    
    st.write("Your feedback helps us improve the app and deliver a better experience for you in the future!")

def logout():
    st.title("Logout")
    st.write("Thank you for visiting our Sales Prediction Platform. We hope you found the insights and recommendations helpful! 😀")
    st.markdown("<br>" * 1, unsafe_allow_html=True)
    if st.session_state.get('logged_in', False):
        st.subheader("Ready to Log Out?")
        st.write("""
            If you have completed your tasks and would like to log out, click the button below. 
            We appreciate your time and look forward to seeing you again soon!✨
        """)

        if st.button("Confirm Logout", key="logout"):
            st.session_state.logged_in = False  
            st.success("You have been logged out successfully.")
            st.balloons()  # Celebrate their visit with balloons!
            st.write("Redirecting you back to the login page...")
            time.sleep(1)
            st.rerun()
    else:
        st.info("You are already logged out.")
    st.write("")
    st.video(r"an animation of a hand drawn business strategy with chart_preview.mp4")

# Main routing logic based on session state
def main():
    if not st.session_state.logged_in:
        if st.session_state.signed_up:
            signup_page()  # Show the signup page
        elif st.session_state.reset_password:
            reset_password_page()
        else:
            login_page()  # Show the login page
    else:
        st.sidebar.title("Dashboard")
        st.sidebar.markdown("---")
        page = st.sidebar.selectbox("Choose a section", ["App", "About", "Ask a Question", "Feedback", "Logout"])

        if page == "App":
            app()
        elif page == "About":
            show_about()
        elif page == "Ask a Question":
            show_ask_question()
        elif page == "Feedback":
            show_feedback()
        elif page == "Logout":
            logout()

# Call the main function to route the app
if __name__ == "__main__":
    main()

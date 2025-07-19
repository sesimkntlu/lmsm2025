import requests
import pandas as pd
import os
import json # Import json for embedding data
import re # Import regex module for cleaning
import traceback # Import traceback for detailed error logging

# Helper function to clean a single header string
def clean_header_string(header):
    # Remove text after newline, including the newline itself
    cleaned = header.split('\n')[0].strip()
    # Remove text in parentheses (e.g., "(Kanorin 1)")
    cleaned = re.sub(r'\s*\(.*\)', '', cleaned).strip()
    # Remove asterisks and extra spaces
    cleaned = cleaned.replace('*', '').strip()
    return cleaned

# --- Step 1: Securely get the API key from the environment variable ---
api_key = os.getenv("GOOGLE_SHEET_API_KEY")
sheet_id = '1MYTD8Z_F408OPRSJos8JWS_0tgvM9Dmo6wlVKfZjrmM' # Replace with your Sheet ID if it's different

# --- Step 2: Fetch data from the Google Sheets API ---
dashboard_data = {
    "totalMunicipality": 0,
    "municipalityChartData": {"labels": [], "data": []},
    "totalGender": 0,
    "genderChartData": {"labels": [], "data": [], "percentages": []},
    "ageDistribution": {},
    "ageChartData": {"labels": [], "data": []},
    "schoolLevelCounts": {},
    "schoolLevelChartData": {"labels": [], "data": []},
    "schoolMunicipalityTableData": [],
    "totalDiscipline": 0,
    "disciplineCounts": {},
    "disciplineChartData": {"labels": [], "data": []},
    "totalTopiku": 0,
    "allNivelEskolaOptions": ["All"],
    "allMunisipiuOptions": ["All"],
    "detailedTableData": [],
    "municipalityPieChartData": {"labels": [], "data": []}
}

try:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/dadus?key={api_key}"
    response = requests.get(url)
    response.raise_for_status() # This will raise an HTTPError for bad responses (4xx or 5xx)
    data = response.json().get('values', [])

    # --- DEBUG PRINT: Raw data fetched from Google Sheets ---
    print("--- Raw data fetched (first 5 rows): ---")
    for i, row in enumerate(data):
        if i < 5:
            print(row)
        else:
            break
    print("------------------------------------------")

    if data and len(data) > 0:
        raw_headers = data[0]
        data_rows = data[1:]

        # Determine the maximum number of columns in the data rows
        max_data_cols = 0
        if data_rows:
            max_data_cols = max(len(row) for row in data_rows)
        else:
            print("No data rows found after headers.")
            # If no data rows, create an empty DataFrame with cleaned headers
            cleaned_headers_for_empty_df = [clean_header_string(h) for h in raw_headers]
            df = pd.DataFrame(columns=cleaned_headers_for_empty_df)
            # Skip further processing if no data
            raise ValueError("No data rows to process.") # Raise to jump to exception handler

        # Slice raw_headers to match the maximum number of columns in data_rows
        # This is crucial to avoid the "columns passed, passed data had X columns" error
        adjusted_raw_headers = raw_headers[:max_data_cols]

        # Create DataFrame with the adjusted raw headers
        df = pd.DataFrame(data_rows, columns=adjusted_raw_headers)

        # --- NEW: Explicitly rename columns using the cleaning function ---
        # Create a dictionary for renaming: {old_name: new_cleaned_name}
        rename_map = {col: clean_header_string(col) for col in df.columns}
        df.rename(columns=rename_map, inplace=True)

        # --- Handle duplicate column names that might arise after cleaning ---
        # E.g., 'Seksu (Kanorin 1)' and 'Seksu (Kanorin 2)' both become 'Seksu'
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            # Append _1, _2, _3 etc. to duplicates
            # The first occurrence keeps the original cleaned name
            indices_of_dup = cols[cols == dup].index.values.tolist()
            for i, idx in enumerate(indices_of_dup):
                if i == 0:
                    cols[idx] = dup # First occurrence remains 'Seksu' or 'Idade'
                else:
                    cols[idx] = f"{dup}_{i}" # Subsequent occurrences get _1, _2, etc. (Seksu_1, Seksu_2)
        df.columns = cols


        # --- DEBUG PRINT: DataFrame head and columns (after ALL cleaning and renaming) ---
        print("--- DataFrame Head (after ALL cleaning and renaming): ---")
        print(df.head())
        print("--- DataFrame Columns (after ALL cleaning and renaming): ---")
        print(df.columns.tolist())
        print("-----------------------------------------")

        # --- DEBUG PRINT: Munisípiu column value_counts (df) ---
        if 'Munisípiu' in df.columns:
            print("--- Munisípiu column value_counts (df, before aggregation): ---")
            print(df['Munisípiu'].value_counts(dropna=False))
            print("----------------------------------")
        else:
            print("--- WARNING: 'Munisípiu' column not found in df after cleaning. ---")


        # --- Data Aggregation for Dashboard Statistics ---
        # Identify all Seksu and Idade columns based on their *newly unique* cleaned names
        sek_cols_for_melt = [col for col in df.columns if col.startswith('Seksu') and not col.endswith('_Manorin')]
        idade_cols_for_melt = [col for col in df.columns if col.startswith('Idade') and not col.endswith('_Manorin')]

        # Create a list of DataFrames for each 'Kanorin' entry for aggregation
        processed_records = []
        # Iterate over the identified Seksu/Idade columns
        for i, (sek_col, idade_col) in enumerate(zip(sek_cols_for_melt, idade_cols_for_melt)):
            temp_df = df[[
                'Munisípiu', # Use 'Munisípiu' with accent here
                'Nivel Eskola', 'Naran Eskola',
                'Dixiplina', 'Títulu/Tópiku Atividade', # Use 'Títulu/Tópiku Atividade' with accent here
                sek_col, idade_col
            ]].copy()
            temp_df.rename(columns={
                'Munisípiu': 'Munisipiu', # NEW: Rename to 'Munisipiu' without accent for consistency
                sek_col: 'Seksu', # Rename back to simple 'Seksu' for aggregation
                idade_col: 'Idade',   # Rename back to simple 'Idade' for aggregation
                'Títulu/Tópiku Atividade': 'Titulu/Tópiku' # Standardize for dashboard
            }, inplace=True)
            processed_records.append(temp_df)


        if processed_records:
            # Concatenate all processed records into one DataFrame for aggregation
            agg_df = pd.concat(processed_records, ignore_index=True)
            
            # Clean whitespace from 'Munisipiu' and replace empty strings with NaN
            if 'Munisipiu' in agg_df.columns:
                agg_df['Munisipiu'] = agg_df['Munisipiu'].astype(str).str.strip()
                agg_df['Munisipiu'] = agg_df['Munisipiu'].replace('', pd.NA) # Replace empty strings with NA
            
            # Drop rows where Seksu or Idade are empty/None
            agg_df = agg_df.dropna(subset=['Seksu', 'Idade'], how='all')

            # Convert 'Idade' to numeric, coercing errors to NaN
            print("--- Idade column before numeric conversion (agg_df): ---")
            print(agg_df['Idade'].head())
            agg_df['Idade'] = pd.to_numeric(agg_df['Idade'], errors='coerce')
            print("--- Idade column after numeric conversion (agg_df): ---")
            print(agg_df['Idade'].head())
            print("---------------------------------------------")

            # --- DEBUG PRINT: Seksu column value counts (agg_df) ---
            print("--- Seksu column value_counts (agg_df): ---")
            print(agg_df['Seksu'].value_counts(dropna=False))
            print("----------------------------------")

            # --- DEBUG PRINT: Munisipiu column value_counts (agg_df) ---
            if 'Munisipiu' in agg_df.columns:
                print("--- Munisipiu column value_counts (agg_df, after aggregation and cleaning): ---")
                print(agg_df['Munisipiu'].value_counts(dropna=False))
                print("----------------------------------")
            else:
                print("--- WARNING: 'Munisipiu' column not found in agg_df after aggregation. ---")


            # --- Data Processing for Dashboard using agg_df ---
            dashboard_data["totalMunicipality"] = agg_df['Munisipiu'].nunique(dropna=True) if 'Munisipiu' in agg_df.columns else 0

            municipality_counts = agg_df['Munisipiu'].value_counts().sort_index() if 'Munisipiu' in agg_df.columns else pd.Series()
            # Filter out empty/NA values from labels and data for charts
            municipality_counts = municipality_counts[municipality_counts.index.notna() & (municipality_counts.index != '')]
            dashboard_data["municipalityChartData"]["labels"] = municipality_counts.index.tolist()
            dashboard_data["municipalityChartData"]["data"] = municipality_counts.values.tolist()
            dashboard_data["municipalityPieChartData"] = dashboard_data["municipalityChartData"]

            gender_counts = agg_df['Seksu'].value_counts() if 'Seksu' in agg_df.columns else pd.Series()
            dashboard_data["totalGender"] = len(agg_df) # Total participants
            dashboard_data["genderChartData"]["labels"] = gender_counts.index.tolist()
            dashboard_data["genderChartData"]["data"] = gender_counts.values.tolist()
            dashboard_data["genderChartData"]["percentages"] = [f"{{{{ (val / dashboard_data['totalGender'] * 100):.1f}}}}%" for val in gender_counts.values] if dashboard_data['totalGender'] > 0 else []

            age_distribution = agg_df['Idade'].value_counts().sort_index().to_dict() if 'Idade' in agg_df.columns else {}
            dashboard_data["ageDistribution"] = {str(k): int(v) for k, v in age_distribution.items()}
            dashboard_data["ageChartData"]["labels"] = [str(age) for age in sorted(agg_df['Idade'].dropna().unique().tolist())] if 'Idade' in agg_df.columns else []
            dashboard_data["ageChartData"]["data"] = [int(age_distribution.get(label, 0)) for label in dashboard_data["ageChartData"]["labels"]]

            school_level_counts = agg_df['Nivel Eskola'].value_counts().sort_index() if 'Nivel Eskola' in agg_df.columns else pd.Series()
            dashboard_data["schoolLevelCounts"] = school_level_counts.to_dict()
            dashboard_data["schoolLevelChartData"]["labels"] = school_level_counts.index.tolist()
            dashboard_data["schoolLevelChartData"]["data"] = school_level_counts.values.tolist()

            school_municipality_grouped = agg_df.groupby(['Munisipiu', 'Naran Eskola']).size().reset_index(name='Total') if 'Munisipiu' in agg_df.columns and 'Naran Eskola' in agg_df.columns else pd.DataFrame()
            dashboard_data["schoolMunicipalityTableData"] = school_municipality_grouped.to_dict(orient='records')

            discipline_counts = agg_df['Dixiplina'].value_counts().sort_index() if 'Dixiplina' in agg_df.columns else pd.Series()
            dashboard_data["totalDiscipline"] = agg_df['Dixiplina'].nunique() if 'Dixiplina' in agg_df.columns else 0
            dashboard_data["disciplineCounts"] = discipline_counts.to_dict()
            dashboard_data["disciplineChartData"]["labels"] = discipline_counts.index.tolist()
            dashboard_data["disciplineChartData"]["data"] = discipline_counts.values.tolist()

            dashboard_data["totalTopiku"] = agg_df['Titulu/Tópiku'].nunique() if 'Titulu/Tópiku' in agg_df.columns else 0

            dashboard_data["allNivelEskolaOptions"] = ["All"] + sorted(agg_df['Nivel Eskola'].dropna().unique().tolist()) if 'Nivel Eskola' in agg_df.columns else ["All"]
            dashboard_data["allMunisipiuOptions"] = ["All"] + sorted(agg_df['Munisipiu'].dropna().unique().tolist()) if 'Munisipiu' in agg_df.columns else ["All"]

            # Detailed Table Data - Use the original df (with cleaned and unique headers) for this
            detailed_data_for_html = []
            for index, row in df.iterrows():
                row_dict = {}
                row_dict['Munisipiu'] = row.get('Munisípiu', 'N/A') # Use 'Munisípiu' with accent
                
                # Combine all Seksu and Idade values for display in the detailed table
                all_seksu_in_row = [row[col] for col in sek_cols_for_melt if pd.notna(row[col]) and row[col] != '']
                all_idade_in_row = [row[col] for col in idade_cols_for_melt if pd.notna(row[col]) and row[col] != '']

                row_dict['Seksu'] = ', '.join(all_seksu_in_row) if all_seksu_in_row else 'N/A'
                row_dict['Idade'] = ', '.join(map(str, all_idade_in_row)) if all_idade_in_row else 'N/A'
                
                row_dict['Dixiplina'] = row.get('Dixiplina', 'N/A')
                row_dict['Nivel Eskola'] = row.get('Nivel Eskola', 'N/A')
                row_dict['Naran Eskola'] = row.get('Naran Eskola', 'N/A')
                row_dict['Titulu/Tópiku'] = row.get('Títulu/Tópiku Atividade', 'N/A') # Use 'Títulu/Tópiku Atividade' with accent
                row_dict['Timestamp'] = row.get('Timestamp', 'N/A')
                
                detailed_data_for_html.append(row_dict)

            dashboard_data["detailedTableData"] = detailed_data_for_html
            
            # Convert values to string and handle NaN/empty for detailed table
            for row in dashboard_data["detailedTableData"]:
                row['id'] = str(row.get('id', index)) # Use index as default id if not present
                for key, value in row.items():
                    if pd.isna(value) or value == '':
                        row[key] = 'N/A'
                    elif isinstance(value, (int, float)):
                        row[key] = str(value)
        else:
            dashboard_data["detailedTableData"] = []


    else:
        print("No data found in Google Sheet or sheet is empty.")

except requests.exceptions.RequestException as e:
    print(f"Error fetching data: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"An unexpected error occurred during data processing: {e}")
    traceback.print_exc()


# --- Step 3: Define the full HTML content with embedded data ---
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demographic Dashboard Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
        }}
        
        body {{
            background-image: url('./assets/AY1A8030.jpg'); /* Updated: Suggested path for your background image */
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center center;
            background-attachment: fixed;
        }}
        .bg-white, .bg-blue-50 {{
            background-color: rgba(255, 255, 255, 0.9);
        }}
        header, footer {{
            position: relative;
            z-index: 10;
        }}
        .text-indigo-800, .text-indigo-700, .text-blue-600, .text-gray-800 {{
            text-shadow: 0px 0px 2px rgba(255,255,255,0.7);
        }}
    
        .max-h-40 {{max-height: 10rem;}}
        .overflow-y-auto {{overflow-y: auto;}}
        canvas {{
            max-width: 100%;
            height: 250px;
        }}
        .chart-container {{
            position: relative;
            height: 250px;
            width: 100%;
        }}
        /* Custom table styles for better appearance and sticky header */
        .detailed-table-wrapper {{
            overflow-x: auto;
            overflow-y: auto;
            max-height: 500px; /* Adjust as needed */
            border-radius: 0.5rem;
            border: 1px solid #e2e8f0; /* gray-200 */
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
        .detailed-table-wrapper table {{
            min-width: 100%;
            border-collapse: collapse;
        }}
        .detailed-table-wrapper thead {{
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: #eff6ff; /* blue-50 */
        }}
        .detailed-table-wrapper th {{
            padding: 0.75rem 1.5rem; /* px-6 py-3 */
            text-align: left;
            font-size: 0.75rem; /* text-xs */
            font-weight: 500; /* font-medium */
            color: #1d4ed8; /* blue-700 */
            text-transform: uppercase;
            letter-spacing: 0.05em; /* tracking-wider */
            border-bottom: 1px solid #cbd5e0; /* gray-300 */
        }}
        .detailed-table-wrapper td {{
            padding: 1rem 1.5rem; /* px-6 py-4 */
            white-space: nowrap;
            font-size: 0.875rem; /* text-sm */
            color: #1f2937; /* gray-900 */
            border-bottom: 1px solid #f3f4f6; /* gray-100 */
        }}
        .detailed-table-wrapper tbody tr:last-child td {{
            border-bottom: none;
        }}
        .detailed-table-wrapper tbody tr:hover {{
            background-color: #f9fafb; /* gray-50 */
        }}
        .pagination-controls button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        .download-button {{
            display: inline-block;
            padding: 12px 25px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: bold;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s ease, transform 0.2s ease;
            box-shadow: 0 4px 10px rgba(0, 123, 255, 0.3);
            margin-top: 20px; /* Added margin for spacing */
        }}
        .download-button:hover {{
            background-color: #0056b3;
            transform: translateY(-2px);
        }}
        .download-button:active {{
            transform: translateY(0);
            box-shadow: 0 2px 5px rgba(0, 123, 255, 0.5);
        }}
    </style>
</head>
<body class="min-h-screen p-6 text-gray-800">
    <header class="text-center mb-10">
        <h1 class="text-5xl font-extrabold text-indigo-600 mb-2 rounded-lg p-2 shadow-sm">
            Relatóriu Atuál Progresu Rejistrasaun Selebrasaun LMSM 2025
        </h1>
        <p class="text-lg font-extrabold text-indigo-700">SESIM-KNTLU</p>
    </header>

    <section class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 flex flex-col items-center justify-center">
            <h2 class="text-2xl font-bold text-indigo-500 mb-3">🏙️ Munisípiu</h2>
            <p id="totalMunicipality" class="text-5xl font-extrabold text-purple-600"></p>
        </div>
        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 flex flex-col items-center justify-center">
            <h2 class="text-2xl font-bold text-indigo-500 mb-3">👥 Seksu</h2>
            <p id="totalGender" class="text-5xl font-extrabold text-purple-600"></p>
        </div>
        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 flex flex-col items-center justify-center">
            <h2 class="text-2xl font-bold text-indigo-500 mb-3">📚 Dixiplina</h2>
            <p id="totalDiscipline" class="text-5xl font-extrabold text-purple-600"></p>
        </div>
        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 flex flex-col items-center justify-center">
            <h2 class="text-2xl font-bold text-indigo-500 mb-3">Tópiku LMSM</h2>
            <p id="totalTopiku" class="text-5xl font-extrabold text-purple-600"></p>
        </div>
    </section>

    <section id="summary-section" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6 mb-10">
        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1">
            <h2 class="text-2xl font-bold text-indigo-500 mb-3">Persentajen tuir Jéneru</h2>
            <div class="chart-container">
                <canvas id="genderChart"></canvas>
            </div>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1">
            <h2 class="text-2xl font-bold text-indigo-700 mb-3">Distribuisaun tuir Idade</h2>
            <div class="chart-container">
                <canvas id="ageChart"></canvas>
            </div>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1">
            <h2 class="text-2xl font-bold text-indigo-700 mb-3">Tópiku tuir kada Dixiplina</h2>
            <div class="chart-container">
                <canvas id="disciplineChart"></canvas>
            </div>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1">
            <h2 class="text-2xl font-bold text-indigo-700 mb-3">Distribuisaun Tópiku tuir Nivel Eskola</h2>
            <div class="chart-container">
                <canvas id="schoolLevelChart"></canvas>
            </div>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 md:col-span-2 lg:col-span-2">
            <h2 class="text-2xl font-bold text-indigo-700 mb-3">Distribuisaun Tópiku tuir Munisípiu</h2>
            <div class="chart-container">
                <canvas id="municipalityChart"></canvas>
            </div>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 md:col-span-2 lg:col-span-2">
            <h2 class="text-2xl font-bold text-indigo-700 mb-3">Tabela kona-ba eskola ne'ebé rejistu hosi kada Munisípiu</h2>
            <div class="max-h-60 overflow-y-auto rounded-lg border border-gray-200 shadow-sm">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-blue-50">
                        <tr>
                            <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Munisípiu</th>
                            <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Naran Eskola</th>
                            <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Totál</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-100" id="schoolMunicipalityTableBody">
                        </tbody>
                </table>
            </div>
        </div>
    </section>

    <section class="bg-white p-6 rounded-xl shadow-lg mb-10">
        <h2 class="text-3xl font-bold text-indigo-800 mb-6">Tabela informasaun detallu kona-ba partisipante ne'ebe rejistu</h2>

        <div class="mb-6 flex flex-wrap items-center gap-4">
            <label for="nivelEskolaFilter" class="text-lg font-semibold text-gray-700">
                Filtru tuir Nivel Eskola:
            </label>
            <select
                id="nivelEskolaFilter"
                class="p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-200 text-gray-700 bg-white"
            >
                </select>

            <label for="munisipiuFilter" class="text-lg font-semibold text-gray-700">
                Filtru tuir Munisípiu:
            </label>
            <select
                id="munisipiuFilter"
                class="p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-200 text-gray-700 bg-white"
            >
                </select>

            <label for="detailedTableSearch" class="sr-only">Search</label>
            <div class="relative flex-grow">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
                    </svg>
                </div>
                <input
                    type="text"
                    id="detailedTableSearch"
                    placeholder="Buka dadus..."
                    class="pl-10 p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-200 w-full text-gray-700"
                >
            </div>

            
            <select
                id="rowsPerPage"
                class="p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all duration-200 text-gray-700 bg-white"
            >
                <option value="10">10</option>
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="All">Hotu</option>
            </select>
        </div>

        <div id="detailed-table-container" class="detailed-table-wrapper">
            </div>

        <div class="flex justify-between items-center mt-4">
            <button
                id="prevPage"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
            >
                Anterior
            </button>
            <span class="text-gray-700">Pájina <span id="currentPageSpan">1</span> hosi <span id="totalPagesSpan">1</span></span>
            <button
                id="nextPage"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
            >
                Tuirmai
            </button>
        </div>
    </section>

    <footer class="text-center text-gray-600 text-sm mt-10">
        <p>&copy; Relatóriu Atuál Rejistrasaun LMSM 2025, SESIM-KNTLU. All rights reserved.</p>
    </footer>

    <script>
        // Define the password for PDF editing (basic deterrent only)
        const PDF_EDIT_PASSWORD = 'your_strong_edit_password'; // <--- CHANGE THIS PASSWORD!

        async function downloadPdf() {{
            const {{ jsPDF }} = window.jspdf;
            const dashboardContent = document.getElementById('summary-section'); // Capture only the summary section for PDF

            // Use html2canvas to render the HTML content into a canvas
            const canvas = await html2canvas(dashboardContent, {{
                scale: 2, // Increase scale for better quality
                useCORS: true // Important for images if any
            }});

            const imgData = canvas.toDataURL('image/png');
            const pdf = new jsPDF('p', 'mm', 'a4'); // 'p' for portrait, 'mm' for millimeters, 'a4' for A4 size

            const imgWidth = 210; // A4 width in mm
            const pageHeight = 297; // A4 height in mm
            const imgHeight = canvas.height * imgWidth / canvas.width;
            let heightLeft = imgHeight;

            let position = 0;

            // Add image to PDF, handling multiple pages if content is long
            pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
            heightLeft -= pageHeight;

            while (heightLeft >= 0) {{
                position = heightLeft - imgHeight;
                pdf.addPage();
                pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
                heightLeft -= pageHeight;
            }}

            // Apply basic password protection for editing (owner password)
            // This is NOT strong security and can be bypassed.
            // A user password (for opening) is not applied here, only owner password for restrictions.
            pdf.save('lmsm-dashboard.pdf', {{
                'ownerPassword': PDF_EDIT_PASSWORD,
                'userPermissions': ['print', 'copy'] // Allow printing and copying, but restrict modification
            }});\
        }}


        // Register Chart.js Datalabels plugin globally
        Chart.register(ChartDataLabels);

        // Embed the processed data directly into a JavaScript variable
        // THIS WILL BE REPLACED BY THE PYTHON SCRIPT
        const dashboardData = {json.dumps(dashboard_data, indent=4)};

        let currentPage = 1;
        let rowsPerPage = 10;
        let currentSearchTerm = '';
        let currentNivelEskolaFilter = 'All';
        let currentMunisipiuFilter = 'All'; // New: Variable for Munisipiu filter

        // Utility to generate consistent colors
        function generateColors(numColors) {{
            const colors = [
                'rgba(75, 192, 192, 0.6)', 'rgba(153, 102, 255, 0.6)', 'rgba(255, 159, 64, 0.6)',
                'rgba(255, 99, 132, 0.6)', 'rgba(54, 162, 235, 0.6)', 'rgba(201, 203, 207, 0.6)',
                'rgba(255, 205, 86, 0.6)', 'rgba(100, 149, 237, 0.6)', 'rgba(255, 0, 255, 0.6)',
                'rgba(0, 255, 0, 0.6)', 'rgba(0, 0, 255, 0.6)', 'rgba(128, 0, 128, 0.6)'
            ];
            return Array.from({{length: numColors}}, (_, i) => colors[i % colors.length]);
        }}

        // Function to create a generic Bar Chart
        function createBarChart(canvasId, title, labels, data) {{
            const ctx = document.getElementById(canvasId).getContext('2d');
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: 'Totál',
                        data: data,
                        backgroundColor: generateColors(labels.length),
                        borderColor: generateColors(labels.length).map(color => color.replace('0.6', '1')),
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: title,
                            font: {{ size: 16, weight: 'bold' }}
                        }},
                        legend: {{
                            display: false
                        }},
                        datalabels: {{
                            anchor: 'end',
                            align: 'top',
                            formatter: (value) => value,
                            color: '#333',
                            font: {{ weight: 'bold' }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                precision: 0
                            }}
                        }}
                    }}
                }}
            }});
        }}

        // Function to create a generic Pie Chart
        function createPieChart(canvasId, title, labels, data) {{
            const ctx = document.getElementById(canvasId).getContext('2d');
            new Chart(ctx, {{
                type: 'pie',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: 'Pursentu',
                        data: data,
                        backgroundColor: generateColors(labels.length),
                        borderColor: '#fff',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: title,
                            font: {{ size: 16, weight: 'bold' }}
                        }},
                        legend: {{
                            position: 'bottom'
                        }},
                        datalabels: {{
                            formatter: (value, ctx) => {{
                                let sum = 0;
                                let dataArr = ctx.chart.data.datasets[0].data;
                                dataArr.map(data => {{
                                    sum += data;
                                }});
                                let percentage = (value * 100 / sum).toFixed(1) + "%";
                                return percentage;
                            }},
                            color: '#fff',
                            font: {{
                                weight: 'bold',
                                size: 14
                            }}
                        }}
                    }}
                }}
            }});
        }}

        // Function to render the detailed table
        function renderDetailedTable() {{
            const tableBody = document.createElement('tbody');
            tableBody.className = "bg-white divide-y divide-gray-100";
            const filteredData = dashboardData.detailedTableData.filter(row => {{
                const matchesSearch = currentSearchTerm === '' ||
                                      Object.values(row).some(value =>
                                          String(value).toLowerCase().includes(currentSearchTerm.toLowerCase())
                                      );
                const matchesNivelEskola = currentNivelEskolaFilter === 'All' ||
                                           row['Nivel Eskola'] === currentNivelEskolaFilter;
                const matchesMunisipiu = currentMunisipiuFilter === 'All' ||
                                         row['Munisipiu'] === currentMunisipiuFilter;
                return matchesSearch && matchesNivelEskola && matchesMunisipiu;
            }});

            const totalPages = rowsPerPage === 'All' ? 1 : Math.ceil(filteredData.length / rowsPerPage);
            document.getElementById('totalPagesSpan').textContent = totalPages;
            document.getElementById('currentPageSpan').textContent = currentPage;

            const startIndex = (currentPage - 1) * rowsPerPage;
            const endIndex = rowsPerPage === 'All' ? filteredData.length : startIndex + rowsPerPage;
            const paginatedData = filteredData.slice(startIndex, endIndex);

            // Clear existing table content
            const detailedTableContainer = document.getElementById('detailed-table-container');
            detailedTableContainer.innerHTML = ''; // Clear previous content

            // Create table structure
            const table = document.createElement('table');
            table.className = "min-w-full divide-y divide-gray-200";
            table.innerHTML = `
                <thead>
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Munisípiu</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Seksu</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Idade</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Dixiplina</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Nivel Eskola</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Naran Eskola</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Titulu/Tópiku</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-blue-700 uppercase tracking-wider">Timestamp</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-100" id="detailedTableBody">
                </tbody>
            `;
            detailedTableContainer.appendChild(table);
            const detailedTableBody = document.getElementById('detailedTableBody');


            paginatedData.forEach(row => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Munisipiu'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Seksu'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Idade'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Dixiplina'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Nivel Eskola'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Naran Eskola'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Titulu/Tópiku'] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{ row['Timestamp'] }}</td>
                `;
                detailedTableBody.appendChild(tr);
            }});

            // Update pagination button states
            document.getElementById('prevPage').disabled = currentPage === 1;
            document.getElementById('nextPage').disabled = currentPage === totalPages;
        }}

        // Function to populate filter options
        function populateFilterOptions() {{
            const nivelEskolaFilter = document.getElementById('nivelEskolaFilter');
            dashboardData.allNivelEskolaOptions.forEach(option => {{
                const opt = document.createElement('option');
                opt.value = option;
                opt.textContent = option;
                nivelEskolaFilter.appendChild(opt);
            }});

            const munisipiuFilter = document.getElementById('munisipiuFilter');
            dashboardData.allMunisipiuOptions.forEach(option => {{
                const opt = document.createElement('option');
                opt.value = option;
                opt.textContent = option;
                munisipiuFilter.appendChild(opt);
            }});
        }}

        // Initialize dashboard elements and charts
        document.addEventListener('DOMContentLoaded', () => {{
            document.getElementById('totalMunicipality').textContent = dashboardData.totalMunicipality;
            document.getElementById('totalGender').textContent = dashboardData.totalGender;
            document.getElementById('totalDiscipline').textContent = dashboardData.totalDiscipline;
            document.getElementById('totalTopiku').textContent = dashboardData.totalTopiku;

            // Create Charts
            createPieChart('genderChart', 'Persentajen tuir Jéneru', dashboardData.genderChartData.labels, dashboardData.genderChartData.data);
            createBarChart('ageChart', 'Distribuisaun tuir Idade', dashboardData.ageChartData.labels, dashboardData.ageChartData.data);
            createBarChart('disciplineChart', 'Tópiku tuir kada Dixiplina', dashboardData.disciplineChartData.labels, dashboardData.disciplineChartData.data);
            createBarChart('schoolLevelChart', 'Distribuisaun Tópiku tuir Nivel Eskola', dashboardData.schoolLevelChartData.labels, dashboardData.schoolLevelChartData.data);
            createBarChart('municipalityChart', 'Distribuisaun Tópiku tuir Munisípiu', dashboardData.municipalityChartData.labels, dashboardData.municipalityChartData.data);

            // Populate School Municipality Table
            const schoolMunicipalityTableBody = document.getElementById('schoolMunicipalityTableBody');
            dashboardData.schoolMunicipalityTableData.forEach(row => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">${{ row['Munisipiu'] }}</td>
                    <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-500">${{ row['Naran Eskola'] }}</td>
                    <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-500">${{ row['Total'] }}</td>
                `;
                schoolMunicipalityTableBody.appendChild(tr);
            }});

            // Populate filter options
            populateFilterOptions();

            // Event Listeners for Filters and Search
            const nivelEskolaFilter = document.getElementById('nivelEskolaFilter');
            nivelEskolaFilter.addEventListener('change', (event) => {{
                currentNivelEskolaFilter = event.target.value;
                currentPage = 1; // Reset to first page on filter change
                renderDetailedTable();
            }});

            const munisipiuFilter = document.getElementById('munisipiuFilter');
            munisipiuFilter.addEventListener('change', (event) => {{
                currentMunisipiuFilter = event.target.value;
                currentPage = 1; // Reset to first page on filter change
                renderDetailedTable();
            }});

            const detailedTableSearch = document.getElementById('detailedTableSearch');
            detailedTableSearch.addEventListener('input', (event) => {{
                currentSearchTerm = event.target.value;
                currentPage = 1; // Reset to first page on search
                renderDetailedTable();
            }});

            const rowsPerPageSelect = document.getElementById('rowsPerPage');
            rowsPerPageSelect.addEventListener('change', (event) => {{
                rowsPerPage = event.target.value === 'All' ? 'All' : parseInt(event.target.value);
                currentPage = 1; // Reset to first page when rows per page changes
                renderDetailedTable();
            }});

            document.getElementById('prevPage').addEventListener('click', () => {{
                if (currentPage > 1) {{
                    currentPage--;
                    renderDetailedTable();
                }}
            }});

            document.getElementById('nextPage').addEventListener('click', () => {{
                const totalPages = rowsPerPage === 'All' ? 1 : Math.ceil(dashboardData.detailedTableData.length / rowsPerPage);
                if (currentPage < totalPages) {{
                    currentPage++;
                    renderDetailedTable();
                }}
            }});

            // Initial render of detailed table with default settings
            renderDetailedTable();
        }});
    </script>
</body>
</html>
"""

# --- Step 4: Write the HTML content to the index.html file ---
# This is the crucial part that was missing or incomplete.
# Ensure this section is present and correct in your generate_dashboard.py file.
try:
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("index.html generated successfully with updated data.")
except Exception as e:
    print(f"Error writing index.html: {e}")


import requests
import pandas as pd
import json
import os
from collections import defaultdict

def fetch_google_sheet_data(spreadsheet_id, sheet_name, api_key):
    """
    Fetches data from a specified Google Sheet using the Google Sheets API.
    Requires the sheet to be publicly accessible (Anyone with the link can view).
    """
    api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}?key={api_key}"

    print(f"Attempting to fetch data from: {api_url}")
    print(f"DEBUG: Constructed API URL: {api_url}")

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        result = response.json()

        if 'values' in result and len(result['values']) > 1:
            raw_values = result['values'][1:]
            print(f"DEBUG: Successfully fetched {len(raw_values)} rows of raw data from Google Sheet.")
            return raw_values
        else:
            print("No data or only headers found in the Google Sheet.")
            return []
    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP error! Status: {e.response.status_code}, Message: {e.response.text}"
        print(f"Error fetching data: {error_message}")
        print("This is often due to incorrect Google Sheet sharing settings or API key permissions.")
        print("Please ensure your Google Sheet is set to 'Anyone with the link can view' with 'Viewer' access.")
        print("Also, confirm the Google Sheets API is enabled in your Google Cloud Project.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Network or request error: {e}")
        raise

def process_data(raw_data, column_mapping):
    """
    Processes the raw data to calculate demographic summaries and prepare table data.
    Adjusted to separate student data into individual rows for detailed table
    and to create a combined school-municipality table.
    """
    gender_counts = {}
    age_distribution = {}

    unique_municipalities_set = set()
    unique_disciplines_set = set()
    unique_topiku_set = set() # New: Set to store unique topiku titles

    municipality_chart_counts = {}
    discipline_chart_counts = {}
    school_level_counts = {}
    school_municipality_counts = defaultdict(lambda: defaultdict(int)) # New structure for Munisipiu-Naran Eskola table

    if not raw_data:
        return {
            "totalMunicipality": 0,
            "municipalityChartData": {"labels": [], "data": []},
            "totalGender": 0,
            "genderChartData": {"labels": [], "data": [], "percentages": []},
            "ageDistribution": {},
            "ageChartData": {"labels": [], "data": []},
            "schoolLevelCounts": {},
            "schoolLevelChartData": {"labels": [], "data": []},
            "schoolMunicipalityTableData": [], # New output for the school-municipality table
            "totalDiscipline": 0,
            "disciplineCounts": {},
            "disciplineChartData": {"labels": [], "data": []},
            "totalTopiku": 0, # New: Return total topiku count
            "allNivelEskolaOptions": ["All"],
            "allMunisipiuOptions": ["All"], # New: Add options for Munisipiu filter
            "detailedTableData": [],
            "municipalityPieChartData": {"labels": [], "data": []} # New: Added for municipality pie chart
        }

    processed_rows = []

    print("\nDEBUG: Processing data rows. Checking column values...")
    for i, row in enumerate(raw_data):
        # Safely get values using .get() for index, and check length of row
        # Stripping whitespace from all string values
        timestamp = row[column_mapping["TIMESTAMP"]].strip() if column_mapping.get("TIMESTAMP") is not None and len(row) > column_mapping["TIMESTAMP"] else 'N/A'

        munisipiu_index = column_mapping.get("MUNISIPIU")
        munisipiu = row[munisipiu_index].strip() if munisipiu_index is not None and len(row) > munisipiu_index else 'N/A'

        nivel_eskola_index = column_mapping.get("NIVEL_ESKOLA")
        nivel_eskola = row[nivel_eskola_index].strip() if nivel_eskola_index is not None and len(row) > nivel_eskola_index else 'N/A'

        naran_eskola_index = column_mapping.get("NARAN_ESKOLA")
        naran_eskola = row[naran_eskola_index].strip() if naran_eskola_index is not None and len(row) > naran_eskola_index else 'N/A'

        dixiplina_index = column_mapping.get("DIXIPLINA")
        dixiplina = row[dixiplina_index].strip() if dixiplina_index is not None and len(row) > dixiplina_index else 'N/A'

        topiku_atividade_index = column_mapping.get("TITULU_TOPIKU_ATIVIDADE") # New: Get topiku index
        topiku_atividade = row[topiku_atividade_index].strip() if topiku_atividade_index is not None and len(row) > topiku_atividade_index else 'N/A' # New: Get topiku value

        dokumentus_index = column_mapping.get("DOKUMENTUS")
        dokumentus = row[dokumentus_index].strip() if dokumentus_index is not None and len(row) > dokumentus_index else 'N/A'

        if munisipiu and munisipiu != 'N/A':
            unique_municipalities_set.add(munisipiu)
            municipality_chart_counts[munisipiu] = municipality_chart_counts.get(munisipiu, 0) + 1

        if dixiplina and dixiplina != 'N/A':
            unique_disciplines_set.add(dixiplina)
            discipline_chart_counts[dixiplina] = discipline_chart_counts.get(dixiplina, 0) + 1

        if topiku_atividade and topiku_atividade != 'N/A': # New: Add to unique topiku set
            unique_topiku_set.add(topiku_atividade)

        if nivel_eskola and nivel_eskola != 'N/A':
            school_level_counts[nivel_eskola] = school_level_counts.get(nivel_eskola, 0) + 1

        # Increment count for Munisipiu and Naran Eskola combination
        if munisipiu != 'N/A' and naran_eskola != 'N/A':
            school_municipality_counts[munisipiu][naran_eskola] += 1

        # --- Process each student (Kanorin) individually for detailed table ---
        for k in range(1, 4): # Loop for Kanorin 1, 2, 3
            kanorin_name_col_key = f"NARAN_KANORIN_{k}"
            kanorin_sex_col_key = f"SEKSU_{k}"
            kanorin_age_col_key = f"IDADE_{k}"

            kanorin_name_index = column_mapping.get(kanorin_name_col_key)
            kanorin_sex_index = column_mapping.get(kanorin_sex_col_key)
            kanorin_age_index = column_mapping.get(kanorin_age_col_key)

            naran_kanorin = row[kanorin_name_index].strip() if kanorin_name_index is not None and len(row) > kanorin_name_index else ''
            seksu = row[kanorin_sex_index].strip() if kanorin_sex_index is not None and len(row) > kanorin_sex_index else ''
            idade = row[kanorin_age_index].strip() if kanorin_age_index is not None and len(row) > kanorin_age_index else ''

            if naran_kanorin: # Only create a new row if student name exists
                # Update gender counts
                if seksu and seksu != 'N/A':
                    gender_counts[seksu] = gender_counts.get(seksu, 0) + 1

                # Update age distribution
                if idade and idade != 'N/A':
                    try:
                        idade_int = int(float(idade))
                        age_distribution[str(idade_int)] = age_distribution.get(str(idade_int), 0) + 1
                    except (ValueError, TypeError):
                        pass

                processed_rows.append({
                    "id": f"{i}-{k}", # Unique ID for each student row
                    "Timestamp": timestamp,
                    "Munisipiu": munisipiu,
                    "Nivel Eskola": nivel_eskola,
                    "Naran Eskola": naran_eskola,
                    "Naran Kanorin": naran_kanorin,
                    "Seksu": seksu if seksu else 'N/A', # Use 'N/A' if empty
                    "Idade": idade if idade else 'N/A', # Use 'N/A' if empty
                    "Dixiplina": dixiplina,
                    "Titulu/Tópiku": topiku_atividade, # Add Titulu/Topiku here
                    "Dokumentus": dokumentus,
                })

    df = pd.DataFrame(processed_rows)

    total_municipality = len(unique_municipalities_set)
    total_disciplines_count = len(unique_disciplines_set)
    total_topiku_count = len(unique_topiku_set) # New: Calculate total unique topiku
    total_genders_count = sum(gender_counts.values()) # Total genders based on individual students

    print(f"\nDEBUG: Final unique_municipalities_set: {sorted(list(unique_municipalities_set))}")
    print(f"DEBUG: Final Calculated total_municipality: {total_municipality}")
    print(f"DEBUG: Final unique_disciplines_set: {sorted(list(unique_disciplines_set))}")
    print(f"DEBUG: Final Calculated total_disciplines_count: {total_disciplines_count}")
    print(f"DEBUG: Final unique_topiku_set: {sorted(list(unique_topiku_set))}") # New: Print debug for topiku
    print(f"DEBUG: Final Calculated total_topiku_count: {total_topiku_count}") # New: Print debug for topiku
    print(f"DEBUG: School Level Counts: {school_level_counts}")
    print(f"DEBUG: School-Municipality Counts (partial view): {dict(list(school_municipality_counts.items())[:2])}") # Print first 2 for brevity
    print("-" * 50)

    municipality_chart_labels = sorted(list(municipality_chart_counts.keys()))
    municipality_chart_data = [municipality_chart_counts[label] for label in municipality_chart_labels]

    # Prepare data for municipality bar chart (top 10 municipalities)
    sorted_municipalities = sorted(municipality_chart_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    municipality_bar_labels = [item[0] for item in sorted_municipalities]
    municipality_bar_data = [item[1] for item in sorted_municipalities]

    gender_chart_labels = sorted(list(gender_counts.keys()))
    gender_chart_data = [gender_counts[label] for label in gender_chart_labels]
    total_genders_for_chart = sum(gender_chart_data)
    gender_percentages = [f"{(count / total_genders_for_chart * 100):.1f}%" for count in gender_chart_data] if total_genders_for_chart > 0 else []

    age_chart_labels = sorted([int(k) for k in age_distribution.keys()])
    age_chart_data = [age_distribution[str(label)] for label in age_chart_labels]
    age_chart_labels = [str(label) for label in age_chart_labels]

    school_level_chart_labels = sorted(list(school_level_counts.keys()))
    school_level_chart_data = [school_level_counts[label] for label in school_level_counts.keys()]

    # Prepare data for the new School-Municipality-Total table
    school_municipality_table_data = []
    for mun, schools in school_municipality_counts.items():
        for school, total in schools.items():
            school_municipality_table_data.append({
                "Munisipiu": mun,
                "Naran Eskola": school,
                "Total": total
            })
    # Sort the new table data (e.g., by Munisipiu, then Naran Eskola)
    school_municipality_table_data = sorted(
        school_municipality_table_data,
        key=lambda x: (x['Munisipiu'], x['Naran Eskola'])
    )

    sorted_disciplines = sorted(discipline_chart_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    discipline_chart_labels = [item[0] for item in sorted_disciplines]
    discipline_chart_data = [item[1] for item in sorted_disciplines]

    all_nivel_eskola_options = sorted(df['Nivel Eskola'].unique().tolist()) if 'Nivel Eskola' in df.columns else []
    all_nivel_eskola_options.insert(0, 'All')

    all_munisipiu_options = sorted(df['Munisipiu'].unique().tolist()) if 'Munisipiu' in df.columns else []
    all_munisipiu_options.insert(0, 'All')

    # Detailed table data is already processed_rows
    detailed_table_data = processed_rows

    return {
        "totalMunicipality": total_municipality,
        "municipalityChartData": {"labels": municipality_chart_labels, "data": municipality_chart_data},
        "totalGender": total_genders_count,
        "genderChartData": {"labels": gender_chart_labels, "data": gender_chart_data, "percentages": gender_percentages},
        "ageDistribution": age_distribution,
        "ageChartData": {"labels": age_chart_labels, "data": age_chart_data},
        "schoolLevelCounts": school_level_counts,
        "schoolLevelChartData": {"labels": school_level_chart_labels, "data": school_level_chart_data},
        "schoolMunicipalityTableData": school_municipality_table_data, # Return new table data
        "totalDiscipline": total_disciplines_count,
        "disciplineCounts": discipline_chart_counts,
        "disciplineChartData": {"labels": discipline_chart_labels, "data": discipline_chart_data},
        "totalTopiku": total_topiku_count, # New: Add total topiku to returned data
        "allNivelEskolaOptions": all_nivel_eskola_options,
        "allMunisipiuOptions": all_munisipiu_options, # New: Return municipality options
        "detailedTableData": detailed_table_data,
        "municipalityPieChartData": {"labels": municipality_bar_labels, "data": municipality_bar_data}
    }

def generate_html_dashboard(dashboard_data, background_image_url=None):
    """
    Generates the complete HTML content for the dashboard.
    Includes embedded JavaScript for interactivity and Chart.js rendering.
    Adjusted for new school-municipality table and separated detailed records.
    Now includes an option for a background image.
    """
    dashboard_data_json = json.dumps(dashboard_data)

    # Conditional CSS for background image
    background_css = ""
    if background_image_url:
        background_css = f"""
            body {{
                background-image: url('{background_image_url}');
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
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LMSM 2025</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
        <style>
            body {{
                font-family: 'Inter', sans-serif;
            }}
            {background_css}
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
        </style>
    </head>
    <body class="min-h-screen p-6 text-gray-800"> <header class="text-center mb-10">
            <h1 class="text-5xl font-extrabold text-indigo-600 mb-2 rounded-lg p-2 shadow-sm">
                Relatóriu Atuál Progresu Rejistrasaun Selebrasaun LMSM 2025
            </h1>
            <p class="text-lg font-extrabold text-indigo-700">SESIM-KNTLU</p>
        </header>

        <section class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8"> <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 transform hover:-translate-y-1 flex flex-col items-center justify-center">
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
                <h2 class="text-2xl font-bold text-indigo-500 mb-3">📚 Tópiku LMSM</h2> <p id="totalTopiku" class="text-5xl font-extrabold text-purple-600"></p>
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
            // Register Chart.js Datalabels plugin globally
            Chart.register(ChartDataLabels);

            // Embed the processed data directly into a JavaScript variable
            const dashboardData = {dashboard_data_json};

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
                                position: 'bottom',
                                labels: {{
                                    font: {{ size: 12 }}
                                }}
                            }},
                            datalabels: {{
                                formatter: (value, ctx) => {{
                                    let sum = 0;
                                    let dataArr = ctx.chart.data.datasets[0].data;
                                    dataArr.map(data => {{
                                        sum += data;
                                    }});
                                    let percentage = (value * 100 / sum).toFixed(1) + '%';
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

            function renderCharts() {{
                // Gender Chart (still Pie)
                createPieChart(
                    'genderChart',
                    '',
                    dashboardData.genderChartData.labels,
                    dashboardData.genderChartData.data
                );

                // Age Chart (still Bar)
                createBarChart(
                    'ageChart',
                    '',
                    dashboardData.ageChartData.labels,
                    dashboardData.ageChartData.data
                );

                // School Level Chart (CHANGED TO PIE CHART as requested)
                createPieChart(
                    'schoolLevelChart',
                    '',
                    dashboardData.schoolLevelChartData.labels,
                    dashboardData.schoolLevelChartData.data
                );

                // Discipline Chart (still Bar)
                createBarChart(
                    'disciplineChart',
                    '',
                    dashboardData.disciplineChartData.labels,
                    dashboardData.disciplineChartData.data
                );

                // Municipality Chart (CHANGED TO BAR CHART as requested)
                createBarChart(
                    'municipalityChart',
                    '',
                    dashboardData.municipalityPieChartData.labels,
                    dashboardData.municipalityPieChartData.data
                );
            }}

            function renderSchoolMunicipalityTable() {{
                const tableBody = document.getElementById('schoolMunicipalityTableBody');
                tableBody.innerHTML = ''; // Hamoos liña sira ne'ebé eziste

                if (dashboardData.schoolMunicipalityTableData.length > 0) {{
                    dashboardData.schoolMunicipalityTableData.forEach(row => {{
                        tableBody.innerHTML += `
                            <tr class="hover:bg-gray-50 transition-colors duration-150">
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${{row.Munisipiu}}</td>
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${{row['Naran Eskola']}}</td>
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${{row.Total}}</td>
                            </tr>
                        `;
                    }});
                }} else {{
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="3" class="px-4 py-2 text-center text-gray-500">
                                La-iha dadus eskola ne'ebé disponivel.
                            </td>
                        </tr>
                    `;
                }}
            }}


            function renderDetailedTable() {{
                const tableContainer = document.getElementById('detailed-table-container');
                let filteredData = dashboardData.detailedTableData;

                // Apply Nivel Eskola Filter
                if (currentNivelEskolaFilter !== 'All') {{
                    filteredData = filteredData.filter(row => row['Nivel Eskola'] === currentNivelEskolaFilter);
                }}

                // Apply Munisipiu Filter (NEW)
                if (currentMunisipiuFilter !== 'All') {{
                    filteredData = filteredData.filter(row => row['Munisipiu'] === currentMunisipiuFilter);
                }}

                // Apply Search Filter
                if (currentSearchTerm) {{
                    const searchTermLower = currentSearchTerm.toLowerCase();
                    filteredData = filteredData.filter(row =>
                        Object.values(row).some(value =>
                            String(value).toLowerCase().includes(searchTermLower)
                        )
                    );
                }}

                // Pagination
                const totalPages = rowsPerPage === 'All' ? 1 : Math.ceil(filteredData.length / rowsPerPage);
                const startIndex = rowsPerPage === 'All' ? 0 : (currentPage - 1) * rowsPerPage;
                const endIndex = rowsPerPage === 'All' ? filteredData.length : startIndex + parseInt(rowsPerPage);
                const paginatedData = filteredData.slice(startIndex, endIndex);

                let tableHtml = `
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead>
                            <tr>
                                <th scope="col">Timestamp</th>
                                <th scope="col">Munisipiu</th>
                                <th scope="col">Nivel Eskola</th>
                                <th scope="col">Naran Eskola</th>
                                <th scope="col">Naran Kanorin</th>
                                <th scope="col">Seksu</th>
                                <th scope="col">Idade</th>
                                <th scope="col">Dixiplina</th>
                                <th scope="col">Títulu/Tópiku</th>
                                <th scope="col">Dokumentu</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-100">
                `;

                if (paginatedData.length > 0) {{
                    paginatedData.forEach(row => {{
                        tableHtml += `
                            <tr class="hover:bg-gray-50 transition-colors duration-150">
                                <td>${{row.Timestamp}}</td>
                                <td>${{row.Munisipiu}}</td>
                                <td>${{row['Nivel Eskola']}}</td>
                                <td>${{row['Naran Eskola']}}</td>
                                <td>${{row['Naran Kanorin']}}</td>
                                <td>${{row.Seksu}}</td>
                                <td>${{row.Idade}}</td>
                                <td>${{row.Dixiplina}}</td>
                                <td>${{row['Titulu/Tópiku']}}</td>
                                <td>${{row.Dokumentus}}</td>
                            </tr>
                        `;
                    }});
                }} else {{
                    tableHtml += `
                        <tr>
                            <td colspan="10" class="px-6 py-4 text-center text-gray-500">
                                La-iha dadus ne'ebé disponivel aliña ho filtrasaun atuál.
                            </td>
                        </tr>
                    `;
                }}

                tableHtml += `
                        </tbody>
                    </table>
                `;
                tableContainer.innerHTML = tableHtml;

                updatePaginationControls(totalPages, filteredData.length);
            }}

            function updatePaginationControls(totalPages, totalFilteredRows) {{
                document.getElementById('currentPageSpan').textContent = currentPage;
                document.getElementById('totalPagesSpan').textContent = totalPages;

                document.getElementById('prevPage').disabled = currentPage === 1;
                document.getElementById('nextPage').disabled = currentPage === totalPages || totalPages === 0 || rowsPerPage === 'All';

                // Ensure current page doesn't exceed total pages after filtering
                if (currentPage > totalPages && totalPages > 0) {{
                    currentPage = totalPages;
                    renderDetailedTable();
                }} else if (totalPages === 0) {{
                    currentPage = 0; // No pages if no data
                    document.getElementById('currentPageSpan').textContent = 0;
                }}
            }}

            function renderFilterOptions() {{
                const nivelEskolaFilterSelect = document.getElementById('nivelEskolaFilter');
                nivelEskolaFilterSelect.innerHTML = ''; // Hamoos Opsaun sira ne'ebé eziste

                dashboardData.allNivelEskolaOptions.forEach(option => {{
                    const optElement = document.createElement('option');
                    optElement.value = option;
                    optElement.textContent = option;
                    nivelEskolaFilterSelect.appendChild(optElement);
                }});

                // Set initial filter value and render table
                nivelEskolaFilterSelect.value = 'All';
                currentNivelEskolaFilter = 'All'; // Initialize filter state


                const munisipiuFilterSelect = document.getElementById('munisipiuFilter'); // NEW: Get Munisipiu filter element
                munisipiuFilterSelect.innerHTML = ''; // Clear existing options

                dashboardData.allMunisipiuOptions.forEach(option => {{ // NEW: Populate Munisipiu options
                    const optElement = document.createElement('option');
                    optElement.value = option;
                    optElement.textContent = option;
                    munisipiuFilterSelect.appendChild(optElement);
                }});

                munisipiuFilterSelect.value = 'All'; // NEW: Set initial Munisipiu filter
                currentMunisipiuFilter = 'All'; // NEW: Initialize Munisipiu filter state

                currentPage = 1; // Reset page on any filter change
                renderDetailedTable(); // Render table with initial filters

                // Add event listener for Nivel Eskola filter changes
                nivelEskolaFilterSelect.addEventListener('change', (event) => {{
                    currentNivelEskolaFilter = event.target.value;
                    currentPage = 1; // Reset page on filter change
                    renderDetailedTable();
                }});

                // Add event listener for Munisipiu filter changes (NEW)
                munisipiuFilterSelect.addEventListener('change', (event) => {{
                    currentMunisipiuFilter = event.target.value;
                    currentPage = 1; // Reset page on filter change
                    renderDetailedTable();
                }});
            }}

            // Initialize dashboard on page load
            document.addEventListener('DOMContentLoaded', () => {{
                // Display total counts
                document.getElementById('totalMunicipality').textContent = dashboardData.totalMunicipality;
                document.getElementById('totalGender').textContent = dashboardData.totalGender;
                document.getElementById('totalDiscipline').textContent = dashboardData.totalDiscipline;
                document.getElementById('totalTopiku').textContent = dashboardData.totalTopiku;

                renderCharts();
                renderSchoolMunicipalityTable();
                renderFilterOptions(); // This also triggers initial renderDetailedTable

                // Event Listeners for Search and Pagination
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
    return html_content

# --- Main execution ---
if __name__ == "__main__":
    # Google Sheet details
    SPREADSHEET_ID = '1MYTD8Z_F408OPRSJos8JWS_0tgvM9Dmo6wlVKfZjrmM'
    # Your API key from the provided information
    API_KEY = "AIzaSyAirZPcce-sRKU1DRdshlzjz07PkRPgwEQ"
    SHEET_NAME = 'dadus'

    # --- Background Image Configuration ---
    # To change the background image, modify this variable to one of the following:
    # "AY1A8030.jpg"
    # "AY1A8072.jpg"
    # "AY1A8051.jpg"
    # Make sure the image file is in the same directory as your dashboard.html
    BACKGROUND_IMAGE_FILENAME = "AY1A8030.jpg"
    # Set to None if you don't want a background image
    # BACKGROUND_IMAGE_FILENAME = None

    # Column mapping (adjust these indices based on your actual sheet)
    # These indices are 0-based. For example, column A is 0, B is 1, C is 2, etc.
    # YOU MUST VERIFY THESE INDICES WITH YOUR ACTUAL GOOGLE SHEET COLUMNS.
    COLUMN_MAPPING = {
        "TIMESTAMP": 0,
        "EMAIL_ADDRESS": 1,
        "MUNISIPIU": 2,
        "NIVEL_ESKOLA": 3,
        "NARAN_ESKOLA": 4,
        "DIXIPLINA": 5,
        "TITULU_TOPIKU_ATIVIDADE": 6,

        # Naran Kompleitu (Student Name)
        "NARAN_KANORIN_1": 7,
        "NARAN_KANORIN_2": 14,
        "NARAN_KANORIN_3": 21,

        # Seksu (Gender)
        "SEKSU_1": 8,
        "SEKSU_2": 15,
        "SEKSU_3": 22,

        # Idade (Age)
        "IDADE_1": 9,
        "IDADE_2": 16,
        "IDADE_3": 23,

        "DOKUMENTUS": 28,
    }

    try:
        data = fetch_google_sheet_data(SPREADSHEET_ID, SHEET_NAME, API_KEY)
        dashboard_results = process_data(data, COLUMN_MAPPING)

        # CORRECTED LINE: Call generate_html_dashboard and store its result
        html_output = generate_html_dashboard(dashboard_results, BACKGROUND_IMAGE_FILENAME)

        output_file = "index.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_output)
        print(f"Dashboard generated successfully: {os.path.abspath(output_file)}")

    except Exception as e:
        print(f"An error occurred during dashboard generation: {e}")

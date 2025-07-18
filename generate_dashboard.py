import requests
import pandas as pd
import os

# --- Step 1: Securely get the API key from the environment variable ---
# This is the correct way to get the key from the GitHub Secret.
# When run locally, you will need to set this environment variable.
api_key = os.getenv("GOOGLE_SHEET_API_KEY")

# Replace with your actual Google Sheet ID
sheet_id = '1MYTD8Z_F408OPRSJos8JWS_0tgvM9Dmo6wlVKfZjrmM' # Replace with your Sheet ID if it's different

# --- Step 2: Fetch data from the Google Sheets API ---
total_topics = "N/A" # Default value in case of error
try:
    # Your existing code to fetch data goes here.
    # The API key is now passed from the environment variable.
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/dadus?key={api_key}"
    response = requests.get(url)
    response.raise_for_status() # This will raise an HTTPError for bad responses (4xx or 5xx)
    data = response.get('values', [])
    
    if data: # Ensure data is not empty
        df = pd.DataFrame(data[1:], columns=data[0])
        # Calculate the total number of topics
        total_topics = len(df)
    else:
        total_topics = "No data found"
    
except requests.exceptions.RequestException as e:
    print(f"Error fetching data: {e}")
    total_topics = "Error fetching data"
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    total_topics = "Error"

# --- Step 3: Generate the HTML content with PDF download functionality ---
# Include jsPDF and html2canvas libraries via CDN
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>LMSM Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            margin: 20px;
            padding: 20px;
            background-color: #f0f2f5;
            color: #333;
            text-align: center;
        }}
        .dashboard-container {{
            background-color: #ffffff;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            max-width: 800px;
            margin: 30px auto;
            position: relative; /* Needed for html2canvas to capture correctly */
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 2.5em;
        }}
        p {{
            font-size: 1.1em;
            line-height: 1.6;
            margin-bottom: 10px;
        }}
        .button-container {{
            margin-top: 30px;
            display: flex;
            justify-content: center;
            gap: 20px;
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
<body>
    <div class="dashboard-container" id="dashboardContent">
        <h1>LMSM Dashboard 2025</h1>
        <p>Relatóriu atual progresu rejistrasaun Selebraun LMSM 2025, SESIM-KNTLU</p>
        <p>Total topics: <strong>{total_topics}</strong></p>
    </div>

    <div class="button-container">
        <!-- Original HTML download link -->
        <a href="index.html" download="lmsm-dashboard.html" class="download-button">Download HTML</a>

        <!-- New PDF download button -->
        <button class="download-button" onclick="downloadPdf()">Download as PDF</button>
    </div>

    <script>
        // Define the password for PDF editing (basic deterrent only)
        const PDF_EDIT_PASSWORD = 'your_strong_edit_password'; // <--- CHANGE THIS PASSWORD!

        async function downloadPdf() {{
            const {{ jsPDF }} = window.jspdf;
            const dashboardContent = document.getElementById('dashboardContent');

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
            }});
        }}
    </script>
</body>
</html>
"""

# --- Step 4: Write the HTML content to the index.html file ---
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Dashboard generated successfully.")

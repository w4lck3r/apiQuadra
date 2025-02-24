from flask import Flask, request, send_file
import os
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pysftp
from flasgger import Swagger, swag_from

app = Flask(__name__)

# Add Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,  # all in
            "model_filter": lambda tag: True,  # all in
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}

swagger_template = {
    "info": {
        "title": "File Processing API",
        "description": "API for processing and managing financial data files",
        "version": "1.0.0"
    }
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'

MAIN_RESULTS_FILE = os.path.join(RESULTS_FOLDER, 'main_results.txt')

PROCESSED_FILES_FILE = 'processed_files.txt'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

current_account = None

# SFTP credentials and configuration
SFTP_HOST = 'localhost'  # Remove http:// prefix
SFTP_USERNAME = 'user'
SFTP_PASSWORD = 'password'
SFTP_REMOTE_PATH = '/pub/main_results.txt'

# Ensure the main results file exists
if not os.path.exists(MAIN_RESULTS_FILE):
    open(MAIN_RESULTS_FILE, 'w').close()

# Read processed files from the file
def load_processed_files():
    """
    Read the list of processed files from PROCESSED_FILES_FILE.
    
    Returns:
        set: Set of processed file names
    """
    if os.path.exists(PROCESSED_FILES_FILE):
        with open(PROCESSED_FILES_FILE, 'r') as f:
            return set(f.read().splitlines())
    return set()

# Write processed files to the file
def save_processed_files():
    """Save the current set of processed files to PROCESSED_FILES_FILE."""
    with open(PROCESSED_FILES_FILE, 'w') as f:
        for file_name in processed_files:
            f.write(file_name + '\n')

# Track processed files
processed_files = load_processed_files()

# Helper functions
def create_m_line(type_line, numero_compte, code_journal_2, folio, date_ecriture, code_lib, sens, montant, date_echeance, code_devise, code_journal_3, libelle):
    """
    Create a formatted M-type line for financial data.
    
    Args:
        type_line (str): Line type identifier
        numero_compte (str): Account number
        code_journal_2 (str): Journal code 2
        folio (str): Folio number
        date_ecriture (str): Writing date
        code_lib (str): Library code
        sens (str): Direction indicator
        montant (int): Amount
        date_echeance (str): Due date
        code_devise (str): Currency code
        code_journal_3 (str): Journal code 3
        libelle (str): Description
    
    Returns:
        str: Formatted M-type line
    """
    return (
        f'{type_line:<1}'
        f'{numero_compte:<8}'
        f'{code_journal_2:<2}'
        f'{folio:<3}'
        f'{date_ecriture:<6}'
        f'{code_lib:<1}'
        f'{" " * 20}'
        f'{sens:<1}'
        f'{montant:013d}'
        f'{" " * 8}'
        f'{date_echeance:<6}'
        f'{" " * 38}'
        f'{code_devise:<3}'
        f'{code_journal_3:<3}'
        f'{" " * 3}'
        f'{libelle:<30}'
        f'{" " * 85}'
    )

def create_i_line(type_line, repartition_percent, montant_repartition, code_centre):
    """
    Create a formatted I-type line for financial data.
    
    Args:
        type_line (str): Line type identifier
        repartition_percent (str): Distribution percentage
        montant_repartition (int): Distribution amount
        code_centre (str): Center code
    
    Returns:
        str: Formatted I-type line
    """
    return (
        f'{type_line:<1}'
        f'{repartition_percent:<5}'
        f'{montant_repartition:013d}'
        f'{code_centre:<3}'
        f'{" " * 10}'
    )

def regrouper_fichier(input_file, output_file):
    """
    Process and group financial data from input file to output file.
    
    Args:
        input_file (str): Path to input file
        output_file (str): Path to output file
    """
    comptes = defaultdict(lambda: {
        'total_montant': 0,
        'code_centre': '',
        'lines': []
    })

    first_m_line = None
    first_r_line = None
    result_lines = []

    with open(input_file, 'r') as f:
        lignes = f.readlines()

    for i, ligne in enumerate(lignes):
        type_ligne = ligne[0]

        if type_ligne == 'M':
            numero_compte = ligne[1:9].strip()
            montant_str = ligne[42:55].strip()

            try:
                montant = int(montant_str)
            except ValueError:
                print(f"Erreur de conversion du montant: '{montant_str}' sur la ligne {i}")
                montant = 0

            if first_m_line is None:
                first_m_line = ligne
                result_lines.append(ligne.strip())  # Retain the first M line unchanged
                continue

            comptes[numero_compte]['total_montant'] += montant
            comptes[numero_compte]['lines'].append(ligne.strip())
            # Store the current account number for the following I line
            current_account = numero_compte
        elif type_ligne == 'R':
            if first_r_line is None:
                first_r_line = ligne
                result_lines.append(ligne.strip())  # Retain the first R line unchanged
                continue

        elif type_ligne == 'I':
            code_centre = ligne[19:22].strip()
            print(f"Debug - Processing I line - Full line: '{ligne}'")
            print(f"Debug - Extracted code_centre: '{code_centre}' from positions 19-22")
            
            # Use the account number from the preceding M line
            if current_account in comptes:
                comptes[current_account]['code_centre'] = code_centre
                print(f"Debug - Stored code_centre '{code_centre}' for account {current_account}")

    # Process grouped accounts
    for numero_compte, data in comptes.items():
        if data['total_montant'] > 0:
            # Use the first line of the group as a template
            sample_line = data['lines'][0]
            code_journal_2 = sample_line[9:11].strip()
            folio = sample_line[11:14].strip()
            date_ecriture = sample_line[14:20].strip()
            code_lib = sample_line[20:21].strip()
            sens = sample_line[41:42].strip()
            date_echeance = sample_line[63:69].strip()
            code_devise = sample_line[107:110].strip()
            code_journal_3 = sample_line[110:113].strip()
            libelle = sample_line[116:146].strip()

            # Create grouped M line with total montant
            grouped_m_line = create_m_line(
                type_line='M',
                numero_compte=numero_compte,
                code_journal_2=code_journal_2,
                folio=folio,
                date_ecriture=date_ecriture,
                code_lib=code_lib,
                sens=sens,
                montant=data['total_montant'],
                date_echeance=date_echeance,
                code_devise=code_devise,
                code_journal_3=code_journal_3,
                libelle=libelle
            )
            result_lines.append(grouped_m_line)

            # Create corresponding I line, reflecting the sum of the amounts
            i_line = create_i_line(
                type_line='I',
                repartition_percent='10000',
                montant_repartition=data['total_montant'],
                code_centre=data['code_centre']
            )
            print(f"Debug - Creating I line for account {numero_compte} with code_centre: '{data['code_centre']}'")
            print(f"Debug - Generated I line: '{i_line}'")
            result_lines.append(i_line)

    # Write the result to the output file
    with open(output_file, 'w') as f_out:
        for line in result_lines:
            f_out.write(line + "\n")

# Append results from all unprocessed files
def weekly_append_results():
    """
    Append unprocessed results to main results file and upload to SFTP server.
    Runs on a scheduled basis to consolidate all new results.
    """
    global processed_files
    print(f"Running weekly append task at {datetime.now()}...")

    for file_name in os.listdir(RESULTS_FOLDER):
        if file_name.startswith('results_') and file_name not in processed_files:
            result_path = os.path.join(RESULTS_FOLDER, file_name)

            # Append to the main results file
            with open(result_path, 'r') as res_file:
                with open(MAIN_RESULTS_FILE, 'a') as main_file:
                    main_file.write(res_file.read())
                    #main_file.write("\n")  # Add a new line after appending each file (NO need to leave a new line after writing)

            # Mark the file as processed
            processed_files.add(file_name)

    # Save the updated list of processed files
    save_processed_files()

    print("Weekly append task completed.")
    
    # Upload the main_results.txt to the SFTP server
    try:
        print("Uploading the main_results.txt to the SFTP server...")
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None  # Disable host key checking for testing
        with pysftp.Connection(
            SFTP_HOST, 
            username=SFTP_USERNAME, 
            password=SFTP_PASSWORD,
            port=8880,
            cnopts=cnopts
        ) as sftp:
            sftp.cwd(os.path.dirname(SFTP_REMOTE_PATH))
            sftp.put(MAIN_RESULTS_FILE, os.path.basename(SFTP_REMOTE_PATH))
        print(f"File successfully uploaded to {SFTP_REMOTE_PATH}")
    except Exception as e:
            print(f"Failed to upload file to SFTP server: {e}")

# Flask routes
@app.route('/process', methods=['POST'])
@swag_from({
    'tags': ['File Processing for QuadraCompta'],
    'summary': 'Process a single file',
    'description': 'Upload a file for processing and receive the processed result file',
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'File to be processed : Facture/Avoir'
        }
    ],
    'responses': {
        '200': {
            'description': 'File processed successfully',
            'content': {
                'application/octet-stream': {
                    'schema': {
                        'type': 'string',
                        'format': 'binary'
                    }
                }
            }
        },
        '400': {
            'description': 'No file provided or void file'
        }
    }
})
def process_file():
    """
    Process a single uploaded file and return the processed result.
    
    Returns:
        tuple: (File or error message, HTTP status code)
    """
    if 'file' not in request.files:
        return "No file provided", 400

    file = request.files['file']
    if file.filename == '':
        return "Void file", 400

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    result_path = os.path.join(RESULTS_FOLDER, f'results_{os.path.basename(file.filename)}')
    file.save(input_path)

    regrouper_fichier(input_path, result_path)

    return send_file(result_path, as_attachment=True)

@app.route('/append_results', methods=['POST'])
@swag_from({
    'tags': ['File Processing for QuadraCompta'],
    'summary': 'Proccess the file and append its results to the main results file',
    'description': 'This endpoint processes the uploaded file and appends its results to the main results file.',
    'parameters': [
        {
            'name': 'Facture/Avoir',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'File to be processed and appended'
        }
    ],
    'responses': {
        '200': {
            'description': 'Results successfully appended',
            'schema': {
                'type': 'string'
            }
        },
        '400': {
            'description': 'No file provided or no file selected'
        }
    }
})
def append_results():
    """
    Process an uploaded file and append its results to the main results file.
    
    Returns:
        tuple: (Success/error message, HTTP status code)
    """
    if 'file' not in request.files:
        return "No file provided", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    input_path  = os.path.join(UPLOAD_FOLDER, file.filename)
    result_path = os.path.join(RESULTS_FOLDER, f'results_{file.filename}')
    file.save(input_path)

    regrouper_fichier(input_path, result_path)

    with open(result_path, 'r') as res_file:
        with open(MAIN_RESULTS_FILE, 'a') as main_file:
            main_file.write(res_file.read())
            #main_file.write("\n")  # Add a new line after appending the file

    return f"Results appended to {MAIN_RESULTS_FILE}", 200

# Start the scheduler
scheduler = BackgroundScheduler()
#scheduler.add_job(weekly_append_results, 'cron', day_of_week='fri', hour=19, minute=0, timezone='UTC')
scheduler.add_job(weekly_append_results, 'interval', minutes=4)
scheduler.start()

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()






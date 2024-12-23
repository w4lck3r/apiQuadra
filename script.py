from flask import Flask, request, send_file
import os
from collections import defaultdict

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Helper functions to create lines
def create_m_line(type_line, numero_compte, code_journal_2, folio, date_ecriture, code_lib, sens, montant, date_echeance, code_devise, code_journal_3, libelle):
    return (
        f'{type_line:<1}'                     # Type
        f'{numero_compte:<8}'                 # Numéro de compte
        f'{code_journal_2:<2}'                # Code journal (2 characters)
        f'{folio:<3}'                         # Numéro de folio
        f'{date_ecriture:<6}'                 # Date écriture
        f'{code_lib:<1}'                      # Code libllée (A/F)
        f'{" " * 20}'                        # Unused space
        f'{sens:<1}'                          # Sens (D/C)
        f'{montant:013d}'                     # Montant en centimes (13 digits for correct format)
        f'{" " * 8}'                         # Unused space
        f'{date_echeance:<6}'                 # Date échéance
        f'{" " * 38}'                        # Unused space
        f'{code_devise:<3}'                   # Code devise
        f'{code_journal_3:<3}'                # Code journal (3 characters)
        f'{" " * 3}'
        f'{libelle:<30}'                      # Libellé écriture
        f'{" " * 85}'                       # Unused space
    )

def create_i_line(type_line, repartition_percent, montant_repartition, code_centre):
    return (
        f'{type_line:<1}'                     # Type
        f'{repartition_percent:<5}'           # Pourcentage de répartition
        f'{montant_repartition:013d}'         # Montant répartition (13 digits for correct format)
        f'{code_centre:<10}'                  # Code centre
        f'{" " * 10}'                        # Unused space
    )

def regrouper_fichier(input_file, output_file):
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

        elif type_ligne == 'R':
            if first_r_line is None:
                first_r_line = ligne
                result_lines.append(ligne.strip())  # Retain the first R line unchanged
                continue

        elif type_ligne == 'I':
            numero_compte = ligne[1:9].strip()
            code_centre = ligne[19:29].strip()
            comptes[numero_compte]['code_centre'] = code_centre

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
            result_lines.append(i_line)

    # Write the result to the output file
    with open(output_file, 'w') as f_out:
        for line in result_lines:
            f_out.write(line + "\n")

# Flask route for processing files
@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return "No file provided", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    result_path = os.path.join(RESULTS_FOLDER, f'results_{file.filename}')
    file.save(input_path)

    regrouper_fichier(input_path, result_path)

    return send_file(result_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
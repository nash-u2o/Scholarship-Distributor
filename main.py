# Note on the dictionary created: if identifiers are the same, the existing/old value is overidden
# Note on unrestricted in the excel file: don't use it unless you want to create logic using custom matching. In the excel file, just make all cells with unrestricted empty
# BUG: This works but there is bug when columns have the same name. If I compare scholarship column a to student column b, but student also has a column named the same as a, this will cause the program to crash

import csv
import os
import re
import traceback
import warnings

import networkx as nx
import pandas as pd
from networkx import max_weight_matching


def preprocess_scholarships(
    identifier: str,
    amount_identifier: str,
    data: pd.DataFrame,
    compare_dict: dict,
) -> dict:
    """
    Creates a dictionary of scholarship requirements
    """

    # Fill nan columns with empty space
    # Deal with deprecation warning
    data.fillna(value="", inplace=True)

    rows = data.iterrows()
    scholarships = {}

    for index, row in rows:
        if int(row[amount_identifier]) <= 0:
            continue
        schol_identifier = row[identifier]

        scholarships[schol_identifier] = {}
        scholarships[schol_identifier][amount_identifier] = row[amount_identifier]
        # Key is not very aptly named. It is simply a column chosen for comparison by the user
        for key in compare_dict.keys():
            # If attribute in scholarship exists
            if row[key] != "":
                if isinstance(row[key], (int, float)):
                    scholarships[schol_identifier][key] = row[key]
                    continue
                else:
                    qualifications = [x.strip() for x in row[key].split(",")]

                    # If matching is custom, substitute the values
                    substituted_qualifications = []
                    if compare_dict[key]["comparison"] == "custom":
                        custom_keys = compare_dict[key]["custom_comparison"].keys()
                        for qual in qualifications:
                            if qual in custom_keys:
                                substituted_qualifications.extend(
                                    compare_dict[key]["custom_comparison"][qual]
                                )
                            else:
                                substituted_qualifications.append(qual)
                        scholarships[schol_identifier][key] = substituted_qualifications
                    else:
                        scholarships[schol_identifier][key] = qualifications

    return scholarships


def preprocess_students(
    identifier: str, cap_identifier: str, compare_dict: dict, data: pd.DataFrame
) -> dict:
    # Fill nan columns with empty space
    data.fillna(
        value="", inplace=True
    )  # Just ignore the deprecation warning until it's actually a problem
    rows = data.iterrows()
    students = {}

    for index, row in rows:
        student_identifier = row[identifier]
        students[student_identifier] = {}
        students[student_identifier][cap_identifier] = row[cap_identifier]

        relevant_attributes = compare_dict.keys()
        for attr in relevant_attributes:
            students[student_identifier][attr] = row[attr]

    return students


""""
For reference, this is what data inside of compare_dict looks like:
"scholarship_column_name": {
    "student_column": "corresponding_student_column_name",
    "comparison": "comparison_type",
    # Only present if comparison type is "custom"
    "custom_comparison": {
        "key_value": ["matching_value1", "matching_value2", ...],
        # More key-value pairs...
    }

This is what schol_dict looks like:
"scholarship_identifier_1": {
    "amount_identifier": amount_value,
    "comparison_column_1": [
        # For "exact" comparison:
        ["value1", "value2", "value3"],
        # OR for "custom" comparison:
        [
            ["matching_value1", "matching_value2", ...], 
        ]
    ],
    "comparison_column_2": [...],
    # More comparison columns...
"""


def custom_matching(
    stu_dict,
    student,
    schol_dict,
    scholarship,
    attribute,
):
    custom_matchings = [x.lower().strip() for x in schol_dict[scholarship][attribute]]
    student_val = stu_dict[student][attribute].lower().strip()
    if student_val in custom_matchings:
        return True
    return False


# Potential bug: Student and Scholarship have same identifiers. Stupid but technically possible
def create_nodes(
    stu_dict: dict,
    schol_dict: dict,
) -> nx.Graph:
    graph = nx.Graph()
    for student in stu_dict:
        graph.add_node(student)
    for scholarship in schol_dict:
        graph.add_node(scholarship)
    return graph


def create_edges(
    stu_dict: dict,
    cap_identifier: str,
    schol_dict: dict,
    amount_identifier: str,
    compare_dict: dict,
    graph: nx.Graph,
) -> list[nx.Graph]:
    columns = compare_dict.keys()

    for scholarship in schol_dict:
        for student in stu_dict:
            qualified = True  # Assume the pair is qualified initially

            for col in columns:
                if col in schol_dict[scholarship].keys():
                    student_val = stu_dict[student][col]
                    scholarship_values = schol_dict[scholarship][col]

                    # Custom comparison
                    if compare_dict[col]["comparison"] == "custom":
                        qualified = custom_matching(
                            stu_dict, student, schol_dict, scholarship, col
                        )
                        if not qualified:
                            break  # Disqualify immediately

                    # Greater comparison
                    elif compare_dict[col]["comparison"] == "greater":
                        try:
                            if float(student_val) < float(scholarship_values):
                                qualified = False
                                break  # Disqualify immediately
                        except ValueError:
                            qualified = False
                            break

                    # Lesser comparison
                    elif compare_dict[col]["comparison"] == "lesser":
                        try:
                            if float(student_val) > float(scholarship_values):
                                qualified = False
                                break  # Disqualify immediately
                        except ValueError:
                            qualified = False
                            break

                    # Exact comparison
                    else:  # Default to "exact"
                        if isinstance(scholarship_values, list):
                            if student_val not in scholarship_values:
                                qualified = False
                                break  # Disqualify immediately
                        else:
                            if student_val != scholarship_values:
                                qualified = False
                                break  # Disqualify immediately

            # If qualified, add an edge to the graph
            if qualified:
                scholarship_amount = schol_dict[scholarship][amount_identifier]
                remaining_student_scholarship = stu_dict[student][cap_identifier]
                weight = min(scholarship_amount, remaining_student_scholarship)

                graph.add_edge(
                    student,
                    scholarship,
                    weight=weight,
                )

    # Remove isolated nodes (nodes with no edges)
    isolated_nodes = list(nx.isolates(graph))
    graph.remove_nodes_from(isolated_nodes)

    # Create subgraphs
    components = nx.connected_components(graph)
    subgraphs = [graph.subgraph(c).copy() for c in components]

    return subgraphs


def save_csv(headers, data, name: str):
    i = 0
    while True:
        file_str = f"{name}.csv" if i == 0 else f"{name}({i}).csv"
        if not os.path.exists(file_str):
            with open(file_str, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(headers)
                writer.writerows(data)
            break
        else:
            i += 1


import os
import re
import traceback

import pandas as pd


def load_file(
    path: str, custom=False
) -> pd.DataFrame | None:  # Added None to return type hint
    path = re.sub('["]', "", path)
    file_extension = ""
    if "." in path:
        file_extension = path[path.rfind(".") + 1 :]  # Use rfind for robustness

    try:
        data = None
        print(
            f"Attempting to load: {path} (Extension: {file_extension}, Custom: {custom})"
        )

        if "xls" in file_extension:  # Covers .xls and .xlsx
            if custom:
                data = pd.read_excel(path, header=None)
            else:
                data = pd.read_excel(path)  # Default header inference
        elif "csv" in file_extension:
            if custom:
                # Try common encodings for header=None case too
                try:
                    data = pd.read_csv(path, header=None)
                except UnicodeDecodeError:
                    try:
                        data = pd.read_csv(path, header=None, encoding="latin1")
                    except UnicodeDecodeError:
                        data = pd.read_csv(path, header=None, encoding="cp1252")
            else:
                # Try default UTF-8, then latin1, then cp1252
                try:
                    data = pd.read_csv(path)
                    print("Info: Successfully loaded with default UTF-8 encoding.")
                except UnicodeDecodeError:
                    print("Info: UTF-8 decoding failed. Trying 'latin1'...")
                    try:
                        data = pd.read_csv(path, encoding="latin1")
                        print("Info: Successfully loaded with 'latin1' encoding.")
                    except UnicodeDecodeError:
                        print("Info: 'latin1' decoding failed. Trying 'cp1252'...")
                        try:
                            data = pd.read_csv(path, encoding="cp1252")  # Try cp1252
                            print("Info: Successfully loaded with 'cp1252' encoding.")
                        except UnicodeDecodeError as ude_final:
                            # Re-raise if all common encodings fail
                            print(
                                "Error: All attempted encodings (UTF-8, latin1, cp1252) failed."
                            )
                            raise ude_final  # Re-raise the last error to be caught below
        else:
            print(f"Error: Unsupported file type '{file_extension}' for path: {path}")
            return None  # Return None for unsupported type

        # If data is successfully loaded by this point
        print("File loaded successfully into DataFrame.")
        return data

    # --- Exception Handling Block ---
    except FileNotFoundError:
        print(f"Error: File not found at the specified path: '{path}'")
        # traceback.print_exc() # Uncomment for full traceback if needed
        return None  # Return None on error
    except UnicodeDecodeError as ude:  # Catch the error if all CSV encodings failed
        print(f"Error: Final encoding issue loading CSV '{path}'.")
        print(f"Specific error: {ude}")
        # traceback.print_exc() # Uncomment for full traceback if needed
        return None  # Return None on error
    except Exception as e:
        # Catch any other unexpected exceptions during loading
        print(f"An unexpected error occurred while loading file: {path}")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        print("-" * 20 + " Full Traceback " + "-" * 20)
        traceback.print_exc()  # Print the full traceback
        print("-" * 54)
        return None  # Return None on error


# Need a way to identify column to identify students
""" TO DO:
* Process scholarship data. How will the comparisons be happening? Well, indexing a scholarship attribute should give acceptable student values
"""
if __name__ == "__main__":
    warnings.simplefilter(
        action="ignore", category=FutureWarning
    )  # Suppress the pandas warning

    schol_data = None
    stu_data = None

    # Load scholarship file
    while schol_data is None:
        schol_file_path = input("Enter scholarship file path: ")
        schol_data = load_file(schol_file_path)

    print()  # Add spacing between sections

    # Load student file
    while stu_data is None:
        stu_file_path = input("Enter student file path: ")
        stu_data = load_file(stu_file_path)

    # Make everything lowercase if it's a string
    schol_data = schol_data.map(lambda x: x.lower() if isinstance(x, str) else x)
    stu_data = stu_data.map(lambda x: x.lower() if isinstance(x, str) else x)

    schol_data.columns = [x.lower() for x in schol_data.columns]
    schol_columns = [x for x in schol_data.columns]
    stu_data.columns = [x.lower() for x in stu_data.columns]
    stu_columns = [x for x in stu_data.columns]
    compare_dict = {}

    print()  # Add spacing before the next section

    schol_identifier = ""
    amount_identifier = ""
    stu_identifier = ""
    cap_identifier = ""

    # Load the matching file
    match_path = input(
        "Provide comparison file for columns. Check the readme for more info on how to structure files for this program: "
    )

    print()

    match_data = load_file(match_path, True)
    match_data = match_data.map(lambda x: x.lower() if isinstance(x, str) else x)
    comparisons = ["exact", "greater", "lesser", "custom"]
    for _, row in match_data.iterrows():
        # row[0] is scholarship value, row[1] is student val, and row[2] is comparison type
        if row[2] == "id":
            schol_identifier = row[0]
            stu_identifier = row[1]
        elif row[2] == "value":
            amount_identifier = row[0]
            cap_identifier = row[1]
        else:
            if row[2] in comparisons:
                compare_dict[row[0]] = {"student_column": row[1]}
                compare_dict[row[0]]["comparison"] = row[2]
            else:
                print(f"{row[2]} is not a valid comparison type")
                quit(-1)

    if any(
        x == ""
        for x in [schol_identifier, amount_identifier, stu_identifier, cap_identifier]
    ):
        print(
            "Error. Please ensure the scholarship and student have both a value and id 'comparison' in the matching file"
        )
        quit(-1)

    for key in compare_dict.keys():
        comparison = compare_dict[key]["comparison"]

        if comparison == "custom":
            compare_dict[key]["custom_comparison"] = {}
            comparison_file = input(
                f"Provide the comparison file for the scholarship column '{key}': "
            )
            print()
            data = load_file(comparison_file, True)
            data.columns = ["scholarship", "student"]
            for index, row in data.iterrows():
                key_val = (
                    row["scholarship"].lower()
                    if isinstance(row["scholarship"], str)
                    else row["scholarship"]
                )
                values = [x.strip().lower() for x in str(row["student"]).split(",")]
                if (
                    row["scholarship"].lower() not in values
                ):  # Also add in the key itself to be safe
                    values.append(row["scholarship"].lower())
                compare_dict[key]["custom_comparison"][key_val] = values

    print()  # Add spacing before the next section

    # Rename columns in student data if matches exist
    rename_map = {}
    for schol_col, mapping in compare_dict.items():
        stu_col = mapping["student_column"]
        if (
            schol_col != stu_col
            and schol_col in schol_columns
            and stu_col in stu_columns
        ):
            rename_map[stu_col] = schol_col

    if rename_map:
        stu_data = stu_data.rename(columns=rename_map)

    # Process scholarships and students
    print("Processing Scholarships...")
    schol_dict = preprocess_scholarships(
        schol_identifier, amount_identifier, schol_data, compare_dict
    )
    print("Processing Students...")
    stu_dict = preprocess_students(
        stu_identifier, cap_identifier, compare_dict, stu_data
    )

    # print("Custom Comparison Dictionary:")
    # print(compare_dict)
    # print("\nProcessed Scholarship Dictionary:")
    # print(schol_dict)
    # print("\nProcessed Student Dictionary:")
    # print(stu_dict)

    student_names = stu_dict.keys()
    scholarship_names = schol_dict.keys()
    match_dict = {name: [] for name in student_names}
    schol_dict_copy = schol_dict.copy()
    stu_dict_copy = stu_dict.copy()
    flag = True

    print("Creating the Graph...")
    graph = create_nodes(stu_dict_copy, schol_dict_copy)
    subgraphs = create_edges(
        stu_dict_copy,
        cap_identifier,
        schol_dict_copy,
        amount_identifier,
        compare_dict,
        graph,
    )
    print("Matching...")
    total = 0
    while True:
        empty_count = 0
        for g in subgraphs:
            matchings = max_weight_matching(g)
            if len(matchings) == 0:
                empty_count += 1
                continue

            student = ""
            scholarship = ""
            for match in matchings:
                # Have to do these checks because the matching algorithm is weird. No consistency between whether a student or scholarship is the first match
                if match[0] in student_names:
                    student = match[0]
                    scholarship = match[1]
                elif match[1] in student_names:
                    student = match[1]
                    scholarship = match[0]
                else:
                    raise ValueError(
                        "Invalid matching. Student identifier not in initial data."
                    )
                # Calculate the actual amount to be awarded (minimum of scholarship amount and remaining student cap)
                scholarship_amount = schol_dict_copy[scholarship][amount_identifier]
                student_remaining_cap = stu_dict_copy[student][cap_identifier]
                awarded_amount = min(scholarship_amount, student_remaining_cap)
                match_dict[student].append((scholarship, awarded_amount))

                # Add the awarded amount to our running total
                total += awarded_amount

                # Adjust student cap, remove student if they can't get anymore money, and remove the matched scholarship
                stu_dict_copy[student][cap_identifier] -= awarded_amount
                if stu_dict_copy[student][cap_identifier] <= 0:
                    g.remove_node(student)
                    del stu_dict_copy[student]
                if awarded_amount >= schol_dict_copy[scholarship][amount_identifier]:
                    g.remove_node(scholarship)
                    del schol_dict_copy[scholarship]
                else:  # Allow the scholarship to be given out again
                    schol_dict_copy[scholarship][amount_identifier] -= awarded_amount

            # If all graphs are empty there are no matches, so break out
        if empty_count == len(subgraphs):
            break

    print("\n\n\nBlossom Matches")
    # Initialize list to store data for CSV export
    csv_data = []

    # Iterate through each student (the aptly named key) in the match dictionary
    for key in match_dict:

        # Get the list of (scholarship, amount) tuples for the current student
        # Use .get() to safely handle cases where a key might be missing or has an empty list
        scholarship_tuples = match_dict.get(key, [])

        # Proceed only if the student was matched with at least one scholarship
        if scholarship_tuples:

            # Extract just the names for display/CSV purposes
            scholarship_names = [
                f"{item[0]} ({item[1]})" for item in scholarship_tuples
            ]

            # Calculate the total amount awarded to this student directly from the tuples
            total_awarded_for_student = sum(item[1] for item in scholarship_tuples)

            # Format scholarship names for the print preview (first 5 + ...)
            scholarship_names_str_preview = ", ".join(map(str, scholarship_names[:5]))
            if len(scholarship_names) > 5:
                scholarship_names_str_preview += ", ..."

            # Print the summary for this student
            print(
                f"{key:<15} {scholarship_names_str_preview:<40} Total: {total_awarded_for_student}"
            )

            # Prepare data row for CSV: Student ID, full comma-separated list of names, total amount
            full_scholarship_names_str = ", ".join(map(str, scholarship_names))
            csv_data.append(
                [key, full_scholarship_names_str, total_awarded_for_student]
            )

    headers = ("Student", "Matched_Scholarships", "Total_Amount")

    print(total)

    save_csv(headers, csv_data, "blossom_matches")

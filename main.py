# Note on the dictionary created: if identifiers are the same, the existing/old value is overidden
# Note on unrestricted in the excel file: don't use it unless you want to create logic using custom matching. In the excel file, just make all cells with unrestricted empty

import csv
import os
import re
import sys

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
    # Deal with deprecation warning
    data.fillna(value="", inplace=True)
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
    # print(schol_dict)
    # print("\n\n\n\n\n\n\n\n\n")
    # print(stu_dict)
    qualified = True
    columns = compare_dict.keys()
    for scholarship in schol_dict:
        for student in stu_dict:
            qualified = True
            for col in columns:
                if col in schol_dict[scholarship].keys():
                    student_val = stu_dict[student][col]
                    if compare_dict[col]["comparison"] == "custom":
                        qualified = custom_matching(
                            stu_dict, student, schol_dict, scholarship, col
                        )
                    elif compare_dict[col]["comparison"] == "greater":
                        if student_val < schol_dict[scholarship][col]:
                            qualified = False
                    elif compare_dict[col]["comparison"] == "lesser":
                        if student_val > schol_dict[scholarship][col]:
                            qualified = False
                    else:
                        scholarship_values = schol_dict[scholarship][col]
                        if student_val not in scholarship_values:
                            qualified = False

            if qualified == True:
                scholarship_amount = schol_dict[scholarship][amount_identifier]
                remaining_student_scholarship = stu_dict[student][cap_identifier]
                weight = (
                    scholarship_amount
                    if remaining_student_scholarship > scholarship_amount
                    else remaining_student_scholarship
                )
                graph.add_edge(
                    student,
                    scholarship,
                    weight=weight,
                )

    # Remove isolated nodes
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


def load_file(path: str, custom=False) -> pd.DataFrame:
    path = re.sub('["]', "", path)
    file_extension = path[path.find(".") + 1 :]

    try:
        if os.path.exists(path):
            if "xls" in file_extension:
                if custom:
                    data = pd.read_excel(path, header=None)
                else:
                    data = pd.read_excel(path)
            elif "csv" in file_extension:
                if custom:
                    data = pd.read_csv(path, header=None)
                else:
                    data = pd.read_csv(path)
            else:
                print("Unsupported file type")
                return None

            return data
        else:
            print("File does not exist")
            return None
    except:
        print("Error while loading file")


# Need a way to identify column to identify students
""" TO DO:
* Process scholarship data. How will the comparisons be happening? Well, indexing a scholarship attribute should give acceptable student values
"""
if __name__ == "__main__":
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

    # Get scholarship identifier
    while True:
        print(f"Scholarship Columns: {[x for x in schol_columns]}")
        schol_identifier = input(
            "For the scholarship file, enter the name of the column that contains the desired identifier (name, scholarship code, etc): "
        ).lower()
        if schol_identifier not in schol_columns:
            print("ERROR***")
            print(f"{schol_identifier} is not a column in the scholarship file.\n")
            print("Please re-enter these columns")
        else:
            break

    print()  # Add spacing before the next section

    # Get student identifier
    while True:
        print(f"Student Columns: {[x for x in stu_columns]}")
        stu_identifier = input(
            "For the student file, enter the name of the column that contains the desired identifier (name, 700#, etc): "
        ).lower()
        if stu_identifier not in stu_columns:
            print("ERROR***")
            print(f"{stu_identifier} is not a column in the student file.\n")
            print("Please re-enter these columns")

        else:
            break

    print()  # Add spacing before the next section

    # Get scholarship amount identifier
    while True:
        print(f"Scholarship Columns: {[x for x in schol_columns]}")
        amount_identifier = input(
            "For the scholarship file, enter the name of the column that contains the monetary amount of the scholarship: "
        )
        if amount_identifier not in schol_columns:
            print(f"{amount_identifier} is not a column in the scholarship file.\n")
        else:
            break

    print()  # Add spacing before the next section

    # Get student cap identifier
    while True:
        print(f"Student Columns: {[x for x in stu_columns]}")
        cap_identifier = input(
            "For the student file, enter the name of the column indicating the students' scholarship cap: "
        )
        if cap_identifier not in stu_columns:
            print(f"{cap_identifier} is not a column in the student file.\n")
        else:
            break

    print()  # Add spacing before the next section

    # Map scholarship columns to student columns
    col_flag = True
    while True:
        print("Type -1 if done\n")
        print(f"Scholarship Columns: {[x for x in schol_columns]}")
        schol_column = (
            input("Enter scholarship column to compare to student column: ")
            .lower()
            .strip()
        )
        if schol_column == "-1":
            break

        print(f"Student Columns: {[x for x in stu_columns]}")
        stu_column = (
            input("Enter student column to compare to scholarship column: ")
            .lower()
            .strip()
        )
        if stu_column == "-1":
            break

        if schol_column not in schol_columns:
            col_flag = False
            print(f"{schol_column} is not a column in the scholarship file.\n")
        if stu_column not in stu_columns:
            col_flag = False
            print(f"{stu_column} is not a column in the student file.\n")

        if col_flag:
            print(f"Comparing {schol_column} to {stu_column}\n")
            compare_dict[schol_column] = {"student_column": stu_column}
        else:
            col_flag = True

    print()  # Add spacing before the next section

    # Get comparison types for columns
    print("Provide comparison types for columns")
    print("* Exact: Perform a direct comparison of values in the column")
    print(
        "* Greater: See if numeric student value is greater than numeric scholarship val. Ex: Student GPA > Scholarship minimum GPA"
    )
    print("* Lesser: See if numeric student value is less than numeric scholarship val")
    print("* Custom: Provide a custom comparison excel/csv file")
    comparisons = ["exact", "greater", "lesser", "custom"]

    for key in compare_dict.keys():
        comparison = (
            input(
                f"What comparison to use for {key} and {compare_dict[key]['student_column']} columns (exact/greater/lesser/custom): "
            )
            .lower()
            .strip()
        )
        while comparison not in comparisons:
            print("Invalid comparison type.\n")
            comparison = (
                input(
                    f"What comparison to use for {key} and {compare_dict[key]['student_column']} columns (exact/greater/lesser/custom)?: "
                )
                .lower()
                .strip()
            )

        compare_dict[key]["comparison"] = comparison

        if comparison == "custom":
            compare_dict[key]["custom_comparison"] = {}
            comparison_file = input("Provide the comparison file: ")
            data = load_file(comparison_file, True)
            data.columns = ["scholarship", "student"]
            for index, row in data.iterrows():
                key_val = (
                    row["scholarship"].lower()
                    if isinstance(row["scholarship"], str)
                    else row["scholarship"]
                )
                values = [x.strip().lower() for x in str(row["student"]).split(",")]
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
    schol_dict = preprocess_scholarships(
        schol_identifier, amount_identifier, schol_data, compare_dict
    )
    stu_dict = preprocess_students(
        stu_identifier, cap_identifier, compare_dict, stu_data
    )

    print("Custom Comparison Dictionary:")
    print(compare_dict)
    print("\nProcessed Scholarship Dictionary:")
    print(schol_dict)
    print("\nProcessed Student Dictionary:")
    print(stu_dict)

    student_names = stu_dict.keys()
    scholarship_names = schol_dict.keys()
    match_dict = {name: [] for name in student_names}
    flag = True
    while flag:
        graph = create_nodes(stu_dict, schol_dict)
        subgraphs = create_edges(
            stu_dict, cap_identifier, schol_dict, amount_identifier, compare_dict, graph
        )

        print(len(subgraphs))
        if not subgraphs:
            flag = False
            break

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
                match_dict[student].append(scholarship)

                # Adjust student cap, remove student if they can't get anymore money, and remove the matched scholarship
                stu_dict[student][cap_identifier] -= schol_dict[scholarship][
                    amount_identifier
                ]
                if stu_dict[student][cap_identifier] <= 0:
                    graph.remove_node(student)
                    del stu_dict[student]
                graph.remove_node(scholarship)
                del schol_dict[scholarship]

            # If all graphs are empty there are no matches, so break out
            if empty_count >= len(subgraphs):
                flag = False
                break
    print("\n\n\nBlossom Matches")
    assigned = 0
    for key in match_dict:
        assigned += len(match_dict[key])
        if len(match_dict[key]) >= 1:
            print(f"{key}: {match_dict[key]}")

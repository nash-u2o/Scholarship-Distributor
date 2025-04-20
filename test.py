import os
import re

import pandas as pd


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


if __name__ == "__main__":
    # Test the load_file function
    test_file_path = input("Enter the path to the file you want to load: ")
    content = load_file(test_file_path, True)
    print("File Content:")
    print(content)

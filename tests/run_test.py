import glob
import json
import os
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

from termcolor import cprint


def get_tasks():
    path_to_trajectories = "./trajectories/test/"
    done_tasks = set()
    newegg = 0
    bestbuy = 0
    walmart = 0
    ebay = 0
    for f in glob.glob(os.path.join(path_to_trajectories, '*.json')):
        with open(f, 'r') as file:
            try:
                json_data = json.load(file)
            except:
                continue
            intent = json_data["intent"]
            done_tasks.add(intent)
            if "newegg" in intent:
                newegg += 1
            if "bestbuy" in intent:
                bestbuy += 1
            if "walmart" in intent:
                walmart += 1
            if "ebay" in intent:
                ebay += 1
    return done_tasks


def process_instruction(i, instruction, type):
    tasks = get_tasks()
    if instruction in tasks:
        return
    cprint("#" * 50, color="blue")
    cprint("#" * 50, color="blue")
    cprint(instruction, color="red")
    cprint("#" * 50, color="blue")
    cprint("#" * 50, color="blue")
    os.system(
        f"python3 ../agent/run.py "
        f"--instruction \"{instruction}\" "
        f"--action-file \"{type}_{i}\" "
        f"--config-path ../config.ini"
        # f" >> ../output/output.txt"
    )


def extract_lines(type, num):
    file_name = "./test_sets/test_set.csv"
    df = pd.read_csv(file_name)
    if type != 'all':
        df = df[df['test_set'] == type]
    return df['intent'][:num]


def run(type, max_workers: int = 1, num: int = 10):
    """
        type - 'general' or 'web' or 'all'
        max_workers - max number of parallel working threads
        num  - number of examples taken from file
    """

    lines = extract_lines(type, num)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_instruction, i, instruction, type) for i, instruction in enumerate(lines)]


if __name__ == "__main__":
    run("web", 1, 50)

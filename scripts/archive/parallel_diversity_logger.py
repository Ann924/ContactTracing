import sys
import os
import csv
from tqdm import tqdm
import logging
from collections import namedtuple

import pandas as pd
import itertools
import time
import concurrent.futures
import shortuuid

# Set path to ContactTracing/
os.chdir('../..')
sys.path.insert(0, '..')

from ctrace.simulation import *
from ctrace import PROJECT_ROOT

# <======================================== Output Configurations ========================================>
# Configure Logging Files => First 5 digits
RUN_LABEL = shortuuid.uuid()[:5]

# Setup output directories
output_path = PROJECT_ROOT / "output" / f'run[{RUN_LABEL}]'
output_path.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = output_path / 'results.csv'
LOGGING_FILE = output_path / 'run.log'

# <================================================== Logging Setup ==================================================>
# Setup up Parallel Log Channel
logger = logging.getLogger("Parallel")
logger.setLevel(logging.DEBUG)

# Set LOGGING_FILE as output
fh = logging.FileHandler(LOGGING_FILE)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

# Info current path
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Current path {sys.path}")

# <================================================== Loaded Data ==================================================>
# Create the SIR datatype (QUEUE version)
SIR = namedtuple("SIR", ["S", "I_QUEUE", "R", "label"])

# Load montgomery graph
G = load_graph("montgomery")

# <================================================== Configurations ==================================================>

# Configurations
# Experiment 1
COMPACT_CONFIG = {
    "G": [G], # Graph
    "p": [0.078], # Probability of infection
    "budget": [i for i in range(60, 1001, 4)], # The k value
    "method": ["weighted"],
    "num_initial_infections": [5], # Initial Initial (DATA)
    "num_shocks": [8], # Size of shocks in initial (DATA)
    "initial_iterations": [7], # Number of iterations before intervention
    "MDP_iterations": [-1], # Number of iterations of intervention
    "iterations_to_recover": [1], # Number of iterations it takes for a infected node to recover (set to 1)
    "from_cache": ['t7.json'], # If cache is specified, some arguments are ignored
    "verbose": [False], # Prints stuff
    "trials": 10, # Number of trials to run for each config
}

# Attributes need to partition configuration! Do NOT have duplicate attributes
COMPLEX = ["G"] # Attributes that need to be processed before printing
HIDDEN = ["visualization", "verbose", "trials"] # These attributes will NOT be logged at all

# Anything not in PRIMITIVE or HIDDEN
PRIMITIVE = list(COMPACT_CONFIG.keys() - set(COMPLEX) - set(HIDDEN)) # Attributes that will be printed as is
RESULTS = ["infected", "peak", "iterations_completed"]

# Utilities
def dict_product(dicts):
    """Expands an dictionary of lists into a list of dictionaries through a cartesian product"""
    return (dict(zip(dicts, x)) for x in itertools.product(*dicts.values()))


def expand_configurations(compact_config: Dict):
    """Expands compact configuration into many runnable configs through a cartesian product"""
    compact_config = compact_config.copy()

    # Handle multiple trials
    compact_config["trial_id"] = [i for i in range(compact_config["trials"])]
    del compact_config["trials"]

    # Expand configuration
    return list(dict_product(compact_config))


def readable_configuration(config: Dict):
    """Takes in a instance of an expanded configuration and returns a readable object"""

    output = {}

    # Handle COMPLEX attributes
    output["G"] = config["G"].NAME

    # Paste in PRIMITIVE attributes
    for p in PRIMITIVE:
        output[p] = config[p]

    # Ignore HIDDEN attributes

    return output


def MDP_runner(param):
    """Takes in runnable parameter and returns a (Result tuple, Readable Params)"""
    readable_params = readable_configuration(param)
    logger.info(f"Launching => {readable_params}")

    (infected, peak, iterations) = generalized_mdp(**param)
    return (infected, peak, iterations), readable_params


def parallel_MDP(args: List[Dict]):
    with concurrent.futures.ProcessPoolExecutor() as executor, open(OUTPUT_FILE, "w") as output_file:
        results = [executor.submit(MDP_runner, arg) for arg in args]
        writer = csv.DictWriter(output_file, fieldnames=COMPLEX + PRIMITIVE + RESULTS)
        writer.writeheader()
        for f in tqdm(concurrent.futures.as_completed(results), total=len(args)):
            ((infected, peak, iterations), readable) = f.result()

            # Merge the two dictionaries, with results taking precedence
            entry = readable
            result_dict = {
                "infected": infected,
                "peak": peak,
                "iterations_completed": iterations,
            }
            entry.update(result_dict)

            # Write and flush results
            writer.writerow(entry)
            output_file.flush()
            logger.info(f"Finished => {entry}")


# Main
print(f'Logging Directory: {LOGGING_FILE}')
expanded_configs = expand_configurations(COMPACT_CONFIG)
parallel_MDP(expanded_configs)
print('done')

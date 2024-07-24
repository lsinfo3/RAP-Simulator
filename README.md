# RAP-Simulator
This project provides a simpy-based simulation of the RAP protocol for Time-Sensitive Networking, aiming to allow for the convenient comparison of the performance between different configuration methods and topology structures. The simulation is written in Python.
We provide the full code used for generating the results detailed in the accompanying paper, and additionally include a smaller example, as detailed below. The topologies used in the paper are generated via [an internally developed tool for generating possible industrial topologies.](https://github.com/lsinfo3/tsn_problem_generator).

## Simulation Input
The definition of the network topology is provided through a json-file, an example of which is provided in the [example_scenario/example.json](example_scenario/example.json) file. This file has been created through the [TSN-topology_generator](https://github.com/lsinfo3/tsn_problem_generator) tool, specifying a small problem instance.
For now, all other parameters are provided through hard-coded parameters in the respective main methods.

## Required dependencies
For a list of required dependencies, please consult the [requirements.txt](requirements.txt) file.

## Running the Example Scenario
To run the example scenario, for which the topology is placed in [example_scenario/example.json](example_scenario/example.json), it is sufficient to simply run the [main_example_scenario.py](main_example_scenario.py) python script. This will run the simulation for the decentralized configuration method on the provided topology. 
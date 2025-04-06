# AutoCHTC: High-Throughput Computing DAG Management Tool

## Overview

AutoCHTC is a command-line tool designed to simplify the creation and management of directed acyclic graphs (DAGs) for high-throughput computing environments using HTCondor Python bindings. This tool streamlines the process of setting up complex job workflows, managing job dependencies, and automating submission tasks.

## Features

- **DAG Creation**: Build multi-layered computational workflows with customizable dependencies
- **Job Management**: Generate job directories with all necessary files (.sub, .sh, .py, queue files)
- **Queue Configuration**: Create and manage job parameter combinations with flexible grouping options
- **Edge Relationships**: Configure job dependencies with various relationship types:
  - Many-to-Many: Connect all jobs in a layer to all jobs in another layer
  - One-to-One: Connect jobs in sequence across layers
  - Grouping: Connect groups of jobs between layers
  - Slicing: Connect specific subsets of jobs between layers
- **Script Integration**: Add pre-processing and post-processing scripts to jobs
- **Directory Cleaning**: Remove DAG-related files to clean up working directories
- **Submit File Editing**: Edit job submit files with proper formatting

## Installation

Ensure you have HTCondor and Python 3 installed on your system. The script requires the `htcondor` Python module.

```bash
pip install htcondor
```

## Usage

Run the script to access the main menu:

```bash
chmod +x autochtc.py
./autochtc.py
```
or
```bash
python autochtc.py
```

### Main Menu Options

1. **Create a new DAG**: Build a workflow with dependent jobs
2. **Generate/Edit a job directory or file**: Create job templates and configuration files
3. **Get statistics on DAGs and jobs**: (Under construction)
4. **Clean current directory**: Remove DAG-related files
5. **Change working directory**: Navigate to a different working location

### Creating a DAG

1. Enter a name for your DAG
2. Select job submit files to include in the workflow
3. Configure queue parameters for each job (manually or from existing queue files)
4. Add pre/post scripts if needed
5. Define relationships between job layers
6. Submit the DAG or save for later submission

### Generating Job Directories

Creates a new job directory with:
- Submit (.sub) file
- Shell script (.sh) file
- Python script (.py) file
- Queue parameter file (.txt)

## Examples

### Creating a Simple DAG

```
1. Enter the name of the DAG: my_workflow
2. Select job submit files to include
3. Configure each job's parameters
4. Set up dependencies between jobs
5. Submit the workflow
```

### Setting Up a Job Directory

```
1. Enter the job name: my_job
2. Enter Docker image: pytorch/pytorch:2.4.1-cuda12.1-cudnn9-devel
3. Enter job arguments: dataset_name model_size learning_rate
```

## Advanced Features

- **Variable Configuration**: Set up job parameters as fixed values, lists, or intervals
- **Grouping Options**: Bundle job parameters together for structured workflows
- **Centralized Logging**: Organize log files by job and cluster
- **Docker Integration**: Seamless support for containerized jobs

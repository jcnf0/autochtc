#!/usr/bin/env python3
import itertools
import os
import re
import shutil

import htcondor
from htcondor import dags

EXCLUDED_FOLDERS = set(
    [
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        "venv",
        "env",
        "conda",
        "build",
        "dist",
        "egg-info",
        "node_modules",
        "logs",
        "results",
        "output",
        "condor_log",
        ".vscode-server",
    ]
)
QUEUE_EXT = ".txt"

# TODO : Refresh a DAG, More complex layer system, Make the log dirs better, Add rescue or not


def correct_submit(submit_file):
    # Corrects the formatting of a submit file
    with open(submit_file, "r") as f:
        lines = f.readlines()

    # If we see a certain word at the start of a line, we want to add \n
    # before it
    words_comments = {
        "universe": "Universe",
        "arguments": "Arguments",
        "Requirements": "Artefact",
        "+is_resumable": "Checkpoint",
        "output": "Logging",
        "request_cpus": "Compute resources",
        "request_gpus": "GPU resources",
        "queue": "Queue",
    }
    for i, line in enumerate(lines):
        for word, comment in words_comments.items():
            if word in line:
                lines[i] = f"\n# {comment}\n" + line

    with open(submit_file, "w") as f:
        f.write("".join(lines))


def print_centered_ascii_art():
    ascii_art = r"""
                _         _____ _    _ _______ _____
     /\        | |       / ____| |  | |__   __/ ____|
    /  \  _   _| |_ ___ | |    | |__| |  | | | |
   / /\ \| | | | __/ _ \| |    |  __  |  | | | |
  / ____ \ |_| | || (_) | |____| |  | |  | | | |____
 /_/    \_\__,_|\__\___/ \_____|_|  |_|  |_|  \_____|
    """

    print(ascii_art)


def get_job_sub(base_dir=".", excluded_dirs=[]):
    available_jobs = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [
            d for d in dirs if d not in EXCLUDED_FOLDERS and d not in excluded_dirs
        ]
        for file in files:
            if file.endswith(".sub"):
                job_path = os.path.join(root, file)
                if not os.path.exists(os.path.join(root, file.replace(".sub", ".dag"))):
                    available_jobs.append(job_path.replace(base_dir + "/", ""))

    if not available_jobs:
        print("No job submit files found.")
        return None

    enumerated_jobs = [f"{i+1}. {job}" for i, job in enumerate(available_jobs)]
    print("Detected jobs:")
    for job in enumerated_jobs:
        print(job)

    while True:
        jobname_or_id = input("Which job? (Enter number or full path): ")
        if jobname_or_id.isdigit() and 1 <= int(jobname_or_id) <= len(available_jobs):
            return available_jobs[int(jobname_or_id) - 1]
        elif jobname_or_id in available_jobs:
            return jobname_or_id
        else:
            print("Invalid selection. Please try again.")


def read_vars(job_sub, job_queue_file):
    pattern = r"\$\((.*?)\)"
    vars = []
    keys = re.findall(pattern, job_sub["arguments"])

    with open(job_queue_file, "r") as f:
        lines = f.readlines()
        for line in lines:
            if "," in line:
                combination = line.replace(" ", "").replace("\n", "").split(",")
            else:
                combination = line.replace("\n", "").split(" ")

            if len(combination) != len(keys):
                print(combination)
                print(f"Warning: Number of values in line does not match number of keys.")

            var = {}
            for i, key in enumerate(keys):
                if combination[i].isdigit():
                    var[key] = int(combination[i])
                else:
                    var[key] = combination[i]
            vars.append(var)

    return vars


def set_vars(job_sub):
    pattern = r"\$\((.*?)\)"
    keys = re.findall(pattern, job_sub["arguments"])
    keys_values = {}

    for key in keys:
        while True:
            try:
                key_type = input(
                    f"\nEnter the number associated with the type of key for {key}:\n1. Fixed/List\n2. Interval\n"
                )
                if key_type not in ["1", "2"]:
                    raise ValueError("Invalid choice. Please enter 1 or 2.")

                if key_type == "1":
                    values = input(
                        f"Enter one or more values for {key} separated by commas or spaces: "
                    )
                    if "," in values:
                        values = values.replace(" ", "").split(",")
                    else:
                        values = values.split(" ")
                    if not values:
                        raise ValueError("Please enter at least one value.")
                    keys_values[key] = values
                    break

                elif key_type == "2":
                    lower = int(input(f"Enter the lower bound for {key}: "))
                    upper = int(input(f"Enter the upper bound for {key}: "))
                    step = int(input(f"Enter the step for {key}: "))
                    if lower >= upper:
                        raise ValueError("Lower bound must be less than upper bound.")
                    if step <= 0:
                        raise ValueError("Step must be greater than 0.")
                    values = list(range(lower, upper + 1, step))
                    keys_values[key] = values
                    break
            except ValueError as e:
                print(f"Error: {e}. Please try again.")

    while True:
        try:
            combine_option = input(
                "How would you like to combine the arguments?\n1. All combinations\n2. Grouped combinations\nEnter choice (1/2): "
            )
            if combine_option not in ["1", "2"]:
                raise ValueError("Invalid choice. Please enter 1 or 2.")
            break
        except ValueError as e:
            print(f"Error: {e}. Please try again.")

    if combine_option == "1":
        # Generate all combinations, iterating over the first arguments first
        combinations = list(itertools.product(*[keys_values[key] for key in keys]))
        vars = []
        for combination in combinations:
            var = {}
            for key in keys:  # Iterate through keys in their original order
                value = combination[keys.index(key)]  # Get the value for this key
                var[key] = int(value) if str(value).isdigit() else value
            vars.append(var)
    elif combine_option == "2":
        # For grouped combinations
        free_keys = list(keys)  # Use a list instead of set to maintain order
        grouped_keys = []

        while free_keys:
            print("\nFree keys:", ", ".join(free_keys))
            group = input(
                "Enter keys to group together (space-separated), or press Enter to finish grouping: "
            ).split()

            if not group:
                break

            try:
                if not all(key in free_keys for key in group):
                    raise ValueError("Invalid keys. Please use only free keys.")
                if len(group) < 2:
                    raise ValueError("Groups must contain at least 2 keys.")
                # Make sure that the number of values for each key in the group is the same
                group_values = [keys_values[key] for key in group]
                if not all(
                    len(values) == len(group_values[0]) for values in group_values
                ):
                    raise ValueError(
                        "Number of values for each key in the group must be the same."
                    )
                grouped_keys.append(group)
                for key in group:
                    free_keys.remove(key)
            except ValueError as e:
                print(f"Error: {e}. Please try again.")

        group_vars = []
        for group in grouped_keys:
            group_values = [keys_values[key] for key in group]
            combinations = list(zip(*group_values))
            group_var_list = []
            for combination in combinations:
                var = {}
                for i, key in enumerate(group):
                    value = combination[i]
                    var[key] = int(value) if str(value).isdigit() else value
                group_var_list.append(var)
            group_vars.append(group_var_list)

        # Ensemble all groups : Take the product of each group
        grouped_primitive_vars = list(itertools.product(*group_vars))
        for i in range(len(grouped_primitive_vars)):
            # Flatten the list of dictionaries into a single dictionary
            var = {}
            for group_var in grouped_primitive_vars[i]:
                var.update(group_var)
            grouped_primitive_vars[i] = var

        free_vars = []
        for key in free_keys:
            free_vars.append([{key: value} for value in keys_values[key]])
        free_primitive_vars = list(itertools.product(*free_vars))

        for i in range(len(free_primitive_vars)):
            var = {}
            for group_var in free_primitive_vars[i]:
                var.update(group_var)
            free_primitive_vars[i] = var

        # Prompt user for order by group or by free

        while True:
            try:
                order_option = input(
                    "How would you like to order the combinations?\n1. Grouped first\n2. Free first\nEnter choice (1/2): "
                )
                if order_option not in ["1", "2"]:
                    raise ValueError("Invalid choice. Please enter 1 or 2.")
                break
            except ValueError as e:
                print(f"Error: {e}. Please try again.")

        if order_option == "1":
            vars = []
            for grouped_primitive_var in grouped_primitive_vars:
                for free_primitive_var in free_primitive_vars:
                    var = grouped_primitive_var.copy()
                    var.update(free_primitive_var)
                    vars.append(var)
        else:
            vars = []
            for free_primitive_var in free_primitive_vars:
                for grouped_primitive_var in grouped_primitive_vars:
                    var = free_primitive_var.copy()
                    var.update(grouped_primitive_var)
                    vars.append(var)

    return vars


def create_dag_directory(dag_name):
    dag_dir = os.path.join(os.getcwd(), dag_name)
    os.makedirs(dag_dir, exist_ok=True)
    return dag_dir


def copy_job_files(job_sub_path, dag_dir):
    job_dir = os.path.dirname(job_sub_path)
    job_sub = htcondor.Submit(open(job_sub_path).read())

    files_to_copy = [os.path.basename(job_sub_path)]
    if "executable" in job_sub.keys():
        files_to_copy.append(job_sub["executable"])
    if "transfer_input_files" in job_sub.keys():
        files_to_copy.extend(
            job_sub["transfer_input_files"].replace(" ", "").split(",")
        )

    # We don't need to copy the queue file, as we will put all vars info in the .dag
    queue = job_sub.getQArgs()
    try:
        queue_file = re.search(rf"\b\w+\{QUEUE_EXT}\b", queue).group(0)
        files_to_copy.append(queue_file)
    except AttributeError:
        print(f"Warning: No {QUEUE_EXT} file found for job {job_sub_path}")
        pass

    for file in files_to_copy:
        src = os.path.join(job_dir, file)
        dst = os.path.join(dag_dir, file)
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            print(f"Warning: File {file} not found in {job_dir}")

    return os.path.join(dag_dir, os.path.basename(job_sub_path))


def clean_directory(directory):
    dag_related_extensions = [".dag", ".dagman.out", ".rescue", ".lock"]
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(ext in file for ext in dag_related_extensions):
                os.remove(os.path.join(root, file))
                print(f"Removed: {os.path.join(root, file)}")


def create_new_dag():
    dagname = input("Enter the name of the DAG: ").strip() or "auto_dag"
    dag_dir = create_dag_directory(dagname)
    dot_config = dags.DotConfig(dagname + ".dot", update=True)
    dag = dags.DAG(dot_config=dot_config)
    layers = []

    while True:
        print(
            "\n----------------CURRENT DAG STRUCTURE----------------\n",
            dag.describe(),
            "\n",
        )
        job_sub_path = get_job_sub(excluded_dirs=[os.path.basename(dag_dir)])
        if not job_sub_path:
            if layers and input("Go back to previous step? (y/N) ").lower() == "y":
                layers.pop()
                continue
            break

        new_job_sub_path = copy_job_files(job_sub_path, dag_dir)
        sub_file = open(new_job_sub_path).read()
        sub_file = re.sub(r"queue.*", "", sub_file)
        sub_file = re.sub(r"JobBatchName.*\n", "", sub_file)

        job_sub = htcondor.Submit(sub_file)

        job_name = os.path.basename(new_job_sub_path).replace(".sub", "")
        if "output" in job_sub.keys():
            job_sub["output"] = f"condor_log/{job_name}/$(Cluster).out"
        if "error" in job_sub.keys():
            job_sub["error"] = f"condor_log/{job_name}/$(Cluster).err"
        if "log" in job_sub.keys():
            job_sub["log"] = f"{job_name}.log"

        queue_option = input(
            f"Choose how to set up the queue:\n1. Manual\n2. Import from job {QUEUE_EXT}\n3. No queue\nEnter choice (1/2/3): "
        )

        if queue_option == "1":
            vars = set_vars(job_sub)
        elif queue_option == "2":
            queue_file = os.path.splitext(new_job_sub_path)[0] + QUEUE_EXT
            if os.path.exists(queue_file):
                vars = read_vars(job_sub, queue_file)
            else:
                print(f"Warning: {queue_file} not found. Using empty vars.")
                vars = [{}]
        else:
            num_jobs = int(
                input("Enter the number of jobs to run (default 1): ") or "1"
            )
            vars = [{} for _ in range(num_jobs)]

        layer_name = job_name

        # Ask about pre-script
        pre_script = None
        if (
            input("Do you want to add a pre-script for this layer? (y/N) ").lower()
            == "y"
        ):
            pre_script_path = input("Enter the path to the pre-script (.sh file): ")
            if os.path.exists(pre_script_path):
                shutil.copy2(pre_script_path, dag_dir)
                pre_script = dags.Script(os.path.basename(pre_script_path))
            else:
                print(
                    f"Warning: Pre-script file {pre_script_path} not found. Skipping pre-script."
                )

        # Ask about post-script
        post_script = None
        if (
            input("Do you want to add a post-script for this layer? (y/N) ").lower()
            == "y"
        ):
            post_script_path = input("Enter the path to the post-script (.sh file): ")
            if os.path.exists(post_script_path):
                shutil.copy2(post_script_path, dag_dir)
                post_script = dags.Script(os.path.basename(post_script_path))
            else:
                print(
                    f"Warning: Post-script file {post_script_path} not found. Skipping post-script."
                )

        if not layers:
            layer = dag.layer(
                name=layer_name,
                submit_description=job_sub,
                vars=vars,
                pre=pre_script,
                post=post_script,
            )
        else:
            edge_type = get_edge_type()
            # If OneToOne edge, we need to make sure the previous layer has the same number of jobs
            if isinstance(edge_type, dags.OneToOne) and len(vars) != len(
                layers[-1].vars
            ):
                print(
                    "Warning: Number of jobs in this layer does not match the previous layer. Setting edge type to ManyToMany."
                )
                edge_type = dags.ManyToMany()

            try:
                layer = layers[-1].child_layer(
                    name=layer_name,
                    submit_description=job_sub,
                    vars=vars,
                    pre=pre_script,
                    post=post_script,
                    edge=edge_type,
                )
            except Exception as e:
                print(f"Error: {e}")
                print()
                continue

        layers.append(layer)

        if input("Would you like to add another layer? (y/N) ").lower() != "y":
            break

    dag_file = dags.write_dag(dag, dag_dir, f"{dagname}.dag")
    for file in os.listdir(dag_dir):
        if file.endswith(".sub"):
            correct_submit(os.path.join(dag_dir, file))

    print(f"DAG file created: {dag_file}")

    if input("Would you like to submit the DAG? (y/N) ").lower() == "y":
        cwd = os.getcwd()
        os.chdir(dag_dir)
        dag_submit = htcondor.Submit.from_dag(str(dag_file), {"force": 1})
        schedd = htcondor.Schedd()
        cluster_id = schedd.submit(dag_submit).cluster()
        print(f"Submitted DAG {dagname}.dag with cluster ID {cluster_id}")
        os.chdir(cwd)


def quick_dag_with_options(job_configs):
    """
    Create a DAG with advanced configuration options for each layer.

    job_configs: List of dictionaries with structure:
    {
        'submit_file': str,  # Path to .sub file
        'pre_script': str,   # Optional path to pre script
        'post_script': str,  # Optional path to post script
        'edge_type': str,    # Optional: 'many2many' (default), 'one2one', 'group', 'slice'
        'edge_params': dict  # Optional: Parameters for edge type
    }
    """
    if not job_configs:
        raise ValueError("No jobs provided")

    # Create DAG name from first job
    dag_name = (
        os.path.splitext(os.path.basename(job_configs[0]["submit_file"]))[0] + "_dag"
    )

    # Create DAG directory
    dag_dir = os.path.join(os.getcwd(), dag_name)
    os.makedirs(dag_dir, exist_ok=True)

    # Initialize DAG
    dot_config = dags.DotConfig(dag_name + ".dot", update=True)
    dag = dags.DAG(dot_config=dot_config)

    prev_layer = None
    for config in job_configs:
        job_file = config["submit_file"]
        job_name = os.path.splitext(os.path.basename(job_file))[0]
        job_dir = os.path.dirname(os.path.abspath(job_file))

        # Read submit file
        with open(job_file) as f:
            sub_content = f.read()
        job_sub = htcondor.Submit(sub_content)

        # Copy necessary files
        files_to_copy = [os.path.basename(job_file)]
        if "executable" in job_sub:
            files_to_copy.append(job_sub["executable"])
        if "transfer_input_files" in job_sub:
            files_to_copy.extend(job_sub["transfer_input_files"].split(","))

        # Copy and setup pre/post scripts if provided
        pre_script = None
        if config.get("pre_script"):
            pre_path = config["pre_script"]
            if os.path.exists(pre_path):
                shutil.copy2(pre_path, dag_dir)
                pre_script = dags.Script(os.path.basename(pre_path))

        post_script = None
        if config.get("post_script"):
            post_path = config["post_script"]
            if os.path.exists(post_path):
                shutil.copy2(post_path, dag_dir)
                post_script = dags.Script(os.path.basename(post_path))

        # Copy all necessary files
        for file in files_to_copy:
            src = os.path.join(job_dir, file.strip())
            dst = os.path.join(dag_dir, os.path.basename(file.strip()))
            if os.path.exists(src):
                shutil.copy2(src, dst)

        # Handle queue file if exists
        vars = [{}]
        queue_args = job_sub.getQArgs()
        if queue_args:
            queue_file = re.search(r"\b\w+\.txt\b", queue_args)
            if queue_file:
                queue_path = os.path.join(job_dir, queue_file.group(0))
                if os.path.exists(queue_path):
                    shutil.copy2(queue_path, dag_dir)
                    # Read vars from queue file
                    pattern = r"\$\((.*?)\)"
                    keys = re.findall(pattern, job_sub["arguments"])
                    vars = []
                    with open(queue_path) as f:
                        for line in f:
                            combination = line.strip().split()
                            var = {}
                            for i, key in enumerate(keys):
                                var[key] = combination[i]
                            vars.append(var)

        # Update log paths
        job_sub["output"] = f"condor_log/{job_name}/$(Cluster).out"
        job_sub["error"] = f"condor_log/{job_name}/$(Cluster).err"
        job_sub["log"] = f"{job_name}.log"

        # Handle edge type
        edge = dags.ManyToMany()  # default
        if prev_layer and "edge_type" in config:
            edge_type = config["edge_type"].lower()
            edge_params = config.get("edge_params", {})

            if edge_type == "one2one":
                edge = dags.OneToOne()
            elif edge_type == "group":
                parent_chunk = edge_params.get("parent_chunk", 1)
                child_chunk = edge_params.get("child_chunk", 1)
                edge = dags.Grouper(
                    parent_chunk_size=parent_chunk, child_chunk_size=child_chunk
                )
            elif edge_type == "slice":
                parent_slice = edge_params.get("parent_slice", slice(None))
                child_slice = edge_params.get("child_slice", slice(None))
                edge = dags.Slicer(parent_slice=parent_slice, child_slice=child_slice)

        # Create layer
        if prev_layer is None:
            layer = dag.layer(
                name=job_name,
                submit_description=job_sub,
                vars=vars,
                pre=pre_script,
                post=post_script,
            )
        else:
            layer = prev_layer.child_layer(
                name=job_name,
                submit_description=job_sub,
                vars=vars,
                edge=edge,
                pre=pre_script,
                post=post_script,
            )
        prev_layer = layer

    # Write DAG file
    dag_file = dags.write_dag(dag, dag_dir, f"{dag_name}.dag")
    print(f"Created DAG: {dag_file}")
    return dag_file


def change_working_directory():
    home_dir = os.path.expanduser("~")
    example_dirs = [
        d
        for d in os.listdir(home_dir)
        if os.path.isdir(os.path.join(home_dir, d)) and not d.startswith(".")
    ]
    example_dirs.sort()

    print("\nAvailable directories:")
    for i, dir_name in enumerate(example_dirs, 1):
        print(f"{i}. {dir_name}")
    print("Or enter a custom path")

    while True:
        choice = input("\nEnter directory number or custom path: ")
        if choice.isdigit() and 1 <= int(choice) <= len(example_dirs):
            new_dir = os.path.join(home_dir, example_dirs[int(choice) - 1])
        else:
            new_dir = os.path.expanduser(choice)

        if os.path.isdir(new_dir):
            os.chdir(new_dir)
            print(f"Changed working directory to: {os.getcwd()}")
            break
        else:
            print("Invalid directory. Please try again.")


def edit_job_submit():
    job_sub_path = get_job_sub()
    if not job_sub_path:
        return

    job_sub = htcondor.Submit(open(job_sub_path).read())

    while True:
        print("\nCurrent job submit file contents:")
        for key, value in job_sub.items():
            print(f"{key} = {value}")

        key_to_edit = input("\nEnter the key to edit (or 'q' to finish editing): ")
        if key_to_edit.lower() == "q":
            break

        if key_to_edit in job_sub.keys():
            print(f"Current value for {key_to_edit}: {job_sub[key_to_edit]}")
            new_value = input(f"Enter new value for {key_to_edit}: ")
            job_sub[key_to_edit] = new_value
        else:
            print(f"Key '{key_to_edit}' not found in job submit file.")

    with open(job_sub_path, "w") as f:
        f.write(str(job_sub))
    correct_submit(job_sub_path)
    print(f"Updated job submit file: {job_sub_path}")


def generate_menu():
    while True:
        print("\n--- Generate Menu ---")
        print("1. Generate new job directory")
        print(f"2. Generate queue {QUEUE_EXT} file")
        print("3. Edit a job submit file")
        print("4. Back to main menu (m)")
        print("q. Quit")

        choice = input("Enter your choice: ")

        if choice == "1":
            generate_job_directory()

        elif choice == "2":
            generate_queue()

        elif choice == "3":
            edit_job_submit()

        elif choice == "4" or choice == "m":
            break

        elif choice == "q":
            print("Quitting AutoCHTC. Goodbye!")
            # Quit the program
            exit()
        else:
            print("Invalid choice. Please try again.")


def generate_queue():
    job_sub_path = get_job_sub()
    if not job_sub_path:
        return

    job_sub = htcondor.Submit(open(job_sub_path).read())
    pattern = r"\$\((.*?)\)"
    keys = re.findall(pattern, job_sub["arguments"])

    vars = set_vars(job_sub)

    queue_file_path = os.path.splitext(job_sub_path)[0] + QUEUE_EXT
    with open(queue_file_path, "w") as f:
        for i, var in enumerate(vars):
            line = (
                " ".join([str(var[key]) for key in keys])
                if QUEUE_EXT == ".txt"
                else ",".join([str(var[key]) for key in keys])
            )
            if i < len(vars) - 1:
                f.write(line + "\n")
            else:
                f.write(line)
    print(f"Generated queue file: {queue_file_path}")


def get_edge_type():
    # TODO: Add number of parents and children as info
    print("Choose the edge type for connecting this layer to the previous one:")
    print("1. ManyToMany (default)")
    print("2. OneToOne")
    print("3. Grouping")
    print("4. Slicing")

    choice = input("Enter your choice (1/2/3/4): ")

    if choice == "2":
        return dags.OneToOne()
    elif choice == "3":
        parent_chunk_size = int(input("Enter the parent chunk size: "))
        child_chunk_size = int(input("Enter the child chunk size: "))
        return dags.Grouper(
            parent_chunk_size=parent_chunk_size, child_chunk_size=child_chunk_size
        )
    elif choice == "4":
        # TODO Error handling
        # Create the slices
        parent_start, parent_end, parent_step = (
            input("Enter the parent slice (start, end, step): ")
            .replace(" ", "")
            .split(",")
        )
        child_start, child_end, child_step = (
            input("Enter the child slice (start, end, step): ")
            .replace(" ", "")
            .split(",")
        )
        parent_slice = slice(int(parent_start), int(parent_end), int(parent_step))
        child_slice = slice(int(child_start), int(child_end), int(child_step))
        return dags.Slicer(parent_slice=parent_slice, child_slice=child_slice)
    else:
        return dags.ManyToMany()


def generate_job_directory():
    job_name = input("Enter the job name: ")

    while job_name == "" or any(
        char in job_name
        for char in [" ", ".", "/", "\\", ":", "*", "?", '"', "<", ">", "|"]
    ):
        print("Invalid job name. Please avoid spaces and special characters.")
        job_name = input("Enter the job name: ")

    docker_image = input("Enter the Docker image (leave empty for default): ")

    # Has to be of the form user/image:tag
    while docker_image != "" and not re.match(
        r"^[a-zA-Z0-9]+/[a-zA-Z0-9-]+:[a-zA-Z0-9]+$", docker_image
    ):
        print("Invalid Docker image format. Please enter in the form user/image:tag")
        docker_image = input("Enter the Docker image: ")

    docker_image = (
        docker_image
        if docker_image != ""
        else "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-devel"
    )

    job_dir = os.path.join(os.getcwd(), job_name)
    os.makedirs(job_dir, exist_ok=True)

    # Get job arguments
    arguments = input("Enter job arguments (space-separated): ").split()

    str_arguments = [f"$({arg})" for arg in arguments]
    # Create .sub file
    sub_template = f"""JobBatchName = "{job_name.capitalize()}"

universe = docker
docker_image = {docker_image}

arguments =  {" ".join(str_arguments)}

# Artefact
Requirements = (Target.HasCHTCStaging == true)
executable = {job_name}.sh
transfer_input_files = {job_name}.py
should_transfer_files = YES
when_to_transfer_output = ON_EXIT

# Checkpoint
+is_resumable           = true

# Logging
output                  = condor_log/Cluster$(Cluster)/output.$(Process).out
error                   = condor_log/Cluster$(Cluster)/error.$(Process).err
log                     = {job_name}.log

# Compute resources

request_cpus            = 1
request_memory          = 40GB
request_disk            = 10GB

# GPU resources
request_gpus            = 1
require_gpus            = (DriverVersion >= 12.1) && (GlobalMemoryMb >= 40000)
+WantGPULab             = True
# change to true if *not* using staging for checkpoints and interested in accessing GPUs beyond CHTC
+WantFlocking           = False
+WantGlidein            = False
+GPUJobLength           = "short"

queue {', '.join(arguments)} from {job_name}{QUEUE_EXT}
"""
    with open(os.path.join(job_dir, f"{job_name}.sub"), "w") as f:
        f.write(sub_template)

    export_args = [f"export {arg}=${i+1}" for i, arg in enumerate(arguments)]
    py_args = [f"--{arg} ${arg}" for arg in arguments]
    # Create .sh file
    sh_template = (
        f"""#!/bin/bash

# Hugging Face
export HF_HOME=/staging/{os.getenv('USER')}/.cache/huggingface
export HF_TOKEN=YOUR_TOKEN
export STAGING_DIR=/staging/{os.getenv('USER')}
# Export the arguments\n"""
        + "\n".join(export_args)
        + f"""\n\npython3 {job_name}.py {' '.join(py_args)}"""
    )

    with open(os.path.join(job_dir, f"{job_name}.sh"), "w") as f:
        f.write(sh_template)

    # Create .py file
    py_template = ""  # Empty for now
    with open(os.path.join(job_dir, f"{job_name}.py"), "w") as f:
        f.write(py_template)

    # Create queue file
    with open(os.path.join(job_dir, f"{job_name}{QUEUE_EXT}"), "w") as f:
        f.write("")

    print(f"Generated job directory: {job_dir}")
    print(
        f"Created files: {job_name}.sub, {job_name}.sh, {job_name}.py, {job_name}{QUEUE_EXT}"
    )
    print(f"Make sure to check and modify the files as needed.")


def main_menu():
    while True:
        print("\n--- AutoCHTC Main Menu ---")
        print(f"Current Directory: {os.getcwd()}")
        print("1. Create a new DAG (dag)")
        print("2. Generate/Edit a job directory or file (gen)")
        print("3. Get statistics on DAGs and jobs (In construction...) (stats)")
        print("4. Clean current directory by removing DAG-related files (clean)")
        print("5. Change working directory (cwd)")
        print("q. Quit")

        choice = input("Enter your choice: ").lower()

        if choice == "1" or choice == "dag":
            create_new_dag()

        elif choice == "2" or choice == "gen":
            generate_menu()

        elif choice == "3" or choice == "stats":
            print("Statistics feature is under construction.")

        elif choice == "4" or choice == "clean":
            clean_directory(os.getcwd())
            print("Directory cleaned of DAG-related files.")

        elif choice == "5" or choice == "cwd":
            change_working_directory()

        elif choice == "q":
            print("Quitting AutoCHTC. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    print_centered_ascii_art()
    main_menu()

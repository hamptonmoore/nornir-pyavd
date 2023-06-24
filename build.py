from nornir import InitNornir
import pyavd
import os, difflib, sys
from nornir.core.task import Task, Result
from nornir_utils.plugins.functions import print_result
from dotenv import load_dotenv
import src.edgerouter.edgerouter as edgerouter
import src.eos.eos as eos
from tqdm import tqdm

load_dotenv()

def build_config(task: Task, eos_designs, avd_facts):
    structured_config = pyavd.get_device_structured_config(task.host.name, eos_designs[task.host.name], avd_facts=avd_facts)

    config = task.host.data["manager"].generate_config(task.host.hostname, structured_config)
    
    task.host.data["designed-config"] = config
    return Result(host=task.host)

def pull_config_local(task: Task):
    try:
        with open(task.host.data["config-path"], "r") as f:
            task.host.data["running-config"] = f.read()
    except FileNotFoundError:
        task.host.data["running-config"] = ""
    return Result(host=task.host)

def diff_config(task: Task):
    changed = False
    diff = ""
    for line in difflib.unified_diff(task.host.data["running-config"].split("\n"), task.host.data["designed-config"].split("\n"), fromfile='running-config', tofile='designed-config', lineterm=''):
        diff += f'{line}\n'
        changed = True
    return Result(host=task.host, diff=diff, changed=changed)


def deploy_configs(task: Task):
    # Replace sensative variables with environment variable replacements
    for key in os.environ:
        if key.startswith("REPLACEMENTS_"):
            task.host.data["designed-config"] = task.host.data["designed-config"].replace(key, os.environ.get(key))

    task.run(task.host.data["manager"].deploy)

def save_config(task: Task):
    with open(task.host.data["config-path"], "w") as f:
        f.write(task.host.data["designed-config"])
    return Result(host=task.host, changed=True)

def increment_progress(progress: tqdm, msg=""):
    progress.update()
    progress.display()
    if msg != "":
        progress.write(f'{progress.desc}: {msg}')

def config_management(task: Task, eos_designs, avd_facts, scope="local"):
    total = 2 if scope == "local" else 3
    with tqdm(total=total, position=task.host.data["chart_id"], desc=f'{task.host.hostname}') as progress:
        device = task.host.data["device"]
        if device == "eos":
            task.host.data["manager"] = eos
        elif device == "edgerouter":
            task.host.data["manager"] = edgerouter
        else:
            return Result(host=task.host, failed=True, result=f'Device {device} is unknown')
        
        task.run(task=build_config, eos_designs=eos_designs, avd_facts=avd_facts)
        increment_progress(progress)
        
        task.host.data["config-path"] = os.path.abspath(f'configs/{task.host.name}.cfg')
        task.run(task=pull_config_local)
        result = task.run(task=diff_config)[0]

        if result.changed:
            task.run(task=save_config)
        increment_progress(progress)


        if scope == "deploy":
            task.host.data["username"] = os.getenv('DEPLOY_USERNAME')
            task.host.data["password"] = os.getenv('DEPLOY_PASSWORD')
            task.run(task=deploy_configs)
            increment_progress(progress)
            return

def run():
    # Initialize Nornir object from config_file
    nr = InitNornir(config_file="config.yml")

    eos_designs = {}
    id = 0
    for hostname in nr.inventory.hosts:
        host = nr.inventory.hosts[hostname]
        host.data["chart_id"] = id
        id += 1

        # Using .dict() or .data was not getting the group variables
        data = host.items()
        res = {}
        for (k, v) in data:
            res[k] = v

        eos_designs[hostname] = res

    # Validate input and convert types as needed
    pyavd.validate_inputs(eos_designs)

    # Generate facts
    avd_facts = pyavd.get_avd_facts(eos_designs)

    scope = "local"
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        scope = "deploy"

    output = nr.run(task=config_management, eos_designs=eos_designs, avd_facts=avd_facts, scope=scope)
    print_result(output)

run()
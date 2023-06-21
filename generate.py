from nornir import InitNornir
import pyavd
import difflib
from nornir.core.task import Task, Result
from nornir_utils.plugins.functions import print_result

def build_config(task: Task, structured_configs):
    config = pyavd.get_device_config(task.host.name, structured_configs[task.host.name])

    task.host.data["designed-config"] = config
    return Result(host=task.host)

def pull_config(task: Task):
    with open(f'configs/{task.host.name}.cfg', "r") as f:
        task.host.data["running-config"] = f.read()
    return Result(host=task.host)

def diff_config(task: Task):
    changed = False
    diff = ""
    for line in difflib.unified_diff(task.host.data["running-config"].split("\n"), task.host.data["designed-config"].split("\n"), fromfile='running-config', tofile='designed-config', lineterm=''):
        diff += f'{line}\n'
        changed = True
    return Result(host=task.host, diff=diff, changed=changed)

def deploy_config(task: Task):
    with open(f'configs/{task.host.name}.cfg', "w") as f:
        f.write(task.host.data["designed-config"])
    return Result(host=task.host, changed=True)

def config_management(task: Task, structured_configs):
    task.run(task=build_config, structured_configs=structured_configs)
    task.run(task=pull_config)
    result = task.run(task=diff_config)[0]
    if result.changed:
        task.run(task=deploy_config)

def run():
    # Initialize Nornir object from config_file
    nr = InitNornir(config_file="config.yml")

    structured_configs = {}

    for hostname in nr.inventory.hosts:
        host = nr.inventory.hosts[hostname]

        # Using .dict() or .data was not getting the group variables
        data = host.items()
        res = {}
        for (k, v) in data:
            res[k] = v

        structured_configs[hostname] = res

    output = nr.run(task=config_management, structured_configs = structured_configs)
    print_result(output)

run()
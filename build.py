from nornir import InitNornir
import pyavd
import pyeapi
import os, difflib, ssl, sys
from nornir.core.task import Task, Result
from nornir_utils.plugins.functions import print_result
from dotenv import load_dotenv

load_dotenv()

def build_config(task: Task, eos_designs, avd_facts):
    structured_config = pyavd.get_device_structured_config(task.host.name, eos_designs[task.host.name], avd_facts=avd_facts)
    config = pyavd.get_device_config(task.host.name, structured_config)

    task.host.data["designed-config"] = config
    return Result(host=task.host)

def pull_config_local(task: Task):
    try:
        with open(f'configs/{task.host.name}.cfg', "r") as f:
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

def deploy_eapi(task: Task):
    cmds = [
        "enable",
        "configure session",
        "rollback clean-config",
        {"cmd": "copy terminal: session-config", "input": task.host.data["designed-config"]},
        "show session-config diffs",
        "commit"
    ]

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    # Using the EOS default ciphers
    context.set_ciphers('AES256-SHA:DHE-RSA-AES256-SHA:AES128-SHA:DHE-RSA-AES128-SHA')

    # Connection to Client
    conn = pyeapi.client.connect(host=task.host.data["EAPI_ENDPOINT"], username=task.host.data["EAPI_USERNAME"], password=task.host.data["EAPI_PASSWORD"], context=context)
    response = conn.execute(cmds, encoding="text")
    changed = response['result'][5]['output'] != ""
    return Result(host=task.host, changed=changed, diff=response['result'][5]['output'])

def deploy_configs(task: Task):
    # Replace sensative variables with environment variable replacements
    for key in os.environ:
        if key.startswith("REPLACEMENTS_"):
            task.host.data["designed-config"] = task.host.data["designed-config"].replace(key, os.environ.get(key))

    if task.host.data["DEPLOY_MODE"] == "eapi":
        task.run(deploy_eapi)
    else:
        return Result(host=task.host, failed=True, result=f'Deploy mode {task.host.data["DEPLOY_MODE"]} is unknown')


def save_config(task: Task):
    with open(f'configs/{task.host.name}.cfg', "w") as f:
        f.write(task.host.data["designed-config"])
    return Result(host=task.host, changed=True)

def config_management(task: Task, eos_designs, avd_facts, scope="local"):
    task.run(task=build_config, eos_designs=eos_designs, avd_facts=avd_facts)

    task.run(task=pull_config_local)
    result = task.run(task=diff_config)[0]

    if result.changed:
        task.run(task=save_config)

    if scope == "deploy":
        task.host.data["EAPI_USERNAME"] = os.getenv('DEPLOY_USERNAME')
        task.host.data["EAPI_PASSWORD"] = os.getenv('DEPLOY_PASSWORD')
        if result.changed:
            return Result(host=task.host, result="cannot deploy when local config differs from designed config", failed=True)
        task.run(task=deploy_configs)
        return

def run():
    # Initialize Nornir object from config_file
    nr = InitNornir(config_file="config.yml")

    eos_designs = {}

    for hostname in nr.inventory.hosts:
        host = nr.inventory.hosts[hostname]

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
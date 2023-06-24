import jinja2
from pathlib import Path
from nornir.core.task import Task, Result
import netmiko
from netmiko.ubiquiti import UbiquitiEdgeRouterFileTransfer, UbiquitiEdgeRouterSSH

def setup_jinja():
    path = Path(__file__).parent
    templateLoader = jinja2.FileSystemLoader(searchpath=path)
    templateEnv = jinja2.Environment(loader=templateLoader)
    return templateEnv

def get_device_config(hostname: str, structured_config):
    templateEnv = setup_jinja()
    # import json
    # print(json.dumps(structured_config, indent=4))
    template = templateEnv.get_template("config.j2")
    structured_config["hostname"] = hostname
    return template.render(structured_config)

def deploy(task: Task):
    # Open SSH connection to device
    # override netmiko connection
    
    ssh_connection = UbiquitiEdgeRouterSSH(
        device_type='ubiquiti_edgerouter',
        ip=task.host.data["host"],
        username=task.host.data["username"],
        password=task.host.data["password"],
    )

    # Copy config to device from terminal
    config = task.host.data["designed-config"].replace("$", "\$")
    ssh_connection.send_command(f'cat <<EOF > /config/config.boot\n{config}\nEOF\n', cmd_verify=False)
    ssh_connection.send_command("\nconfigure\n", cmd_verify=False)
    loadResult = ssh_connection.send_command("load\n", cmd_verify=False)
    if "failed" in loadResult.lower() or "error" in loadResult.lower() or "invalid" in loadResult.lower() or "not valid" in loadResult.lower():
        return Result(host=task.host, failed=True, result=loadResult)
    diff = ssh_connection.send_command("compare\n", cmd_verify=False)
    commitResult = ssh_connection.send_command("commit\n", cmd_verify=False)
    if "Commit failed" in commitResult:
        return Result(host=task.host, failed=True, result=commitResult)
    changed = diff.strip() != "[edit]"
    if changed:
        return Result(host=task.host, changed=changed, diff=diff)
    return Result(host=task.host, changed=False)

    

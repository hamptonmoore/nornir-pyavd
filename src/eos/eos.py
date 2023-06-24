import pyeapi, pyavd
import ssl
from nornir.core.task import Task, Result


def deploy(task: Task):
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
    conn = pyeapi.client.connect(host=task.host.data["host"], username=task.host.data["username"], password=task.host.data["password"], context=context)
    response = conn.execute(cmds, encoding="text")
    changed = response['result'][4]['output'] != ""
    return Result(host=task.host, changed=changed, diff=response['result'][4]['output'])

def generate_config(hostname: str, structured_config):
    return pyavd.get_device_config(hostname, structured_config)
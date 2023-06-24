import jinja2
from pathlib import Path
from nornir.core.task import Task, Result

def setup_jinja():
    path = Path(__file__).parent
    templateLoader = jinja2.FileSystemLoader(searchpath=path)
    templateEnv = jinja2.Environment(loader=templateLoader)
    return templateEnv

def get_device_config(hostname: str, structured_config):
    templateEnv = setup_jinja()
    template = templateEnv.get_template("config.j2")
    structured_config["hostname"] = hostname
    return template.render(structured_config)

def deploy(task: Task):
    print("no deploy for edgerouter")
    return Result(host=task.host, failed=True, result="Deployment does not exist")
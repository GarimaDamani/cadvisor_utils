import time
import json
import logging
import requests
import subprocess
import urllib.parse
from config import app


class CadvisorMetricsValidator:
    def __init__(self):
        self.current_time = int(time.time())
        self.step = 15

    def get_cpu_metrics(self, hostname):
        prometheus_value = -1
        try:
            query = f"sum(container_spec_cpu_shares{{job=\"cadvisor\",id=~\"/docker/(.*)\",instance=~\"{hostname}(.*)\"}}/1024)"
            time_param = f"&time={self.current_time}&step={self.step}"
            url = f"{app.prometheus_instant_query}{urllib.parse.quote(query, safe='()*')}{time_param}"
            response = requests.get(url=url, timeout=10)
            if response.status_code is 200:
                data = json.loads(response.content)['data']['result']
                if len(data) > 0:
                    prometheus_value = round(float(data[0]['value'][1]), 2)
            ssh_cmd = "sudo bash -c \'core=0;for i in \`docker ps -aq\`;do temp=\`docker inspect \$i | grep MARATHON_APP_RESOURCE_CPUS | cut -d= -f 2 | cut -d\\\\\\\" -f 1 | bc\`;core=\`echo \\\"\$core + \$temp\\\" | bc\`;done;echo \\\"\$core\\\";\'"
            cmd = f'ssh -o StrictHostKeyChecking=no {hostname} -t \"{ssh_cmd}\"'
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            output = (p.communicate()[0])
            instance_value = round(float(bytes(output[:-2]).decode()), 2)

            if (instance_value - prometheus_value) > 0.5:
                return instance_value, prometheus_value
        except Exception as e:
            logging.log(logging.ERROR, e.__str__())
        return None, None

    def get_host_names(self):
        hostname = []
        try:
            query = f"docker_n_containers{{name=~\"(.*)\"}}"
            time_param = f"&time={self.current_time}&step={self.step}"
            url = f"{app.prometheus_instant_query}{urllib.parse.quote(query, safe='()*')}{time_param}"
            response = requests.get(url=url, timeout=10)
            if response.status_code is 200:
                data = json.loads(response.content)['data']['result']
                if len(data) > 0:
                    for item in data:
                        if item['metric']['host'] not in hostname:
                            hostname.append(item['metric']['host'])
        except Exception as e:
            logging.log(logging.ERROR, e.__str__())
        return hostname


if __name__ == '__main__':
    cadvisor_validator = CadvisorMetricsValidator()
    host_names = cadvisor_validator.get_host_names()
    output_data = {}
    for host_name in host_names:
        instance_data, prometheus_data = cadvisor_validator.get_cpu_metrics(host_name)
        if instance_data is not None and prometheus_data is not None:
            output_data[host_name] = []
            output_data[host_name].append(instance_data)
            output_data[host_name].append(prometheus_data)

    for k, v in output_data.items():
        print(k, ' : ', str(v))

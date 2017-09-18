# -*- coding:utf-8 -*-
import requests
import json
from Logging import Logging
from Singleton import Singleton


class IPProxyTool(Singleton):

    ip_pool = []
    destIP = 'https://www.baidu.com'

    def requestIPs(self, min_ip_count):
        # 讯代理
        res = requests.get('http://www.xdaili.cn/ipagent//freeip/getFreeIps?page=1&rows=10', timeout=3)
        try:
            res_dict = json.loads(res.text)
            for ip_dict in res_dict['RESULT']['rows']:
                # 循环解析proxy直到proxy池达到min_ip_count数量
                if len(self.ip_pool) >= min_ip_count:
                    return
                address = (ip_dict['ip']+':'+ip_dict['port']).encode('u8')
                self.ip_pool.append(address) if self.isValidIP(address) else None
        except Exception as e:
            # Logging.debug(res.text)
            Logging.error(e.message)

    def circleRequestIPs(self, retryTime, min_ip_count):
        if retryTime == 0 or len(self.ip_pool)>=min_ip_count:
            return
        self.requestIPs(min_ip_count)

        return self.circleRequestIPs(retryTime-1, min_ip_count)

    def refresh(self, retryTime=5, min_ip_count=10):
        for proxy_ip in self.ip_pool:
            if not self.isValidIP(proxy_ip):
                self.ip_pool.remove(proxy_ip)
        self.circleRequestIPs(retryTime, min_ip_count)

    def isValidIP(self, address):
        try:
            res = requests.get(self.destIP, verify=False, proxies={"https":"https://%s" % address}, timeout=2)
        except Exception as e:
            Logging.warning(e.message)
            Logging.warning('proxy ip: %s is invalid...' % address)
            return False
        else:
            if res.status_code == 200:
                Logging.info('proxy ip: %s is valid...' % address)
                return True
            else:
                return False

    # 获取IP池
    def getIPs(self):
        return self.ip_pool

# tool = IPProxyTool()
# tool.refresh(10, 10)
# print(tool.getIPs())
#
# print(IPProxyTool().getIPs())